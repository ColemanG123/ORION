#!/usr/bin/env python3
"""
10_demod_voice_fm_capture.py - ORION Phase 5C NBFM-style voice-FM receiver.

Purpose:
  Demodulate received voice-FM IQ captured by e9e after transmission from 149.

Receiver chain:
  scan time/frequency -> mix to offset -> channel filter -> decimate ->
  limiter -> quadrature FM demod -> optional de-emphasis -> speech cleanup.

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
        description="ORION Phase 5C NBFM-style scanned receiver.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--iq", required=True)
    p.add_argument("--label", default="e9e_149_nbfm_rx")

    p.add_argument("--rate", type=int, default=1_000_000)
    p.add_argument("--expected-offset", "--offset", dest="expected_offset", type=float, default=100_000.0)
    p.add_argument("--offset-span", type=float, default=12_000.0)
    p.add_argument("--offset-step", type=float, default=250.0)

    p.add_argument("--deviation", type=float, default=5_000.0)
    p.add_argument("--channel-cutoff", type=float, default=12_000.0)
    p.add_argument("--analysis-band", type=float, default=9_000.0)
    p.add_argument("--demod-rate", type=int, default=100_000)

    p.add_argument("--audio-rate", type=int, default=44_100)
    p.add_argument("--lowcut", type=float, default=100.0)
    p.add_argument("--highcut", type=float, default=3_400.0)

    p.add_argument("--fft-size", type=int, default=65_536)
    p.add_argument("--hop-size", type=int, default=32_768)
    p.add_argument("--active-threshold-frac", type=float, default=0.35)
    p.add_argument("--active-pad", type=float, default=0.35)
    p.add_argument("--force-start", type=float, default=None)
    p.add_argument("--force-stop", type=float, default=None)

    p.add_argument("--no-limiter", action="store_true", help="Disable limiter output generation.")
    p.add_argument("--deemphasis-us", type=float, default=0.0, help="0 disables de-emphasis.")
    p.add_argument("--trim-active-start", type=float, default=0.8)
    p.add_argument("--notch-hz", type=float, action="append", default=[])
    p.add_argument("--notch-q", type=float, default=35.0)
    p.add_argument("--clean-lowcut", type=float, default=80.0)
    p.add_argument("--clean-highcut", type=float, default=3_400.0)

    return p.parse_args()


def safe_label(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in s)


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5C DEMOD | NBFM-style scanned receiver | "
        f"10_demod_voice_fm_capture.py | {status} | {evidence} | {notes} |"
    )
    existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


def normalize_audio(x: np.ndarray, target_peak: float = 0.90) -> np.ndarray:
    x = np.nan_to_num(np.asarray(x, dtype=np.float32))
    x = x - float(np.mean(x))
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0:
        x = target_peak * x / peak
    return np.clip(x, -1.0, 1.0).astype(np.float32)


def resample_to(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return x.astype(np.float32)
    ratio = Fraction(dst_rate, src_rate).limit_denominator(10_000)
    return signal.resample_poly(x, ratio.numerator, ratio.denominator).astype(np.float32)


def write_wav(path: Path, sr: int, audio: np.ndarray) -> None:
    y = normalize_audio(audio)
    wavfile.write(path, sr, np.int16(y * 32767))


def bandpass_audio(x: np.ndarray, sr: int, lowcut: float, highcut: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    x = x - float(np.mean(x))
    nyq = sr / 2.0
    low = max(1.0, lowcut) / nyq
    high = min(highcut, 0.95 * nyq) / nyq
    if low >= high:
        return x
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

    hp = max(1.0, clean_lowcut) / (sr / 2.0)
    if 0 < hp < 0.95:
        sos = signal.butter(2, hp, btype="highpass", output="sos")
        x = signal.sosfiltfilt(sos, x).astype(np.float32)

    for hz in notch_hz:
        if 0 < hz < sr / 2:
            b, a = signal.iirnotch(w0=hz, Q=notch_q, fs=sr)
            x = signal.filtfilt(b, a, x).astype(np.float32)

    lp = min(clean_highcut, 0.95 * sr / 2.0) / (sr / 2.0)
    if 0 < lp < 0.95:
        sos = signal.butter(4, lp, btype="lowpass", output="sos")
        x = signal.sosfiltfilt(sos, x).astype(np.float32)

    return normalize_audio(x)


def deemphasis(x: np.ndarray, sr: int, tau_us: float) -> np.ndarray:
    if tau_us <= 0:
        return x.astype(np.float32)

    tau = tau_us * 1e-6
    dt_s = 1.0 / sr
    alpha = dt_s / (tau + dt_s)

    y = np.empty_like(x, dtype=np.float32)
    y[0] = x[0]
    for n in range(1, len(x)):
        y[n] = y[n - 1] + alpha * (x[n] - y[n - 1])
    return y.astype(np.float32)


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
    offsets = np.arange(
        expected_offset - offset_span,
        expected_offset + offset_span + 0.1 * offset_step,
        offset_step,
        dtype=np.float64,
    )
    freqs = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1.0 / fs))
    masks = [np.abs(freqs - off) <= analysis_band for off in offsets]

    starts = np.arange(0, len(iq) - fft_size + 1, hop_size, dtype=np.int64)
    frame_times = (starts + fft_size / 2.0) / fs
    scores = np.zeros((len(offsets), len(starts)), dtype=np.float32)
    win = np.hanning(fft_size).astype(np.float32)

    print(f"[scan] frames={len(starts)} offsets={len(offsets)}")

    for frame_idx, start in enumerate(starts):
        frame = iq[start:start + fft_size]
        spec = np.fft.fftshift(np.fft.fft(frame * win))
        power = np.abs(spec) ** 2 + 1e-20
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

    return frame_times, best_offset, best_score, top_candidates


def choose_active_window(
    frame_times: np.ndarray,
    score: np.ndarray,
    capture_duration: float,
    threshold_frac: float,
    pad_s: float,
):
    smooth = np.convolve(score, np.ones(5) / 5.0, mode="same")
    med = float(np.median(smooth))
    mx = float(np.max(smooth))

    if mx - med < 1.0:
        return 0.0, capture_duration, med, mx

    threshold = med + threshold_frac * (mx - med)
    active = np.where(smooth > threshold)[0]
    if len(active) == 0:
        return 0.0, capture_duration, med, mx

    runs = contiguous_runs(active)
    best = max(runs, key=lambda r: (r[1] - r[0] + 1, float(np.mean(smooth[r[0]:r[1] + 1]))))
    start_s = max(0.0, float(frame_times[best[0]]) - pad_s)
    stop_s = min(capture_duration, float(frame_times[best[1]]) + pad_s)

    if stop_s - start_s < 1.0:
        stop_s = capture_duration

    return start_s, stop_s, med, mx


def mix_down(iq: np.ndarray, fs: int, offset_hz: float) -> np.ndarray:
    n = np.arange(len(iq), dtype=np.float64)
    return (iq * np.exp(-1j * 2.0 * np.pi * offset_hz * n / fs)).astype(np.complex64)


def channel_filter_and_decimate(
    z: np.ndarray,
    fs: int,
    cutoff_hz: float,
    demod_rate: int,
):
    decim = max(1, int(round(fs / demod_rate)))
    actual_rate = int(round(fs / decim))

    cutoff_norm = min(cutoff_hz / (fs / 2.0), 0.45)
    taps = signal.firwin(numtaps=257, cutoff=cutoff_norm)
    z_filt = signal.lfilter(taps, [1.0], z).astype(np.complex64)

    if decim > 1:
        z_dec = signal.resample_poly(z_filt, up=1, down=decim).astype(np.complex64)
    else:
        z_dec = z_filt

    return z_filt, z_dec, actual_rate, decim


def limit_complex(z: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    mag = np.abs(z)
    return (z / np.maximum(mag, eps)).astype(np.complex64)


def quadrature_demod(z: np.ndarray, fs: int, deviation_hz: float) -> np.ndarray:
    if len(z) < 2:
        return np.zeros(0, dtype=np.float32)
    dphi = np.angle(z[1:] * np.conj(z[:-1]))
    audio = dphi * fs / (2.0 * np.pi * deviation_hz)
    audio = np.concatenate([[audio[0]], audio]).astype(np.float32)
    audio = audio - float(np.mean(audio))
    return audio


def audio_pipeline(
    demod: np.ndarray,
    demod_rate: int,
    audio_rate: int,
    lowcut: float,
    highcut: float,
    deemphasis_us: float,
) -> np.ndarray:
    x = deemphasis(demod, demod_rate, deemphasis_us)
    x = resample_to(x, demod_rate, audio_rate)
    x = bandpass_audio(x, audio_rate, lowcut, highcut)
    return normalize_audio(x)


def power_db(x: np.ndarray) -> float:
    return 10.0 * np.log10(max(float(np.mean(np.abs(x) ** 2)), 1e-30))


def compute_channel_snr(iq: np.ndarray, fs: int, best_offset: float, active_start: float, active_stop: float, cutoff_hz: float):
    n0 = int(active_start * fs)
    n1 = int(active_stop * fs)

    active = iq[n0:n1]
    baseline = iq[:max(0, n0 - int(0.5 * fs))]
    if len(baseline) < fs // 4:
        baseline = iq[:max(1, min(len(iq), fs))]

    a_mix = mix_down(active, fs, best_offset)
    b_mix = mix_down(baseline, fs, best_offset)
    a_filt, _, _, _ = channel_filter_and_decimate(a_mix, fs, cutoff_hz, fs)
    b_filt, _, _, _ = channel_filter_and_decimate(b_mix, fs, cutoff_hz, fs)

    return power_db(a_filt) - power_db(b_filt)


def make_plot(
    png_path: Path,
    label: str,
    active_iq: np.ndarray,
    fs: int,
    mixed_filtered: np.ndarray,
    demod_rate: int,
    raw_audio: np.ndarray,
    limited_audio: np.ndarray,
    cleaned_audio: np.ndarray,
    audio_rate: int,
    expected_offset: float,
    best_offset: float,
    active_start: float,
    active_stop: float,
    frame_times: np.ndarray,
    best_score: np.ndarray,
):
    f_active, db_active = spectrum_complex(active_iq, fs)
    f_chan, db_chan = spectrum_complex(mixed_filtered, demod_rate)
    f_raw, db_raw = spectrum_real(raw_audio, audio_rate)
    f_lim, db_lim = spectrum_real(limited_audio, audio_rate)
    f_clean, db_clean = spectrum_real(cleaned_audio, audio_rate)

    fig, axes = plt.subplots(5, 1, figsize=(12, 15), constrained_layout=True)
    fig.suptitle(f"ORION Phase 5C NBFM Receiver - {label}")

    axes[0].plot(frame_times, best_score)
    axes[0].axvspan(active_start, active_stop, alpha=0.2)
    axes[0].set_title(f"Scan Score at Chosen Offset {best_offset/1e3:+.2f} kHz")
    axes[0].set_xlabel("Capture time (s)")
    axes[0].set_ylabel("Score (dB)")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(f_active / 1e3, db_active)
    axes[1].axvline(expected_offset / 1e3, linestyle=":", label="expected")
    axes[1].axvline(best_offset / 1e3, linestyle="--", label="chosen")
    axes[1].set_title("Active-Window RX Spectrum")
    axes[1].set_xlabel("Frequency offset from 915 MHz (kHz)")
    axes[1].set_ylabel("dB relative")
    axes[1].set_xlim(-250, 500)
    axes[1].set_ylim(-100, 5)
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(f_chan / 1e3, db_chan)
    axes[2].set_title("Channelized Baseband Spectrum")
    axes[2].set_xlabel("Frequency after mixdown/filter/decim (kHz)")
    axes[2].set_ylabel("dB relative")
    axes[2].set_xlim(-40, 40)
    axes[2].set_ylim(-100, 5)
    axes[2].grid(True, alpha=0.3)

    n = min(len(raw_audio), len(limited_audio), len(cleaned_audio), audio_rate)
    t = np.arange(n) / audio_rate
    axes[3].plot(t, raw_audio[:n], label="raw")
    axes[3].plot(t, limited_audio[:n], alpha=0.75, label="limited")
    axes[3].plot(t, cleaned_audio[:n], alpha=0.75, label="limited_cleaned")
    axes[3].set_title("Recovered Audio, First Second")
    axes[3].set_xlabel("Time (s)")
    axes[3].set_ylabel("Amplitude")
    axes[3].legend()
    axes[3].grid(True, alpha=0.3)

    axes[4].plot(f_raw, db_raw, label="raw")
    axes[4].plot(f_lim, db_lim, label="limited")
    axes[4].plot(f_clean, db_clean, label="limited_cleaned")
    axes[4].set_title("Recovered Audio Spectrum")
    axes[4].set_xlabel("Audio frequency (Hz)")
    axes[4].set_ylabel("dB relative")
    axes[4].set_xlim(0, 5000)
    axes[4].set_ylim(-100, 5)
    axes[4].legend()
    axes[4].grid(True, alpha=0.3)

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

    raw_wav = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}_raw_active.wav"
    limited_wav = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}_limited_active.wav"
    cleaned_wav = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}_limited_cleaned_active.wav"
    json_path = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}.json"
    png_path = AUDIO_DIR / f"rx_voice_fm_{label}_{timestamp}.png"

    print("=" * 72)
    print("ORION Phase 5C - NBFM-Style Received Voice Demodulation")
    print("=" * 72)
    print("Offline analysis only. No SDR. No RF.")
    print()
    print(f"IQ input        : {iq_path}")
    print(f"Rate            : {args.rate/1e6:.3f} Msps")
    print(f"Expected offset : {args.expected_offset/1e3:+.1f} kHz")
    print(f"Offset scan     : +/- {args.offset_span/1e3:.1f} kHz, step {args.offset_step:.0f} Hz")
    print(f"Channel cutoff  : {args.channel_cutoff/1e3:.1f} kHz")
    print(f"Demod rate      : {args.demod_rate/1e3:.1f} ksps")
    print(f"Limiter         : {'off' if args.no_limiter else 'on'}")
    print(f"De-emphasis     : {args.deemphasis_us:.1f} us")

    iq = np.load(iq_path).astype(np.complex64).ravel()
    duration = len(iq) / args.rate

    frame_times, best_offset, best_score, top_candidates = scan_offsets_and_time(
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
        frame_times,
        best_score,
        capture_duration=duration,
        threshold_frac=args.active_threshold_frac,
        pad_s=args.active_pad,
    )

    if args.force_start is not None:
        active_start = max(0.0, args.force_start)
    if args.force_stop is not None:
        active_stop = min(duration, args.force_stop)

    start_idx = int(round(active_start * args.rate))
    stop_idx = int(round(active_stop * args.rate))
    active_iq = iq[start_idx:stop_idx]

    mixed = mix_down(active_iq, args.rate, best_offset)
    mixed_filt, mixed_decim, actual_demod_rate, decim = channel_filter_and_decimate(
        mixed,
        fs=args.rate,
        cutoff_hz=args.channel_cutoff,
        demod_rate=args.demod_rate,
    )

    raw_demod = quadrature_demod(mixed_decim, actual_demod_rate, args.deviation)
    raw_audio = audio_pipeline(
        raw_demod,
        actual_demod_rate,
        args.audio_rate,
        args.lowcut,
        args.highcut,
        args.deemphasis_us,
    )

    limited_decim = limit_complex(mixed_decim)
    limited_demod = quadrature_demod(limited_decim, actual_demod_rate, args.deviation)
    limited_audio = audio_pipeline(
        limited_demod,
        actual_demod_rate,
        args.audio_rate,
        args.lowcut,
        args.highcut,
        args.deemphasis_us,
    )

    cleaned_audio = cleanup_audio(
        limited_audio,
        sr=args.audio_rate,
        trim_start_s=args.trim_active_start,
        notch_hz=args.notch_hz,
        notch_q=args.notch_q,
        clean_lowcut=args.clean_lowcut,
        clean_highcut=args.clean_highcut,
    )

    write_wav(raw_wav, args.audio_rate, raw_audio)
    write_wav(limited_wav, args.audio_rate, limited_audio)
    write_wav(cleaned_wav, args.audio_rate, cleaned_audio)

    channel_snr_db = compute_channel_snr(
        iq=iq,
        fs=args.rate,
        best_offset=best_offset,
        active_start=active_start,
        active_stop=active_stop,
        cutoff_hz=args.channel_cutoff,
    )

    make_plot(
        png_path=png_path,
        label=label,
        active_iq=active_iq,
        fs=args.rate,
        mixed_filtered=mixed_decim,
        demod_rate=actual_demod_rate,
        raw_audio=raw_audio,
        limited_audio=limited_audio,
        cleaned_audio=cleaned_audio,
        audio_rate=args.audio_rate,
        expected_offset=args.expected_offset,
        best_offset=best_offset,
        active_start=active_start,
        active_stop=active_stop,
        frame_times=frame_times,
        best_score=best_score,
    )

    metadata = {
        "phase": "Phase 5C DEMOD",
        "script": "10_demod_voice_fm_capture.py",
        "mode": "nbfm_style_receiver",
        "label": label,
        "timestamp": timestamp,
        "iq_input": str(iq_path),
        "sample_rate_hz": args.rate,
        "capture_duration_s": duration,
        "expected_offset_hz": args.expected_offset,
        "best_offset_hz": best_offset,
        "offset_span_hz": args.offset_span,
        "offset_step_hz": args.offset_step,
        "analysis_band_hz": args.analysis_band,
        "active_start_s": active_start,
        "active_stop_s": active_stop,
        "active_duration_s": active_stop - active_start,
        "fm_deviation_hz": args.deviation,
        "channel_cutoff_hz": args.channel_cutoff,
        "demod_rate_hz": actual_demod_rate,
        "decimation_factor": decim,
        "limiter_enabled": not args.no_limiter,
        "deemphasis_us": args.deemphasis_us,
        "channel_snr_db_active_vs_baseline": channel_snr_db,
        "cleanup": {
            "trim_active_start_s": args.trim_active_start,
            "notch_hz": args.notch_hz,
            "notch_q": args.notch_q,
            "clean_lowcut_hz": args.clean_lowcut,
            "clean_highcut_hz": args.clean_highcut,
            "note": "Cleanup targets channel artifacts and broad speech band, not speaker-specific vocal EQ."
        },
        "top_offset_candidates": top_candidates,
        "raw_active_wav": str(raw_wav.relative_to(ROOT)),
        "limited_active_wav": str(limited_wav.relative_to(ROOT)),
        "limited_cleaned_active_wav": str(cleaned_wav.relative_to(ROOT)),
        "plot_path": str(png_path.relative_to(ROOT)),
        "rf_status": "OFFLINE ANALYSIS ONLY",
    }

    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    append_testlog(
        "COMPLETE",
        str(png_path.relative_to(ROOT)),
        f"label={label} best_offset={best_offset/1e3:+.2f}kHz "
        f"snr={channel_snr_db:.2f}dB active={active_start:.2f}-{active_stop:.2f}s",
    )

    print()
    print("[+] Raw active WAV:             " + str(raw_wav))
    print("[+] Limited active WAV:         " + str(limited_wav))
    print("[+] Limited cleaned active WAV: " + str(cleaned_wav))
    print("[+] Metadata:                   " + str(json_path))
    print("[+] Plot:                       " + str(png_path))
    print()
    print(f"Chosen offset       : {best_offset/1e3:+.2f} kHz")
    print(f"Detected active     : {active_start:.2f} s to {active_stop:.2f} s")
    print(f"Channel SNR estimate: {channel_snr_db:.2f} dB")
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
    print("Listen to LIMITED CLEANED active first, then LIMITED active.")
    print("Done.")


if __name__ == "__main__":
    main()
