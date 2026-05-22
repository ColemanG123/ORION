#!/usr/bin/env python3
"""
06_offline_voice_fm_test.py — ORION Phase 5B: offline voice FM modulation/demodulation.

Goal:
  Prove the voice waveform path in software before involving any SDR hardware.

Input:
  WAV from Phase 5A.

Outputs:
  data/audio/fm_<label>_<timestamp>_conditioned.wav
  data/audio/fm_<label>_<timestamp>_recovered.wav
  data/audio/fm_<label>_<timestamp>.json
  data/audio/fm_<label>_<timestamp>.png
  optional: data/audio/fm_<label>_<timestamp>_iq.npy

No SDR. No RF. No transmission.
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
from scipy.io import wavfile
from scipy import signal

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
TEST_LOG = ROOT / "docs" / "test_logs" / "TEST_LOG.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION Phase 5B offline voice FM modulation/demodulation. No SDR, no RF.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", required=True, help="Input WAV file from Phase 5A.")
    p.add_argument("--label", default="voice_fm_offline", help="Label for outputs.")
    p.add_argument("--iq-rate", type=int, default=240_000, help="Simulated IQ sample rate in Hz.")
    p.add_argument("--deviation", type=float, default=5_000.0, help="FM peak deviation in Hz.")
    p.add_argument("--lowcut", type=float, default=100.0, help="Speech high-pass cutoff in Hz.")
    p.add_argument("--highcut", type=float, default=3_400.0, help="Speech low-pass cutoff in Hz.")
    p.add_argument("--audio-out-rate", type=int, default=44_100, help="Recovered WAV sample rate.")
    p.add_argument("--save-iq", action="store_true", help="Save simulated FM IQ as .npy.")
    return p.parse_args()


def read_wav_mono(path: Path) -> tuple[int, np.ndarray]:
    sr, data = wavfile.read(path)

    if data.ndim == 2:
        data = data.mean(axis=1)

    if np.issubdtype(data.dtype, np.integer):
        maxv = np.iinfo(data.dtype).max
        audio = data.astype(np.float32) / maxv
    else:
        audio = data.astype(np.float32)

    audio = np.nan_to_num(audio)
    audio = np.clip(audio, -1.0, 1.0)
    return int(sr), audio


def resample_to(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return x.astype(np.float32)

    ratio = Fraction(dst_rate, src_rate).limit_denominator(10_000)
    y = signal.resample_poly(x, ratio.numerator, ratio.denominator)
    return y.astype(np.float32)


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


def fm_modulate(message: np.ndarray, fs: int, deviation_hz: float) -> np.ndarray:
    message = np.clip(message.astype(np.float32), -1.0, 1.0)
    phase = np.cumsum(2.0 * np.pi * deviation_hz * message / fs)
    iq = np.exp(1j * phase).astype(np.complex64)
    return iq


def fm_demodulate(iq: np.ndarray, fs: int, deviation_hz: float) -> np.ndarray:
    # Instantaneous phase difference between adjacent complex samples.
    dphi = np.angle(iq[1:] * np.conj(iq[:-1]))
    recovered = dphi * fs / (2.0 * np.pi * deviation_hz)
    recovered = np.concatenate([[recovered[0]], recovered])
    recovered = recovered - np.mean(recovered)
    return recovered.astype(np.float32)


def write_wav_float(path: Path, sr: int, audio: np.ndarray) -> None:
    audio = np.nan_to_num(audio)
    audio = np.clip(audio, -1.0, 1.0)
    wavfile.write(path, sr, np.int16(audio * 32767))


def db_spectrum(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x)
    n = len(x)
    win = np.hanning(n)
    spec = np.fft.rfft(np.real(x) * win)
    freq = np.fft.rfftfreq(n, d=1.0 / fs)
    mag = np.abs(spec)
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    db -= np.max(db)
    return freq, db


def iq_spectrum(iq: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(iq)
    win = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(iq * win))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
    mag = np.abs(spec)
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    db -= np.max(db)
    return freq, db


def save_plot(
    png_path: Path,
    original: np.ndarray,
    original_sr: int,
    conditioned: np.ndarray,
    recovered: np.ndarray,
    out_sr: int,
    iq: np.ndarray,
    iq_rate: int,
    label: str,
) -> None:
    max_seconds = min(1.0, len(conditioned) / original_sr, len(recovered) / out_sr)

    n_cond = int(max_seconds * original_sr)
    n_rec = int(max_seconds * out_sr)

    t_cond = np.arange(n_cond) / original_sr
    t_rec = np.arange(n_rec) / out_sr

    f_orig, db_orig = db_spectrum(conditioned, original_sr)
    f_rec, db_rec = db_spectrum(recovered, out_sr)
    f_iq, db_iq = iq_spectrum(iq, iq_rate)

    fig, axes = plt.subplots(4, 1, figsize=(10, 12), constrained_layout=True)
    fig.suptitle(f"ORION Phase 5B Offline Voice FM — {label}")

    axes[0].plot(t_cond, conditioned[:n_cond], label="conditioned input")
    axes[0].plot(t_rec, recovered[:n_rec], alpha=0.75, label="demod recovered")
    axes[0].set_title("Time-Domain Audio Comparison, First Second")
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Amplitude")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(f_orig, db_orig, label="conditioned input")
    axes[1].plot(f_rec, db_rec, alpha=0.75, label="demod recovered")
    axes[1].set_title("Audio Spectrum Comparison")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Magnitude (dB relative)")
    axes[1].set_xlim(0, 8000)
    axes[1].set_ylim(-100, 5)
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(f_iq / 1000.0, db_iq)
    axes[2].set_title("Simulated FM IQ Spectrum")
    axes[2].set_xlabel("Frequency Offset (kHz)")
    axes[2].set_ylabel("Magnitude (dB relative)")
    axes[2].set_xlim(-30, 30)
    axes[2].set_ylim(-100, 5)
    axes[2].grid(True, alpha=0.3)

    err_len = min(len(conditioned), len(resample_to(recovered, out_sr, original_sr)))
    rec_at_orig = resample_to(recovered, out_sr, original_sr)[:err_len]
    cond_for_err = conditioned[:err_len]
    err = cond_for_err - rec_at_orig
    axes[3].plot(np.arange(min(len(err), original_sr)) / original_sr, err[:original_sr])
    axes[3].set_title("Recovery Error, First Second")
    axes[3].set_xlabel("Time (s)")
    axes[3].set_ylabel("Error")
    axes[3].grid(True, alpha=0.3)

    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5B | Offline voice FM modulation/demodulation | "
        f"06_offline_voice_fm_test.py | {status} | {evidence} | {notes} |"
    )
    existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"[error] Input WAV not found: {input_path}")
        sys.exit(1)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in args.label)

    prefix = AUDIO_DIR / f"fm_{safe_label}_{timestamp}"
    conditioned_wav = Path(str(prefix) + "_conditioned.wav")
    recovered_wav = Path(str(prefix) + "_recovered.wav")
    json_path = Path(str(prefix) + ".json")
    png_path = Path(str(prefix) + ".png")
    iq_path = Path(str(prefix) + "_iq.npy")

    print("=" * 72)
    print("ORION Phase 5B — Offline Voice FM Test")
    print("=" * 72)
    print("No SDR. No RF. No transmission.")
    print()
    print(f"Input WAV      : {input_path}")
    print(f"IQ rate        : {args.iq_rate} Hz")
    print(f"FM deviation   : {args.deviation:.1f} Hz")
    print(f"Speech band    : {args.lowcut:.1f} Hz to {args.highcut:.1f} Hz")

    sr, audio = read_wav_mono(input_path)
    conditioned = speech_condition(audio, sr, args.lowcut, args.highcut)
    conditioned_iq_rate = resample_to(conditioned, sr, args.iq_rate)

    iq = fm_modulate(conditioned_iq_rate, args.iq_rate, args.deviation)
    recovered_iq_rate = fm_demodulate(iq, args.iq_rate, args.deviation)
    recovered = resample_to(recovered_iq_rate, args.iq_rate, args.audio_out_rate)
    recovered = speech_condition(recovered, args.audio_out_rate, args.lowcut, args.highcut)

    write_wav_float(conditioned_wav, sr, conditioned)
    write_wav_float(recovered_wav, args.audio_out_rate, recovered)

    if args.save_iq:
        np.save(iq_path, iq)

    # Simple quality metric: correlation between conditioned input and recovered audio.
    rec_at_input_rate = resample_to(recovered, args.audio_out_rate, sr)
    n = min(len(conditioned), len(rec_at_input_rate))
    a = conditioned[:n]
    b = rec_at_input_rate[:n]
    corr = float(np.corrcoef(a, b)[0, 1]) if n > 10 and np.std(a) > 0 and np.std(b) > 0 else 0.0
    err_rms = float(np.sqrt(np.mean((a - b) ** 2))) if n else 0.0

    save_plot(
        png_path,
        audio,
        sr,
        conditioned,
        recovered,
        args.audio_out_rate,
        iq,
        args.iq_rate,
        safe_label,
    )

    metadata = {
        "phase": "Phase 5B",
        "script": "06_offline_voice_fm_test.py",
        "label": safe_label,
        "timestamp": timestamp,
        "input_wav": str(input_path),
        "input_sample_rate_hz": sr,
        "audio_out_rate_hz": args.audio_out_rate,
        "iq_rate_hz": args.iq_rate,
        "fm_deviation_hz": args.deviation,
        "speech_lowcut_hz": args.lowcut,
        "speech_highcut_hz": args.highcut,
        "conditioned_wav": str(conditioned_wav.relative_to(ROOT)),
        "recovered_wav": str(recovered_wav.relative_to(ROOT)),
        "plot_path": str(png_path.relative_to(ROOT)),
        "iq_path": str(iq_path.relative_to(ROOT)) if args.save_iq else None,
        "correlation_conditioned_vs_recovered": corr,
        "recovery_error_rms": err_rms,
        "rf_status": "NO SDR, NO RF, NO TRANSMISSION",
    }
    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    status = "PASS" if corr > 0.90 else "REVIEW"
    append_testlog(
        status,
        str(png_path.relative_to(ROOT)),
        f"label={safe_label} corr={corr:.4f} err_rms={err_rms:.5f} "
        f"deviation={args.deviation:.0f}Hz iq_rate={args.iq_rate}Hz",
    )

    print()
    print("[+] Conditioned WAV: " + str(conditioned_wav))
    print("[+] Recovered WAV:   " + str(recovered_wav))
    print("[+] Metadata:        " + str(json_path))
    print("[+] Plot:            " + str(png_path))
    if args.save_iq:
        print("[+] FM IQ:           " + str(iq_path))
    print()
    print(f"Correlation conditioned vs recovered : {corr:.4f}")
    print(f"Recovery error RMS                   : {err_rms:.5f}")
    print(f"Verdict                              : {status}")
    print()
    print("Listen to the recovered WAV. If it is clear, Phase 5B passes.")
    print("Done.")


if __name__ == "__main__":
    main()
