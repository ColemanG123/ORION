#!/usr/bin/env python3
"""
07_generate_pluto_voice_fm_iq.py — ORION Phase 5C-1.

Generate a Pluto-ready complex FM voice IQ file from a Phase 5A WAV.

No SDR. No RF. No transmission.

This script prepares the waveform that could later be transmitted by Pluto B
after a separate safety review and explicit RF confirmation step.
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
        description="Generate Pluto-ready FM voice IQ. No SDR, no RF.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", required=True, help="Input WAV from Phase 5A.")
    p.add_argument("--label", default="pluto_voice_fm", help="Output label.")
    p.add_argument("--iq-rate", type=int, default=1_000_000, help="IQ sample rate in Hz.")
    p.add_argument("--offset", type=float, default=100_000.0, help="Baseband carrier offset in Hz.")
    p.add_argument("--deviation", type=float, default=15_000.0, help="FM peak deviation in Hz.")
    p.add_argument("--lowcut", type=float, default=60.0, help="Speech high-pass cutoff in Hz.")
    p.add_argument("--highcut", type=float, default=8_000.0, help="Speech low-pass cutoff in Hz.")
    p.add_argument("--amplitude", type=float, default=0.10, help="Normalized IQ amplitude for future TX.")
    p.add_argument("--audio-out-rate", type=int, default=44_100, help="Preview recovered WAV rate.")
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
    return int(sr), data


def resample_to(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return x.astype(np.float32)
    ratio = Fraction(dst_rate, src_rate).limit_denominator(10_000)
    return signal.resample_poly(x, ratio.numerator, ratio.denominator).astype(np.float32)


def speech_condition(x: np.ndarray, sr: int, lowcut: float, highcut: float) -> np.ndarray:
    x = x.astype(np.float32)
    x = x - float(np.mean(x))

    nyq = sr / 2.0
    low = max(1.0, lowcut) / nyq
    high = min(highcut, nyq * 0.95) / nyq
    if low >= high:
        raise ValueError(f"Invalid speech filter: lowcut={lowcut}, highcut={highcut}, sr={sr}")

    sos = signal.butter(4, [low, high], btype="bandpass", output="sos")
    y = signal.sosfiltfilt(sos, x)

    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 0:
        y = 0.85 * y / peak

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
    audio = np.nan_to_num(audio)
    audio = np.clip(audio, -1.0, 1.0)
    wavfile.write(path, sr, np.int16(audio * 32767))


def spectrum_db_complex(iq: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(iq)
    win = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(iq * win))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
    mag = np.abs(spec)
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    db -= np.max(db)
    return freq, db


def spectrum_db_real(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(x)
    win = np.hanning(n)
    spec = np.fft.rfft(x * win)
    freq = np.fft.rfftfreq(n, d=1.0 / fs)
    mag = np.abs(spec)
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    db -= np.max(db)
    return freq, db


def save_plot(
    png_path: Path,
    conditioned: np.ndarray,
    recovered: np.ndarray,
    audio_sr: int,
    rec_sr: int,
    iq: np.ndarray,
    iq_rate: int,
    label: str,
) -> None:
    seconds = min(1.0, len(conditioned) / audio_sr, len(recovered) / rec_sr)
    n_a = int(seconds * audio_sr)
    n_r = int(seconds * rec_sr)

    t_a = np.arange(n_a) / audio_sr
    t_r = np.arange(n_r) / rec_sr

    f_a, db_a = spectrum_db_real(conditioned, audio_sr)
    f_r, db_r = spectrum_db_real(recovered, rec_sr)
    f_iq, db_iq = spectrum_db_complex(iq, iq_rate)

    fig, axes = plt.subplots(3, 1, figsize=(10, 10), constrained_layout=True)
    fig.suptitle(f"ORION Phase 5C-1 Pluto-Ready Voice FM IQ — {label}")

    axes[0].plot(t_a, conditioned[:n_a], label="conditioned input")
    axes[0].plot(t_r, recovered[:n_r], alpha=0.75, label="preview recovered")
    axes[0].set_title("Audio Preview, First Second")
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Amplitude")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(f_a, db_a, label="conditioned input")
    axes[1].plot(f_r, db_r, alpha=0.75, label="preview recovered")
    axes[1].set_title("Audio Spectrum Preview")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Magnitude (dB relative)")
    axes[1].set_xlim(0, 10_000)
    axes[1].set_ylim(-100, 5)
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(f_iq / 1000.0, db_iq)
    axes[2].set_title("Pluto-Ready Complex FM IQ Spectrum")
    axes[2].set_xlabel("Frequency Offset from Pluto LO (kHz)")
    axes[2].set_ylabel("Magnitude (dB relative)")
    axes[2].set_xlim(-50, 180)
    axes[2].set_ylim(-100, 5)
    axes[2].grid(True, alpha=0.3)

    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5C-1 | Generate Pluto-ready voice FM IQ | "
        f"07_generate_pluto_voice_fm_iq.py | {status} | {evidence} | {notes} |"
    )
    existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"[error] Input WAV not found: {input_path}")
        sys.exit(1)

    if not (0 < args.amplitude <= 0.5):
        print("[error] amplitude must be > 0 and <= 0.5 for this safety-prep script.")
        sys.exit(1)

    # Carson-rule sanity check. This is not exact, but prevents obvious aliasing.
    estimated_half_bw = args.deviation + args.highcut
    if abs(args.offset) + estimated_half_bw > 0.45 * args.iq_rate:
        print("[error] Offset/deviation/audio bandwidth too close to Nyquist.")
        print(f"        abs(offset)+deviation+highcut = {abs(args.offset)+estimated_half_bw:.1f} Hz")
        print(f"        0.45*iq_rate                  = {0.45*args.iq_rate:.1f} Hz")
        sys.exit(1)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in args.label)

    prefix = AUDIO_DIR / f"pluto_voice_fm_{safe_label}_{timestamp}"
    iq_path = Path(str(prefix) + "_iq.npy")
    preview_wav_path = Path(str(prefix) + "_preview_recovered.wav")
    conditioned_wav_path = Path(str(prefix) + "_conditioned.wav")
    json_path = Path(str(prefix) + ".json")
    png_path = Path(str(prefix) + ".png")

    print("=" * 72)
    print("ORION Phase 5C-1 — Generate Pluto-Ready Voice FM IQ")
    print("=" * 72)
    print("No SDR. No RF. No transmission.")
    print()
    print(f"Input WAV       : {input_path}")
    print(f"IQ sample rate  : {args.iq_rate} Hz")
    print(f"Carrier offset  : {args.offset:.1f} Hz")
    print(f"FM deviation    : {args.deviation:.1f} Hz")
    print(f"Speech band     : {args.lowcut:.1f} Hz to {args.highcut:.1f} Hz")
    print(f"IQ amplitude    : {args.amplitude:.3f}")

    audio_sr, audio = read_wav_mono(input_path)
    conditioned = speech_condition(audio, audio_sr, args.lowcut, args.highcut)
    msg_iq_rate = resample_to(conditioned, audio_sr, args.iq_rate)

    iq = fm_modulate_with_offset(
        msg_iq_rate,
        args.iq_rate,
        args.deviation,
        args.offset,
        args.amplitude,
    )

    recovered_iq_rate = fm_demod_preview(iq, args.iq_rate, args.deviation, args.offset)
    recovered = resample_to(recovered_iq_rate, args.iq_rate, args.audio_out_rate)
    recovered = speech_condition(recovered, args.audio_out_rate, args.lowcut, args.highcut)

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
        conditioned,
        recovered,
        audio_sr,
        args.audio_out_rate,
        iq,
        args.iq_rate,
        safe_label,
    )

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
        "intended_future_tone_absolute_hz": 915_000_000 + args.offset,
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
    print(f"Preview correlation : {corr:.4f}")
    print(f"Preview error RMS   : {err_rms:.5f}")
    print(f"Verdict             : {status}")
    print()
    print("Done. This generated a waveform file only; no SDR was used.")


if __name__ == "__main__":
    main()
