#!/usr/bin/env python3
"""
07_generate_pluto_voice_fm_iq.py — ORION Phase 5C-1.

Generate a 149-ready complex FM voice IQ file from a Phase 5A WAV.

No SDR. No RF. No transmission.

Purpose:
  Prepare a full-message voice-FM IQ waveform for later safety-gated TX from 149.

Key Phase 5C improvement:
  This version adds source-audio conditioning before FM modulation:
    - speech bandpass,
    - optional dynamics compression,
    - optional soft limiting,
    - fade-in/fade-out edges,
    - exact zero-mean correction at IQ rate for cleaner IQ looping,
    - safer RMS/peak control.

Why:
  Phase 5C hi-fi RF tests showed clear voice recovery, but crackle on loud
  consonants/vowels. Final recovered WAVs were not digitally clipping, so the
  next best lever is source waveform conditioning before FM modulation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
TEST_LOG = ROOT / "docs" / "test_logs" / "TEST_LOG.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate 149-ready FM voice IQ. No SDR, no RF.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--input", required=True, help="Input WAV from Phase 5A.")
    p.add_argument("--label", default="pluto_voice_fm", help="Output label.")

    p.add_argument("--iq-rate", type=int, default=1_000_000, help="IQ sample rate in Hz.")
    p.add_argument("--offset", type=float, default=100_000.0, help="Baseband carrier offset in Hz.")
    p.add_argument("--deviation", type=float, default=12_000.0, help="FM peak deviation in Hz.")
    p.add_argument("--lowcut", type=float, default=60.0, help="Speech high-pass cutoff in Hz.")
    p.add_argument("--highcut", type=float, default=7_000.0, help="Speech low-pass cutoff in Hz.")
    p.add_argument("--amplitude", type=float, default=0.10, help="Normalized IQ amplitude for future TX.")
    p.add_argument("--audio-out-rate", type=int, default=44_100, help="Preview recovered WAV rate.")

    # Source-audio conditioning.
    p.add_argument("--target-rms", type=float, default=0.18, help="Conditioned speech RMS target.")
    p.add_argument("--target-peak", type=float, default=0.72, help="Conditioned speech peak target.")
    p.add_argument("--no-compressor", action="store_true", help="Disable source-audio compressor.")
    p.add_argument("--compressor-threshold-db", type=float, default=-18.0)
    p.add_argument("--compressor-ratio", type=float, default=3.0)
    p.add_argument("--compressor-attack-ms", type=float, default=5.0)
    p.add_argument("--compressor-release-ms", type=float, default=80.0)
    p.add_argument("--softclip-drive", type=float, default=1.25, help="1.0 disables most soft limiting.")
    p.add_argument("--fade-ms", type=float, default=25.0, help="Fade at message edges to reduce loop clicks.")
    p.add_argument("--disable-loop-mean-correction", action="store_true",
                   help="Do not force zero mean after resampling to IQ rate.")

    return p.parse_args()


def read_wav_mono(path: Path) -> tuple[int, np.ndarray]:
    sr, data = wavfile.read(path)
    if data.ndim == 2:
        data = data.mean(axis=1)

    if np.issubdtype(data.dtype, np.integer):
        data = data.astype(np.float32) / np.iinfo(data.dtype).max
    else:
        data = data.astype(np.float32)

    data = np.nan_to_num(data)
    data = np.clip(data, -1.0, 1.0)
    return int(sr), data.astype(np.float32)


def resample_to(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return x.astype(np.float32)
    ratio = Fraction(dst_rate, src_rate).limit_denominator(10_000)
    return signal.resample_poly(x, ratio.numerator, ratio.denominator).astype(np.float32)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float32) ** 2))) if len(x) else 0.0


def peak_abs(x: np.ndarray) -> float:
    return float(np.max(np.abs(x))) if len(x) else 0.0


def normalize_to_rms_and_peak(
    x: np.ndarray,
    target_rms: float,
    target_peak: float,
) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    x = x - float(np.mean(x))

    r = rms(x)
    if r > 1e-9 and target_rms > 0:
        x = x * (target_rms / r)

    p = peak_abs(x)
    if p > target_peak and p > 0:
        x = x * (target_peak / p)

    return np.clip(x, -target_peak, target_peak).astype(np.float32)


def speech_bandpass(x: np.ndarray, sr: int, lowcut: float, highcut: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    x = x - float(np.mean(x))

    nyq = sr / 2.0
    low = max(1.0, lowcut) / nyq
    high = min(highcut, 0.95 * nyq) / nyq

    if low >= high:
        raise ValueError(f"Invalid speech filter: lowcut={lowcut}, highcut={highcut}, sr={sr}")

    sos = signal.butter(4, [low, high], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, x).astype(np.float32)


def smooth_envelope_abs(
    x: np.ndarray,
    sr: int,
    attack_ms: float,
    release_ms: float,
) -> np.ndarray:
    """
    Simple peak-envelope follower for compressor gain control.
    """
    x_abs = np.abs(x).astype(np.float32)
    env = np.zeros_like(x_abs)

    attack = np.exp(-1.0 / max(1.0, attack_ms * 1e-3 * sr))
    release = np.exp(-1.0 / max(1.0, release_ms * 1e-3 * sr))

    prev = 0.0
    for i, val in enumerate(x_abs):
        coeff = attack if val > prev else release
        prev = coeff * prev + (1.0 - coeff) * val
        env[i] = prev

    return np.maximum(env, 1e-8)


def compress_audio(
    x: np.ndarray,
    sr: int,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
) -> np.ndarray:
    """
    Lightweight feed-forward compressor.

    This is not meant as studio mastering. It is meant to reduce large speech
    peaks before FM modulation, so loud syllables do not dominate instantaneous
    deviation.
    """
    x = np.asarray(x, dtype=np.float32)
    if ratio <= 1.0:
        return x

    env = smooth_envelope_abs(x, sr, attack_ms, release_ms)
    level_db = 20.0 * np.log10(np.maximum(env, 1e-8))

    over_db = level_db - threshold_db
    compressed_over_db = np.where(over_db > 0.0, over_db / ratio, over_db)
    gain_db = compressed_over_db - over_db
    gain = 10.0 ** (gain_db / 20.0)

    y = x * gain.astype(np.float32)
    return y.astype(np.float32)


def softclip_audio(x: np.ndarray, drive: float) -> np.ndarray:
    """
    Soft limiter using tanh. drive=1.0 is mild; larger values limit peaks more.
    """
    x = np.asarray(x, dtype=np.float32)
    if drive <= 1.0:
        return x.astype(np.float32)

    y = np.tanh(drive * x) / np.tanh(drive)
    return y.astype(np.float32)


def apply_edge_fades(x: np.ndarray, sr: int, fade_ms: float) -> np.ndarray:
    """
    Fade message edges to reduce loop-boundary clicks when the full IQ file wraps.
    """
    x = np.asarray(x, dtype=np.float32).copy()
    fade_n = int(max(0.0, fade_ms) * 1e-3 * sr)

    if fade_n <= 1 or 2 * fade_n >= len(x):
        return x

    fade_in = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, fade_n, dtype=np.float32)

    x[:fade_n] *= fade_in
    x[-fade_n:] *= fade_out
    return x.astype(np.float32)


def condition_speech_audio(
    x: np.ndarray,
    sr: int,
    lowcut: float,
    highcut: float,
    target_rms: float,
    target_peak: float,
    use_compressor: bool,
    compressor_threshold_db: float,
    compressor_ratio: float,
    compressor_attack_ms: float,
    compressor_release_ms: float,
    softclip_drive: float,
    fade_ms: float,
) -> np.ndarray:
    y = speech_bandpass(x, sr, lowcut, highcut)

    if use_compressor:
        y = compress_audio(
            y,
            sr=sr,
            threshold_db=compressor_threshold_db,
            ratio=compressor_ratio,
            attack_ms=compressor_attack_ms,
            release_ms=compressor_release_ms,
        )

    y = normalize_to_rms_and_peak(y, target_rms=target_rms, target_peak=target_peak)
    y = softclip_audio(y, drive=softclip_drive)
    y = normalize_to_rms_and_peak(y, target_rms=target_rms, target_peak=target_peak)
    y = apply_edge_fades(y, sr, fade_ms=fade_ms)
    y = y - float(np.mean(y))

    # Final peak safety.
    p = peak_abs(y)
    if p > target_peak and p > 0:
        y = y * (target_peak / p)

    return y.astype(np.float32)


def enforce_zero_mean_for_loop(message_iq_rate: np.ndarray) -> np.ndarray:
    """
    Force exact zero mean at IQ rate.

    For a repeated FM IQ message, the loop boundary is cleaner when the integrated
    FM phase over one full message is near an integer number of cycles. With a
    carrier offset that already completes an integer number of cycles over a
    5-second message, forcing message mean to zero removes the residual FM phase
    drift across the wrap.
    """
    y = np.asarray(message_iq_rate, dtype=np.float32)
    y = y - float(np.mean(y, dtype=np.float64))
    return y.astype(np.float32)


def fm_modulate_with_offset(
    message: np.ndarray,
    fs: int,
    deviation_hz: float,
    offset_hz: float,
    amplitude: float,
) -> np.ndarray:
    message = np.clip(message.astype(np.float32), -1.0, 1.0)
    n = np.arange(len(message), dtype=np.float64)

    fm_phase = np.cumsum(2.0 * np.pi * deviation_hz * message / fs)
    carrier_phase = 2.0 * np.pi * offset_hz * n / fs
    iq = amplitude * np.exp(1j * (carrier_phase + fm_phase))
    return iq.astype(np.complex64)


def fm_demod_preview(iq: np.ndarray, fs: int, deviation_hz: float, offset_hz: float) -> np.ndarray:
    n = np.arange(len(iq), dtype=np.float64)
    mixed = iq * np.exp(-1j * 2.0 * np.pi * offset_hz * n / fs)
    dphi = np.angle(mixed[1:] * np.conj(mixed[:-1]))
    recovered = dphi * fs / (2.0 * np.pi * deviation_hz)
    recovered = np.concatenate([[recovered[0]], recovered])
    recovered = recovered - np.mean(recovered)
    return recovered.astype(np.float32)


def write_wav(path: Path, sr: int, audio: np.ndarray) -> None:
    audio = np.nan_to_num(np.asarray(audio, dtype=np.float32))
    p = peak_abs(audio)
    if p > 1.0:
        audio = audio / p
    audio = np.clip(audio, -1.0, 1.0)
    wavfile.write(path, sr, np.int16(audio * 32767))


def spectrum_db_complex(iq: np.ndarray, fs: int, max_n: int = 262_144) -> tuple[np.ndarray, np.ndarray]:
    n = min(len(iq), max_n)
    x = iq[:n]
    win = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(x * win))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
    mag = np.abs(spec)
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    db -= np.max(db)
    return freq, db


def spectrum_db_real(x: np.ndarray, fs: int, max_n: int = 262_144) -> tuple[np.ndarray, np.ndarray]:
    n = min(len(x), max_n)
    x = x[:n]
    win = np.hanning(n)
    spec = np.fft.rfft(x * win)
    freq = np.fft.rfftfreq(n, d=1.0 / fs)
    mag = np.abs(spec)
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    db -= np.max(db)
    return freq, db


def save_plot(
    png_path: Path,
    raw: np.ndarray,
    conditioned: np.ndarray,
    recovered: np.ndarray,
    audio_sr: int,
    rec_sr: int,
    iq: np.ndarray,
    iq_rate: int,
    label: str,
) -> None:
    seconds = min(1.0, len(raw) / audio_sr, len(conditioned) / audio_sr, len(recovered) / rec_sr)
    n_raw = int(seconds * audio_sr)
    n_cond = int(seconds * audio_sr)
    n_rec = int(seconds * rec_sr)

    t_raw = np.arange(n_raw) / audio_sr
    t_cond = np.arange(n_cond) / audio_sr
    t_rec = np.arange(n_rec) / rec_sr

    f_raw, db_raw = spectrum_db_real(raw, audio_sr)
    f_cond, db_cond = spectrum_db_real(conditioned, audio_sr)
    f_rec, db_rec = spectrum_db_real(recovered, rec_sr)
    f_iq, db_iq = spectrum_db_complex(iq, iq_rate)

    fig, axes = plt.subplots(4, 1, figsize=(11, 13), constrained_layout=True)
    fig.suptitle(f"ORION Phase 5C-1 149-Ready Voice FM IQ — {label}")

    axes[0].plot(t_raw, raw[:n_raw], alpha=0.65, label="raw input")
    axes[0].plot(t_cond, conditioned[:n_cond], alpha=0.85, label="conditioned input")
    axes[0].plot(t_rec, recovered[:n_rec], alpha=0.75, label="preview recovered")
    axes[0].set_title("Audio Preview, First Second")
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Amplitude")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(f_raw, db_raw, alpha=0.65, label="raw input")
    axes[1].plot(f_cond, db_cond, alpha=0.85, label="conditioned input")
    axes[1].plot(f_rec, db_rec, alpha=0.75, label="preview recovered")
    axes[1].set_title("Audio Spectrum Preview")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Magnitude (dB relative)")
    axes[1].set_xlim(0, 10_000)
    axes[1].set_ylim(-100, 5)
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(f_iq / 1000.0, db_iq)
    axes[2].set_title("149-Ready Complex FM IQ Spectrum")
    axes[2].set_xlabel("Frequency Offset from 915 MHz LO (kHz)")
    axes[2].set_ylabel("Magnitude (dB relative)")
    axes[2].set_xlim(-80, 180)
    axes[2].set_ylim(-100, 5)
    axes[2].grid(True, alpha=0.3)

    edge_n = min(len(conditioned), int(0.08 * audio_sr))
    edge_t = np.arange(edge_n) / audio_sr
    axes[3].plot(edge_t, conditioned[:edge_n], label="start edge")
    axes[3].plot(edge_t, conditioned[-edge_n:], label="end edge")
    axes[3].set_title("Conditioned Message Edge Check")
    axes[3].set_xlabel("Time within edge window (s)")
    axes[3].set_ylabel("Amplitude")
    axes[3].legend()
    axes[3].grid(True, alpha=0.3)

    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5C-1 | Generate 149-ready voice FM IQ | "
        f"07_generate_pluto_voice_fm_iq.py | {status} | {evidence} | {notes} |"
    )
    existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


def safe_label_text(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in s)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"[error] Input WAV not found: {input_path}")
        sys.exit(1)

    if not (0 < args.amplitude <= 0.5):
        print("[error] amplitude must be > 0 and <= 0.5 for this safety-prep script.")
        sys.exit(1)

    if args.target_peak <= 0 or args.target_peak > 1.0:
        print("[error] target-peak must be in (0, 1].")
        sys.exit(1)

    if args.target_rms <= 0 or args.target_rms > args.target_peak:
        print("[error] target-rms must be >0 and <= target-peak.")
        sys.exit(1)

    estimated_half_bw = args.deviation + args.highcut
    if abs(args.offset) + estimated_half_bw > 0.45 * args.iq_rate:
        print("[error] Offset/deviation/audio bandwidth too close to Nyquist.")
        print(f"        abs(offset)+deviation+highcut = {abs(args.offset)+estimated_half_bw:.1f} Hz")
        print(f"        0.45*iq_rate                  = {0.45*args.iq_rate:.1f} Hz")
        sys.exit(1)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = safe_label_text(args.label)

    prefix = AUDIO_DIR / f"pluto_voice_fm_{safe_label}_{timestamp}"
    iq_path = Path(str(prefix) + "_iq.npy")
    preview_wav_path = Path(str(prefix) + "_preview_recovered.wav")
    conditioned_wav_path = Path(str(prefix) + "_conditioned.wav")
    json_path = Path(str(prefix) + ".json")
    png_path = Path(str(prefix) + ".png")

    print("=" * 72)
    print("ORION Phase 5C-1 — Generate 149-Ready Voice FM IQ")
    print("=" * 72)
    print("No SDR. No RF. No transmission.")
    print()
    print(f"Input WAV       : {input_path}")
    print(f"IQ sample rate  : {args.iq_rate} Hz")
    print(f"Carrier offset  : {args.offset:.1f} Hz")
    print(f"FM deviation    : {args.deviation:.1f} Hz")
    print(f"Speech band     : {args.lowcut:.1f} Hz to {args.highcut:.1f} Hz")
    print(f"IQ amplitude    : {args.amplitude:.3f}")
    print(f"Compressor      : {'off' if args.no_compressor else 'on'}")
    print(f"Target RMS/peak : {args.target_rms:.3f} / {args.target_peak:.3f}")
    print(f"Fade edges      : {args.fade_ms:.1f} ms")

    audio_sr, raw_audio = read_wav_mono(input_path)

    conditioned = condition_speech_audio(
        raw_audio,
        sr=audio_sr,
        lowcut=args.lowcut,
        highcut=args.highcut,
        target_rms=args.target_rms,
        target_peak=args.target_peak,
        use_compressor=not args.no_compressor,
        compressor_threshold_db=args.compressor_threshold_db,
        compressor_ratio=args.compressor_ratio,
        compressor_attack_ms=args.compressor_attack_ms,
        compressor_release_ms=args.compressor_release_ms,
        softclip_drive=args.softclip_drive,
        fade_ms=args.fade_ms,
    )

    msg_iq_rate = resample_to(conditioned, audio_sr, args.iq_rate)

    if not args.disable_loop_mean_correction:
        msg_iq_rate = enforce_zero_mean_for_loop(msg_iq_rate)

    # Safety after IQ-rate correction.
    msg_peak = peak_abs(msg_iq_rate)
    if msg_peak > args.target_peak and msg_peak > 0:
        msg_iq_rate = msg_iq_rate * (args.target_peak / msg_peak)

    iq = fm_modulate_with_offset(
        msg_iq_rate,
        args.iq_rate,
        args.deviation,
        args.offset,
        args.amplitude,
    )

    recovered_iq_rate = fm_demod_preview(iq, args.iq_rate, args.deviation, args.offset)
    recovered = resample_to(recovered_iq_rate, args.iq_rate, args.audio_out_rate)
    recovered = speech_bandpass(recovered, args.audio_out_rate, args.lowcut, args.highcut)
    recovered = normalize_to_rms_and_peak(recovered, target_rms=args.target_rms, target_peak=args.target_peak)

    np.save(iq_path, iq)
    write_wav(conditioned_wav_path, audio_sr, conditioned)
    write_wav(preview_wav_path, args.audio_out_rate, recovered)

    rec_at_input_rate = resample_to(recovered, args.audio_out_rate, audio_sr)
    n = min(len(conditioned), len(rec_at_input_rate))
    a = conditioned[:n]
    b = rec_at_input_rate[:n]
    corr = float(np.corrcoef(a, b)[0, 1]) if n > 10 and np.std(a) > 0 and np.std(b) > 0 else 0.0
    err_rms = float(np.sqrt(np.mean((a - b) ** 2))) if n else 0.0

    save_plot(
        png_path,
        raw_audio,
        conditioned,
        recovered,
        audio_sr,
        args.audio_out_rate,
        iq,
        args.iq_rate,
        safe_label,
    )

    iq_phase_cycles = float(args.offset * len(iq) / args.iq_rate)
    fm_phase_cycles = float(args.deviation * np.sum(msg_iq_rate, dtype=np.float64) / args.iq_rate)

    metadata = {
        "phase": "Phase 5C-1",
        "script": "07_generate_pluto_voice_fm_iq.py",
        "label": safe_label,
        "timestamp": timestamp,
        "input_wav": str(input_path),
        "audio_sample_rate_hz": audio_sr,
        "iq_sample_rate_hz": args.iq_rate,
        "baseband_carrier_offset_hz": args.offset,
        "fm_deviation_hz": args.deviation,
        "speech_lowcut_hz": args.lowcut,
        "speech_highcut_hz": args.highcut,
        "iq_amplitude": args.amplitude,
        "estimated_carson_half_bandwidth_hz": estimated_half_bw,
        "conditioning": {
            "target_rms": args.target_rms,
            "target_peak": args.target_peak,
            "compressor_enabled": not args.no_compressor,
            "compressor_threshold_db": args.compressor_threshold_db,
            "compressor_ratio": args.compressor_ratio,
            "compressor_attack_ms": args.compressor_attack_ms,
            "compressor_release_ms": args.compressor_release_ms,
            "softclip_drive": args.softclip_drive,
            "fade_ms": args.fade_ms,
            "loop_mean_correction_enabled": not args.disable_loop_mean_correction,
            "raw_peak": peak_abs(raw_audio),
            "raw_rms": rms(raw_audio),
            "conditioned_peak": peak_abs(conditioned),
            "conditioned_rms": rms(conditioned),
            "iq_rate_message_peak": peak_abs(msg_iq_rate),
            "iq_rate_message_rms": rms(msg_iq_rate),
            "carrier_phase_cycles_per_loop": iq_phase_cycles,
            "fm_phase_cycles_per_loop": fm_phase_cycles,
        },
        "iq_samples": int(len(iq)),
        "iq_duration_s": float(len(iq) / args.iq_rate),
        "iq_dtype": "complex64",
        "iq_path": str(iq_path.relative_to(ROOT)),
        "conditioned_wav": str(conditioned_wav_path.relative_to(ROOT)),
        "preview_recovered_wav": str(preview_wav_path.relative_to(ROOT)),
        "plot_path": str(png_path.relative_to(ROOT)),
        "correlation_conditioned_vs_preview": corr,
        "preview_error_rms": err_rms,
        "rf_status": "NO SDR, NO RF, NO TRANSMISSION",
        "intended_future_rf_center_hz": 915_000_000,
        "intended_future_voice_absolute_hz": 915_000_000 + args.offset,
        "intended_future_tx_identity": "149",
        "intended_future_rx_identity": "e9e",
    }

    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    status = "PASS" if corr > 0.95 else "REVIEW"
    append_testlog(
        status,
        str(png_path.relative_to(ROOT)),
        f"label={safe_label} offset={args.offset:.0f}Hz dev={args.deviation:.0f}Hz "
        f"iq_rate={args.iq_rate}Hz amp={args.amplitude:.3f} corr={corr:.4f}",
    )

    print()
    print("[+] IQ saved:                " + str(iq_path))
    print("[+] Conditioned WAV saved:   " + str(conditioned_wav_path))
    print("[+] Preview recovered WAV:   " + str(preview_wav_path))
    print("[+] Metadata saved:          " + str(json_path))
    print("[+] Plot saved:              " + str(png_path))
    print()
    print(f"Conditioned peak/RMS : {peak_abs(conditioned):.4f} / {rms(conditioned):.4f}")
    print(f"IQ-rate msg peak/RMS : {peak_abs(msg_iq_rate):.4f} / {rms(msg_iq_rate):.4f}")
    print(f"Carrier cycles/loop  : {iq_phase_cycles:.6f}")
    print(f"FM cycles/loop       : {fm_phase_cycles:.9f}")
    print(f"Preview correlation  : {corr:.4f}")
    print(f"Preview error RMS    : {err_rms:.5f}")
    print(f"Verdict              : {status}")
    print()
    print("Done. This generated a waveform file only; no SDR was used.")


if __name__ == "__main__":
    main()