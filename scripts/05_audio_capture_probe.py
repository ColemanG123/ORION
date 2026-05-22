#!/usr/bin/env python3
"""
05_audio_capture_probe.py — ORION Phase 5A: Scarlett / microphone audio capture probe.

Goal:
  Prove Windows -> audio interface -> Python works before any SDR or RF voice work.

Outputs per run:
  data/audio/audio_<label>_<timestamp>.wav
  data/audio/audio_<label>_<timestamp>.json
  data/audio/audio_<label>_<timestamp>.png
  docs/test_logs/TEST_LOG.md row

No SDR. No RF. No transmission.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
TEST_LOG = ROOT / "docs" / "test_logs" / "TEST_LOG.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION Phase 5A audio capture probe. No SDR, no RF.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--list-devices", action="store_true",
                   help="List input audio devices and exit.")
    p.add_argument("--device", default=None,
                   help="Input device index or name substring, e.g. 3 or Scarlett.")
    p.add_argument("--label", default="audio_probe",
                   help="Short label for output filenames and TEST_LOG.")
    p.add_argument("--duration", type=float, default=5.0,
                   help="Capture duration in seconds.")
    p.add_argument("--samplerate", type=int, default=48_000,
                   help="Audio sample rate in Hz.")
    p.add_argument("--channels", type=int, default=1,
                   help="Number of input channels to record.")
    return p.parse_args()


def require_deps():
    missing = []
    try:
        import numpy as np  # noqa
    except Exception:
        missing.append("numpy")
    try:
        import sounddevice as sd  # noqa
    except Exception:
        missing.append("sounddevice")
    try:
        import matplotlib.pyplot as plt  # noqa
    except Exception:
        missing.append("matplotlib")
    try:
        from scipy.io import wavfile  # noqa
    except Exception:
        missing.append("scipy")

    if missing:
        print("[error] Missing Python package(s): " + ", ".join(missing))
        print("Run:")
        print("  python -m pip install -r requirements.txt")
        sys.exit(1)

    import numpy as np
    import sounddevice as sd
    import matplotlib.pyplot as plt
    from scipy.io import wavfile
    return np, sd, plt, wavfile


def list_input_devices(sd) -> None:
    print()
    print("=" * 72)
    print("ORION Phase 5A — Input Audio Devices")
    print("=" * 72)
    devices = sd.query_devices()
    default_in = sd.default.device[0]

    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            star = "  <-- default input" if idx == default_in else ""
            print(
                f"[{idx:2d}] {dev['name']}"
                f" | inputs={dev['max_input_channels']}"
                f" | default_sr={int(dev['default_samplerate'])} Hz"
                f"{star}"
            )
    print()


def resolve_device(sd, device_spec: str | None):
    if device_spec is None:
        idx = sd.default.device[0]
        if idx is None or idx < 0:
            raise RuntimeError("No default input device is configured.")
        name = sd.query_devices(idx)["name"]
        return idx, name

    spec = str(device_spec).strip()

    if spec.isdigit():
        idx = int(spec)
        dev = sd.query_devices(idx)
        if dev["max_input_channels"] <= 0:
            raise RuntimeError(f"Device {idx} exists but has no input channels.")
        return idx, dev["name"]

    matches = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and spec.lower() in dev["name"].lower():
            matches.append((idx, dev["name"]))

    if not matches:
        raise RuntimeError(f"No input device matched substring: {spec!r}")
    if len(matches) > 1:
        print("[error] Device substring matched multiple devices:")
        for idx, name in matches:
            print(f"  [{idx}] {name}")
        raise RuntimeError("Use the exact device index instead.")

    return matches[0]


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5A | Audio capture probe | "
        f"05_audio_capture_probe.py | {status} | {evidence} | {notes} |"
    )
    try:
        existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
        TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"[warn] Could not update TEST_LOG.md: {exc}")


def save_plot(np, plt, audio, samplerate: int, png_path: Path, title: str) -> None:
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = len(mono)
    t = np.arange(n) / samplerate

    # Spectrum, normalized to the strongest audio-frequency bin.
    window = np.hanning(n)
    spec = np.fft.rfft(mono * window)
    freqs = np.fft.rfftfreq(n, d=1.0 / samplerate)
    mag = np.abs(spec)
    mag_db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    mag_db = mag_db - np.max(mag_db)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    fig.suptitle(title)

    axes[0].plot(t, mono)
    axes[0].set_title("Captured Audio Waveform")
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(freqs, mag_db)
    axes[1].set_title("Audio Spectrum, Relative to Strongest Bin")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Magnitude (dB relative)")
    axes[1].set_xlim(0, min(10_000, samplerate / 2))
    axes[1].set_ylim(-100, 5)
    axes[1].grid(True, alpha=0.3)

    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    np, sd, plt, wavfile = require_deps()

    if args.list_devices:
        list_input_devices(sd)
        return

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 72)
    print("ORION Phase 5A — Audio Capture Probe")
    print("=" * 72)
    print("No SDR. No RF. No transmission.")
    print()

    try:
        device_idx, device_name = resolve_device(sd, args.device)
    except Exception as exc:
        print(f"[error] {exc}")
        print()
        print("Run this to inspect available inputs:")
        print("  python scripts\\05_audio_capture_probe.py --list-devices")
        sys.exit(1)

    frames = int(round(args.duration * args.samplerate))
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in args.label)

    wav_path = AUDIO_DIR / f"audio_{safe_label}_{timestamp}.wav"
    json_path = AUDIO_DIR / f"audio_{safe_label}_{timestamp}.json"
    png_path = AUDIO_DIR / f"audio_{safe_label}_{timestamp}.png"

    print(f"Input device : [{device_idx}] {device_name}")
    print(f"Sample rate  : {args.samplerate} Hz")
    print(f"Channels     : {args.channels}")
    print(f"Duration     : {args.duration:.2f} s")
    print()
    print("Speak into the mic after the countdown.")
    for k in range(3, 0, -1):
        print(f"  {k}...")
        sd.sleep(1000)

    print("[record] Capturing audio...")
    try:
        audio = sd.rec(
            frames,
            samplerate=args.samplerate,
            channels=args.channels,
            dtype="float32",
            device=device_idx,
        )
        sd.wait()
    except Exception as exc:
        print(f"[error] Capture failed: {exc}")
        append_testlog("FAIL", "—", f"label={safe_label} device={device_name} error={exc}")
        sys.exit(1)

    audio = np.asarray(audio, dtype=np.float32)
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio

    peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    rms = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0
    clipping_fraction = float(np.mean(np.abs(mono) >= 0.999)) if len(mono) else 0.0

    # Save WAV as int16 for ordinary playback compatibility.
    wav_i16 = np.int16(np.clip(audio, -1.0, 1.0) * 32767)
    if wav_i16.ndim == 2 and wav_i16.shape[1] == 1:
        wav_i16 = wav_i16[:, 0]
    wavfile.write(wav_path, args.samplerate, wav_i16)

    metadata = {
        "phase": "Phase 5A",
        "script": "05_audio_capture_probe.py",
        "label": safe_label,
        "timestamp": timestamp,
        "device_index": device_idx,
        "device_name": device_name,
        "sample_rate_hz": args.samplerate,
        "channels": args.channels,
        "duration_s": args.duration,
        "frames": int(frames),
        "peak_abs": peak,
        "rms": rms,
        "clipping_fraction": clipping_fraction,
        "wav_path": str(wav_path.relative_to(ROOT)),
        "plot_path": str(png_path.relative_to(ROOT)),
        "rf_status": "NO SDR, NO RF, NO TRANSMISSION",
    }
    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    save_plot(
        np,
        plt,
        audio,
        args.samplerate,
        png_path,
        f"ORION Phase 5A Audio Capture — {safe_label}",
    )

    print()
    print("[+] WAV saved:      " + str(wav_path))
    print("[+] Metadata saved: " + str(json_path))
    print("[+] Plot saved:     " + str(png_path))
    print()
    print(f"Peak amplitude : {peak:.4f}  (target: ~0.2 to 0.8, avoid 1.0)")
    print(f"RMS amplitude  : {rms:.4f}")
    print(f"Clipping frac. : {clipping_fraction:.6f}")

    if peak < 0.02:
        verdict = "WEAK_INPUT"
        print("[!] Input is very quiet. Check Scarlett gain, mic switch, Windows input device.")
    elif clipping_fraction > 0.001 or peak > 0.98:
        verdict = "CLIPPING_RISK"
        print("[!] Input is near clipping. Lower Scarlett gain.")
    else:
        verdict = "PASS"
        print("[+] Audio capture level looks usable.")

    append_testlog(
        verdict,
        str(png_path.relative_to(ROOT)),
        f"label={safe_label} device=[{device_idx}] {device_name} "
        f"peak={peak:.4f} rms={rms:.4f} clip={clipping_fraction:.6f}",
    )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
