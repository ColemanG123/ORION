#!/usr/bin/env python3
"""
10_demod_voice_fm_capture.py - ORION Phase 5C scanned voice-FM demodulator.

Purpose:
  Demodulate received voice-FM IQ captured by e9e after transmission from 149.

This script:
  - scans around the expected RF offset,
  - chooses a received offset and active window,
  - demodulates FM,
  - saves raw and cleaned recovered audio,
  - applies optional cleanup without tuning to one speaker's voice.

No SDR. No RF. Offline analysis only.
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
        description="ORION Phase 5C scanned voice-FM demodulator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--iq", required=True, help="RX IQ .npy capture from e9e.")
    p.add_argument("--label", default="e9e_149_voice_fm_scan", help="Output label.")

    p.add_argument("--rate", type=int, default=1_000_000, help="RX IQ sample rate in Hz.")
    p.add_argument("--expected-offset", "--offset", dest="expected_offset", type=float, default=100_000.0)
    p.add_argument("--offset-span", type=float, default=30_000.0)
    p.add_argument("--offset-step", type=float, default=1_000.0)

    p.add_argument("--deviation", type=float, default=5_000.0, help="FM deviation used by TX waveform.")
    p.add_argument("--rf-lowpass", type=float, default=12_000.0, help="Complex LPF cutoff after mixdown.")
    p.add_argument("--analysis-band", type=float, default=9_000.0, help="Half-band for energy scoring.")

    p.add_argument("--audio-rate", type=int, default=44_100)
    p.add_argument("--lowcut", type=float, default=100.0, help="Raw recovered speech high-pass cutoff.")
    p.add_argument("--highcut", type=float, default=3_400.0, help="Raw recovered speech low-pass cutoff.")

    p.add_argument("--fft-size", type=int, default=65_536)
    p.add_argument("--hop-size", type=int, default=32_768)
    p.add_argument("--active-threshold-frac", type=float, default=0.35)
    p.add_argument("--active-pad", type=float, default=0.35)

    p.add_argument("--force-start", type=float, default=None)
    p.add_argument("--force-stop", type=float, default=None)

    # Cleanup stage. These are channel/artifact controls, not speaker-specific EQ.
    p.add_argument("--trim-active-start", type=float, default=0.8,
                   help="Seconds trimmed from start of active audio for cleaned output only.")
    p.add_argument("--notch-hz", type=float, action="append", default=[],
                   help="Optional audio notch center frequency. Repeatable.")
    p.add_argument("--notch-q", type=float, default=35.0)
    p.add_argument("--clean-lowcut", type=float, default=80.0,
                   help="Cleaned-output high-pass cutoff.")
    p.add_argument("--clean-highcut", type=float, default=3_400.0,
                   help="Cleaned-output low-pass cutoff. Keep broad for general voice.")

    return p.parse_args()


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5C DEMOD | Scanned voice-FM demod/cleanup | "
        f"10_demod_voice_fm_capture.py | {status} | {evidence} | {notes} |"
    )
    existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


def safe_label(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in s)


def resample_to(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return x.astype(np.float32)
    ratio = Fraction(dst_rate, src_rate).limit_denominator(10_000)
    return signal.resample_poly(x, ratio.numerator, ratio.denominator).astype(np.float32)


def normalize_audio(x: np.ndarray, target_peak: float = 0.90) -> np.ndarray:
    x = np.nan_to_num(np.asarray(x, dtype=np.float32))
    x = x - float(np.mean(x))
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0:
        x = target_peak * x / peak
    return np.clip(x, -1.0, 1.0).astype(np.float32)


def bandpass_audio(x: np.ndarray, sr: int, lowcut: float, highcut: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    x = x - float(np.mean(x))

    nyq = sr / 2.0
    low = max(1.0, lowcut) / nyq
    high = min(highcut, 0.95 * nyq) / nyq

    if low >= high:
        return x.astype(np.float32)

    sos = signal.butter(4, [low, high], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, x).astype(np.float32)


def cleanup_audio(
    x: np.ndarray,
    sr: int,
    trim_start_s: float,
    notch_hz: list[float],
    notch_q: float,
    clean_lowcut: float,
    clean_highcut: float,
) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)

    trim_n = int(max(0.0, trim_start_s) * sr)
    if trim_n < len(x):
        x = x[trim_n:]

    x = x - float(np.mean(x))

    # Gentle high-pass. This is not voice-specific; it removes LF rumble/DC.
    hp_norm = max(1.0, clean_lowcut) / (sr / 2.0)
    if 0 < hp_norm < 0.95:
        sos_hp = signal.butter(2, hp_norm, btype="highpass", output="sos")
        x = signal.sosfiltfilt(sos_hp, x).astype(np.float32)

    # Optional narrow notches for channel artifacts.
    for hz in notch_hz:
        if 0 < hz < sr / 2:
            b, a = signal.iirnotch(w0=hz, Q=notch_q, fs=sr)
            x = signal.filtfilt(b, a, x).astype(np.float32)

    # Preserve a general comms-grade voice band.
    lp_norm = min(clean_highcut, 0.95 * sr / 2.0) / (sr / 2.0)
    if 0 < lp_norm < 0.95:
        sos_lp = signal.butter(4, lp_norm, btype="lowpass", output="sos")
        x = signal.sosfiltfilt(sos_lp, x).astype(np.float32)

    return normalize_audio(x)


def write_wav(path: Path, sr: int, audio: np.ndarray) -> None:
    audio = normalize_audio(audio)
    wavfile.write(path, sr, np.int16(audio * 32767))


def spectrum_complex(iq: np.ndarray, fs: int, max_n: int = 262_144):
    n = min(len(iq), max_n)
    x = iq[:n]
    win = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(x * win))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
    db = 20.0 * np.log10(np.maximum(np.abs(spec), 1e-12))
    db -= np.max(db)
    return freq, db


def spectrum_real(x: np.ndarray, fs: int, max_n: int = 262_144):
    n = min(len(x), max_n)
    x = np.asarray(x[:n], dtype=np.float32)
    win = np.hanning(n)
    spec = np.fft.rfft(x * win)
    freq = np.fft.rfftfreq(n, d=1.0 / fs)
    db = 20.0 * np.log10(np.maximum(np.abs(spec), 1e-12))
    db -= np.max(db)
    return freq, db


def contiguous_runs(indices: np.ndarray) -> list[tuple[int, int]]:
    if len(indices) == 0:
        return []
    runs = []
    start = int(indices[0])
    prev = int(indices[0])
    for value in indices[1:]:
        value = int(value)
        if value == prev + 1:
            prev = value
        else:
            runs.append((start, prev))
            start = value
            prev = value
    runs.append((start, prev))
    return runs


def scan_offsets_and_time(
    iq: np.ndarray,
    fs: int,
    expected_offset: float,
    offset_span: float,
    offset_step: float,
    analysis_band: float,
    fft_size: int,
    hop_size: int,
):
    if len(iq) < fft_size:
        raise ValueError("IQ capture is shorter than fft-size.")

    offsets = np.arange(
        expected_offset - offset_span,
        expected_offset + offset_span + 0.1 * offset_step,
        offset_step,
        dtype=np.float64,
    )

    freqs = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1.0 / fs))
    masks = []
    for off in offsets:
        mask = np.abs(freqs - off) <= analysis_band
        masks.append(mask)

    window = np.hanning(fft_size).astype(np.float32)
    starts = np.arange(0, len(iq) - fft_size + 1, hop_size, dtype=np.int64)
    frame_times = (starts + fft_size / 2.0) / fs
    scores = np.zeros((len(offsets), len(starts)), dtype=np.float32)

    print(f"[scan] frames={len(starts)} offsets={len(offsets)} fft={fft_size} hop={hop_size}")

    for frame_idx, start in enumerate(starts):
        frame = iq[start:start + fft_size]
        spec = np.fft.fftshift(np.fft.fft(frame * window))
        power = (np.abs(spec) ** 2).astype(np.float64) + 1e-20
        floor = float(np.median(power))

        for off_idx, mask in enumerate(masks):
            band_power = float(np.mean(power[mask]))
            scores[off_idx, frame_idx] = 10.0 * np.log10(band_power / floor)

    offset_strength = np.percentile(scores, 95, axis=1) - np.median(scores, axis=1)
    best_idx = int(np.argmax(offset_strength))
    best_offset = float(offsets[best_idx])
    best_score = scores[best_idx, :]

    top_order = np.argsort(offset_strength)[::-1]
    top_candidates = []
    for idx in top_order[:8]:
        idx = int(idx)
        top_candidates.append({
            "offset_hz": float(offsets[idx]),
            "strength_db": float(offset_strength[idx]),
            "score_p95_db": float(np.percentile(scores[idx, :], 95)),
            "score_median_db": float(np.median(scores[idx, :])),
        })

    return offsets, frame_times, scores, best_offset, best_score, top_candidates


def choose_active_window(
    frame_times: np.ndarray,
    score: np.ndarray,
    capture_duration: float,
    threshold_frac: float,
    pad_s: float,
):
    kernel = np.ones(5, dtype=np.float32) / 5.0
    smooth = np.convolve(score, kernel, mode="same")

    med = float(np.median(smooth))
    mx = float(np.max(smooth))
    spread = mx - med

    if spread < 1.0:
        return 0.0, capture_duration, med, mx

    threshold = med + threshold_frac * spread
    active = np.where(smooth > threshold)[0]

    if len(active) == 0:
        return 0.0, capture_duration, med, mx

    runs = contiguous_runs(active)
    best_run = None
    best_tuple = None
    for a, b in runs:
        length = b - a + 1
        avg = float(np.mean(smooth[a:b + 1]))
        key = (length, avg)
        if best_tuple is None or key > best_tuple:
            best_tuple = key
            best_run = (a, b)

    a, b = best_run
    start_s = max(0.0, float(frame_times[a]) - pad_s)
    stop_s = min(capture_duration, float(frame_times[b]) + pad_s)

    if stop_s - start_s < 1.0:
        stop_s = capture_duration

    return start_s, stop_s, med, mx


def complex_lowpass(x: np.ndarray, fs: int, cutoff_hz: float) -> np.ndarray:
    norm = cutoff_hz / (fs / 2.0)
    norm = min(max(norm, 1e-6), 0.95)
    sos = signal.butter(6, norm, btype="lowpass", output="sos")
    y_re = signal.sosfiltfilt(sos, np.real(x))
    y_im = signal.sosfiltfilt(sos, np.imag(x))
    return (y_re + 1j * y_im).astype(np.complex64)


def fm_demodulate_segment(
    iq_segment: np.ndarray,
    fs: int,
    offset_hz: float,
    deviation_hz: float,
    rf_lowpass_hz: float,
):
    n = np.arange(len(iq_segment), dtype=np.float64)
    mixed = iq_segment * np.exp(-1j * 2.0 * np.pi * offset_hz * n / fs)
    mixed_lp = complex_lowpass(mixed, fs, rf_lowpass_hz)

    dphi = np.angle(mixed_lp[1:] * np.conj(mixed_lp[:-1]))
    audio = dphi * fs / (2.0 * np.pi * deviation_hz)
    audio = np.concatenate([[audio[0]], audio]).astype(np.float32)
    audio = audio - float(np.mean(audio))

    return mixed_lp, audio


def make_plot(
    png_path: Path,
    label: str,
    active_iq: np.ndarray,
    mixed_lp: np.ndarray,
    audio_raw: np.ndarray,
    audio_clean: np.ndarray,
    audio_sr: int,
    fs: int,
    expected_offset: float,
    best_offset: float,
    active_start: float,
    active_stop: float,
    frame_times: np.ndarray,
    best_score: np.ndarray,
    score_med: float,
    score_max: float,
):
    f_full, db_full = spectrum_complex(active_iq, fs)
    f_mix, db_mix = spectrum_complex(mixed_lp, fs)
    f_raw, db_raw = spectrum_real(audio_raw, audio_sr)
    f_clean, db_clean = spectrum_real(audio_clean, audio_sr)

    n_raw = min(len(audio_raw), audio_sr)
    n_clean = min(len(audio_clean), audio_sr)
    t_raw = np.arange(n_raw) / audio_sr
    t_clean = np.arange(n_clean) / audio_sr

    fig, axes = plt.subplots(5, 1, figsize=(12, 14), constrained_layout=True)
    fig.suptitle(f"ORION Phase 5C Scanned/Cleaned Voice-FM Demod - {label}")

    axes[0].plot(frame_times, best_score)
    axes[0].axvspan(active_start, active_stop, alpha=0.2, label="chosen active window")
    axes[0].axhline(score_med, linestyle="--", label="score median")
    axes[0].axhline(score_max, linestyle=":", label="score max")
    axes[0].set_title(f"Time Scan Score at Chosen Offset {best_offset/1e3:+.2f} kHz")
    axes[0].set_xlabel("Capture time (s)")
    axes[0].set_ylabel("Band/floor score (dB)")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(f_full / 1e3, db_full)
    axes[1].axvline(expected_offset / 1e3, linestyle=":", label="expected")
    axes[1].axvline(best_offset / 1e3, linestyle="--", label="chosen")
    axes[1].set_title("Active-Window Raw RX IQ Spectrum")
    axes[1].set_xlabel("Frequency offset from 915 MHz (kHz)")
    axes[1].set_ylabel("dB relative")
    axes[1].set_xlim(-250, 500)
    axes[1].set_ylim(-100, 5)
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    axes[2].plot(f_mix / 1e3, db_mix)
    axes[2].set_title("Mixed and Low-Passed FM Region")
    axes[2].set_xlabel("Frequency after mixdown (kHz)")
    axes[2].set_ylabel("dB relative")
    axes[2].set_xlim(-60, 60)
    axes[2].set_ylim(-100, 5)
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(t_raw, audio_raw[:n_raw], label="raw active")
    axes[3].plot(t_clean, audio_clean[:n_clean], alpha=0.8, label="cleaned active")
    axes[3].set_title("Recovered Audio Waveform, First Second")
    axes[3].set_xlabel("Time (s)")
    axes[3].set_ylabel("Amplitude")
    axes[3].grid(True, alpha=0.3)
    axes[3].legend()

    axes[4].plot(f_raw, db_raw, label="raw active")
    axes[4].plot(f_clean, db_clean, alpha=0.85, label="cleaned active")
    axes[4].set_title("Recovered Audio Spectrum")
    axes[4].set_xlabel("Audio frequency (Hz)")
    axes[4].set_ylabel("dB relative")
    axes[4].set_xlim(0, 5000)
    axes[4].set_ylim(-100, 5)
    axes[4].grid(True, alpha=0.3)
    axes[4].legend()

    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    iq_path = Path(args.iq)

    if not iq_path.exists():
        print(f"[error] IQ capture not found: {iq_path}")
        sys.exit(1)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    label = safe_label(args.label)

    wav_raw_active = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}_raw_active.wav"
    wav_clean_active = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}_cleaned_active.wav"
    wav_full_clean = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}_full_cleaned.wav"
    json_path = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}.json"
    png_path = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}.png"

    print("=" * 72)
    print("ORION Phase 5C - Scanned/Cleaned Received Voice-FM Demodulation")
    print("=" * 72)
    print("Offline analysis only. No SDR. No RF.")
    print()
    print(f"IQ input         : {iq_path}")
    print(f"Rate             : {args.rate/1e6:.3f} Msps")
    print(f"Expected offset  : {args.expected_offset/1e3:+.1f} kHz")
    print(f"Offset scan      : +/- {args.offset_span/1e3:.1f} kHz, step {args.offset_step/1e3:.2f} kHz")
    print(f"Deviation        : {args.deviation/1e3:.1f} kHz")
    print(f"RF low-pass      : {args.rf_lowpass/1e3:.1f} kHz")
    print(f"Cleanup notches  : {args.notch_hz if args.notch_hz else 'none'}")

    iq = np.load(iq_path).astype(np.complex64).ravel()
    capture_duration = len(iq) / args.rate

    _, frame_times, _, best_offset, best_score, top_candidates = scan_offsets_and_time(
        iq=iq,
        fs=args.rate,
        expected_offset=args.expected_offset,
        offset_span=args.offset_span,
        offset_step=args.offset_step,
        analysis_band=args.analysis_band,
        fft_size=args.fft_size,
        hop_size=args.hop_size,
    )

    active_start, active_stop, score_med, score_max = choose_active_window(
        frame_times=frame_times,
        score=best_score,
        capture_duration=capture_duration,
        threshold_frac=args.active_threshold_frac,
        pad_s=args.active_pad,
    )

    if args.force_start is not None:
        active_start = max(0.0, float(args.force_start))
    if args.force_stop is not None:
        active_stop = min(capture_duration, float(args.force_stop))

    if active_stop <= active_start:
        active_start = 0.0
        active_stop = capture_duration

    start_idx = int(round(active_start * args.rate))
    stop_idx = int(round(active_stop * args.rate))
    active_iq = iq[start_idx:stop_idx]

    mixed_lp_active, audio_active_iq_rate = fm_demodulate_segment(
        iq_segment=active_iq,
        fs=args.rate,
        offset_hz=best_offset,
        deviation_hz=args.deviation,
        rf_lowpass_hz=args.rf_lowpass,
    )

    _, audio_full_iq_rate = fm_demodulate_segment(
        iq_segment=iq,
        fs=args.rate,
        offset_hz=best_offset,
        deviation_hz=args.deviation,
        rf_lowpass_hz=args.rf_lowpass,
    )

    audio_raw = resample_to(audio_active_iq_rate, args.rate, args.audio_rate)
    audio_raw = bandpass_audio(audio_raw, args.audio_rate, args.lowcut, args.highcut)
    audio_raw = normalize_audio(audio_raw)

    audio_clean = cleanup_audio(
        audio_raw,
        sr=args.audio_rate,
        trim_start_s=args.trim_active_start,
        notch_hz=args.notch_hz,
        notch_q=args.notch_q,
        clean_lowcut=args.clean_lowcut,
        clean_highcut=args.clean_highcut,
    )

    audio_full = resample_to(audio_full_iq_rate, args.rate, args.audio_rate)
    audio_full = bandpass_audio(audio_full, args.audio_rate, args.lowcut, args.highcut)
    audio_full = cleanup_audio(
        audio_full,
        sr=args.audio_rate,
        trim_start_s=0.0,
        notch_hz=args.notch_hz,
        notch_q=args.notch_q,
        clean_lowcut=args.clean_lowcut,
        clean_highcut=args.clean_highcut,
    )

    write_wav(wav_raw_active, args.audio_rate, audio_raw)
    write_wav(wav_clean_active, args.audio_rate, audio_clean)
    write_wav(wav_full_clean, args.audio_rate, audio_full)

    make_plot(
        png_path=png_path,
        label=label,
        active_iq=active_iq,
        mixed_lp=mixed_lp_active,
        audio_raw=audio_raw,
        audio_clean=audio_clean,
        audio_sr=args.audio_rate,
        fs=args.rate,
        expected_offset=args.expected_offset,
        best_offset=best_offset,
        active_start=active_start,
        active_stop=active_stop,
        frame_times=frame_times,
        best_score=best_score,
        score_med=score_med,
        score_max=score_max,
    )

    metadata = {
        "phase": "Phase 5C DEMOD",
        "script": "10_demod_voice_fm_capture.py",
        "mode": "time_frequency_scan_with_audio_cleanup",
        "label": label,
        "timestamp": timestamp,
        "iq_input": str(iq_path),
        "sample_rate_hz": args.rate,
        "capture_duration_s": capture_duration,
        "expected_offset_hz": args.expected_offset,
        "best_offset_hz": best_offset,
        "offset_span_hz": args.offset_span,
        "offset_step_hz": args.offset_step,
        "analysis_band_hz": args.analysis_band,
        "fm_deviation_hz": args.deviation,
        "rf_lowpass_hz": args.rf_lowpass,
        "audio_rate_hz": args.audio_rate,
        "speech_lowcut_hz": args.lowcut,
        "speech_highcut_hz": args.highcut,
        "active_start_s": active_start,
        "active_stop_s": active_stop,
        "active_duration_s": active_stop - active_start,
        "cleanup": {
            "trim_active_start_s": args.trim_active_start,
            "notch_hz": args.notch_hz,
            "notch_q": args.notch_q,
            "clean_lowcut_hz": args.clean_lowcut,
            "clean_highcut_hz": args.clean_highcut,
            "note": "Cleanup targets channel artifacts and broad speech band, not speaker-specific vocal EQ."
        },
        "top_offset_candidates": top_candidates,
        "raw_active_wav": str(wav_raw_active.relative_to(ROOT)),
        "cleaned_active_wav": str(wav_clean_active.relative_to(ROOT)),
        "full_cleaned_wav": str(wav_full_clean.relative_to(ROOT)),
        "plot_path": str(png_path.relative_to(ROOT)),
        "rf_status": "OFFLINE ANALYSIS ONLY",
    }
    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    append_testlog(
        "COMPLETE",
        str(png_path.relative_to(ROOT)),
        f"label={label} best_offset={best_offset/1e3:+.2f}kHz "
        f"active={active_start:.2f}-{active_stop:.2f}s "
        f"notches={args.notch_hz}",
    )

    print()
    print("[+] Raw active WAV:      " + str(wav_raw_active))
    print("[+] Cleaned active WAV:  " + str(wav_clean_active))
    print("[+] Full cleaned WAV:    " + str(wav_full_clean))
    print("[+] Metadata:            " + str(json_path))
    print("[+] Plot:                " + str(png_path))
    print()
    print(f"Chosen offset       : {best_offset/1e3:+.2f} kHz")
    print(f"Detected active     : {active_start:.2f} s to {active_stop:.2f} s")
    print(f"Cleaned trim start  : {args.trim_active_start:.2f} s")
    print()
    print("Top offset candidates:")
    for c in top_candidates[:5]:
        print(
            f"  {c['offset_hz']/1e3:+7.2f} kHz | "
            f"strength={c['strength_db']:.2f} dB | "
            f"p95={c['score_p95_db']:.2f} dB | "
            f"median={c['score_median_db']:.2f} dB"
        )
    print()
    print("Listen to the CLEANED active WAV first.")
    print("Done.")


if __name__ == "__main__":
    main()
