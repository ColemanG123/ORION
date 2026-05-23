#!/usr/bin/env python3
"""
12_analyze_latest_hifi_audio.py — ORION Phase 5C hi-fi recovered-audio diagnostic.

Purpose
-------
Analyze the latest recovered hi-fi WAV/JSON artifacts from scripts/10_demod_voice_fm_capture.py.

This avoids PowerShell heredoc issues. Run from E:\\ORION:

    python scripts\\12_analyze_latest_hifi_audio.py

Optional:

    python scripts\\12_analyze_latest_hifi_audio.py --label loop20_hifi_g25_tx32
    python scripts\\12_analyze_latest_hifi_audio.py --wav data\\audio\\some_file.wav

Outputs:
  - console summary
  - data/audio/diagnostics/hifi_audio_diagnostic_<timestamp>.json
  - data/audio/diagnostics/hifi_audio_diagnostic_<timestamp>.png
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy import signal


ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "data" / "audio"
DIAG = AUDIO / "diagnostics"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Analyze latest ORION Phase 5C hi-fi recovered audio.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--label", default="loop20_hifi_g25_tx32",
                   help="Label substring used to find latest WAV/JSON.")
    p.add_argument("--wav", default=None, help="Specific WAV path to analyze.")
    p.add_argument("--json", default=None, help="Specific metadata JSON path to print.")
    p.add_argument("--skip-start", type=float, default=0.5,
                   help="Seconds skipped before spectral analysis.")
    return p.parse_args()


def newest(pattern: str) -> Path | None:
    files = sorted(AUDIO.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def read_wav_float(path: Path) -> tuple[int, np.ndarray]:
    sr, x = wavfile.read(path)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if np.issubdtype(x.dtype, np.integer):
        x = x.astype(np.float32) / np.iinfo(x.dtype).max
    else:
        x = x.astype(np.float32)
    return int(sr), x.astype(np.float32)


def integrate_power(y: np.ndarray, x: np.ndarray) -> float:
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    return float(np.trapz(y, x))


def band_power(f: np.ndarray, P: np.ndarray, lo: float, hi: float) -> float:
    mask = (f >= lo) & (f < hi)
    if not np.any(mask):
        return 0.0
    return integrate_power(P[mask], f[mask])


def db(x: float) -> float:
    return float(10.0 * np.log10(max(float(x), 1e-30)))


def analyze_audio(wav_path: Path, skip_start: float) -> dict:
    sr, x = read_wav_float(wav_path)
    duration = len(x) / sr

    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
    crest = peak / rms if rms > 0 else 0.0
    clip98 = float(np.mean(np.abs(x) > 0.98))
    clip90 = float(np.mean(np.abs(x) > 0.90))
    clip80 = float(np.mean(np.abs(x) > 0.80))

    x_eval = x[int(skip_start * sr):] if len(x) > int((skip_start + 1.0) * sr) else x
    x_eval = x_eval - float(np.mean(x_eval))

    nperseg = min(8192, len(x_eval))
    f, P = signal.welch(x_eval, fs=sr, nperseg=nperseg)

    bands = {
        "speech_60_8000": band_power(f, P, 60, 8000),
        "speech_100_3400": band_power(f, P, 100, 3400),
        "presence_2000_5000": band_power(f, P, 2000, 5000),
        "hiss_8000_14000": band_power(f, P, 8000, 14000),
        "ring_1500_4000": band_power(f, P, 1500, 4000),
        "low_cloud_60_700": band_power(f, P, 60, 700),
    }

    band = (f >= 60) & (f <= 12000)
    f_band = f[band]
    P_band = P[band]
    peaks, _ = signal.find_peaks(P_band, distance=20)

    peak_list = []
    if len(peaks):
        order = np.argsort(P_band[peaks])[::-1][:20]
        mx = float(np.max(P_band))
        for idx in order:
            pk = peaks[idx]
            peak_list.append({
                "freq_hz": float(f_band[pk]),
                "rel_power": float(P_band[pk] / mx),
            })

    return {
        "wav_path": str(wav_path),
        "sample_rate_hz": sr,
        "duration_s": duration,
        "peak": peak,
        "rms": rms,
        "crest_factor": crest,
        "clipping_fraction_0p98": clip98,
        "clipping_fraction_0p90": clip90,
        "clipping_fraction_0p80": clip80,
        "skip_start_s": skip_start,
        "band_power_db": {k: db(v) for k, v in bands.items()},
        "speech_to_hiss_db": db(bands["speech_60_8000"]) - db(bands["hiss_8000_14000"]),
        "presence_to_speech_db": db(bands["presence_2000_5000"]) - db(bands["speech_60_8000"]),
        "ring_to_speech_db": db(bands["ring_1500_4000"]) - db(bands["speech_60_8000"]),
        "low_cloud_to_speech_db": db(bands["low_cloud_60_700"]) - db(bands["speech_60_8000"]),
        "dominant_peaks": peak_list,
    }


def make_plot(wav_path: Path, metrics: dict, out_png: Path, skip_start: float) -> None:
    sr, x = read_wav_float(wav_path)
    x_eval = x[int(skip_start * sr):] if len(x) > int((skip_start + 1.0) * sr) else x
    x_eval = x_eval - float(np.mean(x_eval))

    n = min(len(x), sr * 2)
    t = np.arange(n) / sr

    f, P = signal.welch(x_eval, fs=sr, nperseg=min(8192, len(x_eval)))
    Pdb = 10 * np.log10(np.maximum(P, 1e-30))
    Pdb -= np.max(Pdb)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    fig.suptitle("ORION Phase 5C Hi-Fi Audio Diagnostic")

    axes[0].plot(t, x[:n])
    axes[0].set_title("Recovered audio waveform, first 2 seconds")
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(f, Pdb)
    axes[1].set_title("Recovered audio spectrum")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Relative PSD (dB)")
    axes[1].set_xlim(0, 12000)
    axes[1].set_ylim(-100, 5)
    axes[1].grid(True, alpha=0.3)

    for p in metrics.get("dominant_peaks", [])[:8]:
        hz = p["freq_hz"]
        if 0 <= hz <= 12000:
            axes[1].axvline(hz, linestyle=":", alpha=0.35)

    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    DIAG.mkdir(parents=True, exist_ok=True)

    if args.wav:
        wav_path = Path(args.wav)
        if not wav_path.is_absolute():
            wav_path = ROOT / wav_path
    else:
        wav_path = newest(f"rx_voice_fm_{args.label}_*_limited_cleaned_active.wav")

    if wav_path is None or not wav_path.exists():
        raise FileNotFoundError(f"No WAV found for label {args.label!r}")

    if args.json:
        json_path = Path(args.json)
        if not json_path.is_absolute():
            json_path = ROOT / json_path
    else:
        json_path = newest(f"rx_voice_fm_{args.label}_*.json")

    metadata = {}
    if json_path and json_path.exists():
        metadata = json.loads(json_path.read_text(encoding="utf-8"))

    metrics = analyze_audio(wav_path, skip_start=args.skip_start)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = DIAG / f"hifi_audio_diagnostic_{timestamp}.json"
    out_png = DIAG / f"hifi_audio_diagnostic_{timestamp}.png"

    report = {
        "metrics": metrics,
        "metadata": metadata,
        "interpretation_hints": {
            "high_clipping_fraction": "If clipping fractions are nonzero or peak/rms is suspicious, reduce TX gain/amplitude or adjust deviation.",
            "dominant_high_peak": "A stable narrow peak in the 1.5–8 kHz range is a notch-filter candidate.",
            "crackle_without_clipping": "If clipping is low but crackle remains, try deviation sweep and/or lower TX gain/RX gain.",
        },
    }

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    make_plot(wav_path, metrics, out_png, args.skip_start)

    print("=" * 72)
    print("ORION Phase 5C Hi-Fi Audio Diagnostic")
    print("=" * 72)
    print(f"WAV      : {wav_path}")
    if json_path and json_path.exists():
        print(f"Metadata : {json_path}")
    print()
    if metadata:
        print("Demod metadata:")
        for key in [
            "best_offset_hz",
            "channel_snr_db_active_vs_baseline",
            "active_start_s",
            "active_stop_s",
            "fm_deviation_hz",
            "channel_cutoff_hz",
            "demod_rate_hz",
            "deemphasis_us",
        ]:
            if key in metadata:
                print(f"  {key}: {metadata[key]}")
    print()
    print("Audio metrics:")
    for key in [
        "sample_rate_hz",
        "duration_s",
        "peak",
        "rms",
        "crest_factor",
        "clipping_fraction_0p98",
        "clipping_fraction_0p90",
        "clipping_fraction_0p80",
        "speech_to_hiss_db",
        "presence_to_speech_db",
        "ring_to_speech_db",
        "low_cloud_to_speech_db",
    ]:
        print(f"  {key}: {metrics.get(key)}")
    print()
    print("Dominant peaks:")
    for p in metrics["dominant_peaks"][:15]:
        print(f"  {p['freq_hz']:8.1f} Hz   rel_power={p['rel_power']:.3f}")
    print()
    print(f"Diagnostic JSON: {out_json}")
    print(f"Diagnostic PNG : {out_png}")


if __name__ == "__main__":
    main()
