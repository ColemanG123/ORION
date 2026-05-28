#!/usr/bin/env python3
"""
08_rx_voice_fm_capture.py — ORION Phase 5C RX IQ recorder.

Records finite IQ from e9e for later offline FM demodulation.

RX only. No transmission.

Identity rule:
  Use stable serial identity, not unstable USB paths.

  Default:
    --rx-id e9e

  Optional debug override:
    --uri <current IIO URI>
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion.pluto_identity import canonical_suffix, resolve_pluto_uri

CAPTURE_DIR = ROOT / "data" / "captures"
SCREENSHOT_DIR = ROOT / "data" / "screenshots"
TEST_LOG = ROOT / "docs" / "test_logs" / "TEST_LOG.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION Phase 5C RX IQ capture from e9e. RX only, no TX.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--rx-id", default="e9e", help="Stable RX identity or serial suffix. Default is e9e.")
    p.add_argument("--uri", default=None, help="Optional direct RX URI override for debugging. Normally omit this.")
    p.add_argument(
        "--expect-serial-suffix",
        default=None,
        help="Optional expected RX serial suffix. Defaults to suffix implied by --rx-id.",
    )

    p.add_argument("--label", default="e9e_voice_rx", help="Output label.")
    p.add_argument("--freq", type=float, default=915e6, help="RX LO frequency in Hz.")
    p.add_argument("--rate", type=int, default=1_000_000, help="Sample rate in samples/s.")
    p.add_argument("--bandwidth", type=int, default=1_000_000, help="RX RF bandwidth in Hz.")
    p.add_argument("--duration", type=float, default=7.0, help="Capture duration in seconds.")
    p.add_argument("--gain-mode", default="slow_attack", help="RX gain mode.")
    p.add_argument("--gain-db", type=float, default=50.0, help="Manual RX gain if gain-mode=manual.")
    p.add_argument("--buffer-size", type=int, default=262144, help="RX buffer size.")
    p.add_argument("--max-fft", type=int, default=262144, help="Max samples used for FFT plot.")
    return p.parse_args()


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5C RX | Voice FM IQ capture from e9e | "
        f"08_rx_voice_fm_capture.py | {status} | {evidence} | {notes} |"
    )
    existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


def check_serial(uri: str, expected_suffix: str) -> tuple[str, str]:
    try:
        import iio

        ctx = iio.Context(uri)
        serial = ctx.attrs.get("hw_serial", "")
        model = ctx.attrs.get("hw_model", "")
    except Exception as exc:
        raise RuntimeError(f"Could not open IIO context for serial check: {exc}")

    if not serial.lower().endswith(expected_suffix.lower()):
        raise RuntimeError(
            f"Serial mismatch for {uri}. Expected suffix {expected_suffix}, got {serial!r}."
        )

    return serial, model


def resolve_rx_uri(args: argparse.Namespace) -> tuple[str, str, str, str]:
    expected_suffix = args.expect_serial_suffix or canonical_suffix(args.rx_id)

    if args.uri:
        uri = args.uri
        serial, model = check_serial(uri, expected_suffix)
        return uri, serial, model, expected_suffix

    match = resolve_pluto_uri(args.rx_id, verbose=True)
    uri = match.uri
    serial, model = check_serial(uri, expected_suffix)
    return uri, serial, model, expected_suffix


def spectrum(iq: np.ndarray, fs: int, max_fft: int):
    n = min(len(iq), max_fft)
    x = iq[:n]
    win = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(x * win))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
    mag = np.abs(spec)
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    db -= np.max(db)
    return freq, db


def save_plot(path: Path, iq: np.ndarray, fs: int, center_hz: float, label: str, max_fft: int):
    freq, db = spectrum(iq, fs, max_fft)
    floor = float(np.percentile(db, 10))
    peak_idx = int(np.argmax(db))
    peak_db = float(db[peak_idx])
    peak_offset = float(freq[peak_idx])

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    ax.plot(freq / 1e6, db)
    ax.axhline(floor, linestyle="--", label=f"10th pct floor: {floor:.1f} dB rel")
    ax.axvline(0, linestyle=":", alpha=0.7)
    ax.axvline(0.100, linestyle=":", alpha=0.7, label="+100 kHz expected voice center")
    ax.set_title(f"ORION Phase 5C RX Capture — {label}\n{center_hz/1e6:.3f} MHz, {fs/1e6:.3f} Msps")
    ax.set_xlabel(f"Frequency offset from {center_hz/1e6:.3f} MHz (MHz)")
    ax.set_ylabel("Magnitude (dB relative)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.annotate(
        f"Peak: {peak_db:.1f} dB rel\n@ {peak_offset/1e3:+.1f} kHz",
        xy=(peak_offset / 1e6, peak_db),
        xytext=(peak_offset / 1e6 + 0.05, peak_db - 10),
        arrowprops=dict(arrowstyle="->"),
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)

    return floor, peak_db, peak_offset


def main() -> None:
    args = parse_args()

    try:
        import adi
    except Exception as exc:
        print(f"[error] import adi failed: {exc}")
        sys.exit(1)

    try:
        rx_uri, rx_serial, rx_model, expected_suffix = resolve_rx_uri(args)
    except Exception as exc:
        print(f"[error] {exc}")
        append_testlog("FAIL", "—", f"rx_id={args.rx_id} uri={args.uri} resolve_failed={exc}")
        sys.exit(1)

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in args.label)

    npy_path = CAPTURE_DIR / f"voice_rx_{safe_label}_{timestamp}.npy"
    json_path = CAPTURE_DIR / f"voice_rx_{safe_label}_{timestamp}.json"
    png_path = SCREENSHOT_DIR / f"voice_rx_{safe_label}_{timestamp}.png"

    target_samples = int(round(args.duration * args.rate))

    print("=" * 72)
    print("ORION Phase 5C — RX Voice FM IQ Capture")
    print("=" * 72)
    print("RX only. No transmission.")
    print()
    print(f"RX identity : {args.rx_id}")
    print(f"Resolved URI: {rx_uri}")
    print(f"Serial      : {rx_serial}")
    print(f"Model       : {rx_model}")
    print(f"Expected SN : ...{expected_suffix}")
    print(f"Label       : {safe_label}")
    print(f"Freq        : {args.freq/1e6:.6f} MHz")
    print(f"Rate        : {args.rate/1e6:.3f} Msps")
    print(f"Bandwidth   : {args.bandwidth/1e6:.3f} MHz")
    print(f"Duration    : {args.duration:.2f} s")
    print(f"Samples     : {target_samples}")

    try:
        sdr = adi.Pluto(rx_uri)
        sdr.rx_lo = int(args.freq)
        sdr.sample_rate = int(args.rate)
        sdr.rx_rf_bandwidth = int(args.bandwidth)
        sdr.rx_buffer_size = int(args.buffer_size)
        sdr.gain_control_mode_chan0 = args.gain_mode
        if args.gain_mode == "manual":
            sdr.rx_hardwaregain_chan0 = float(args.gain_db)
    except Exception as exc:
        print(f"[error] RX setup failed: {exc}")
        append_testlog("FAIL", "—", f"label={safe_label} rx_uri={rx_uri} setup_error={exc}")
        sys.exit(1)

    print()
    print("[rx] Flushing initial buffers...")
    for _ in range(3):
        try:
            _ = sdr.rx()
        except Exception:
            pass

    chunks = []
    got = 0
    print("[rx] Capturing...")
    while got < target_samples:
        try:
            x = sdr.rx()
        except KeyboardInterrupt:
            print("[rx] Aborted by operator.")
            break
        except Exception as exc:
            print(f"[error] RX failed: {exc}")
            append_testlog("FAIL", "—", f"label={safe_label} rx_uri={rx_uri} rx_error={exc}")
            sys.exit(1)

        x = np.asarray(x, dtype=np.complex64).ravel()
        chunks.append(x)
        got += len(x)
        print(f"  {got}/{target_samples} samples", end="\r")

    print()

    iq = np.concatenate(chunks)[:target_samples].astype(np.complex64)
    np.save(npy_path, iq)

    floor, peak_db, peak_offset = save_plot(png_path, iq, args.rate, args.freq, safe_label, args.max_fft)

    metadata = {
        "phase": "Phase 5C RX",
        "script": "08_rx_voice_fm_capture.py",
        "label": safe_label,
        "timestamp": timestamp,
        "rx_identity": args.rx_id,
        "resolved_uri": rx_uri,
        "rx_serial": rx_serial,
        "rx_model": rx_model,
        "expected_serial_suffix": expected_suffix,
        "manual_uri_override_used": bool(args.uri),
        "center_freq_hz": args.freq,
        "sample_rate_hz": args.rate,
        "rx_bandwidth_hz": args.bandwidth,
        "gain_mode": args.gain_mode,
        "gain_db": args.gain_db if args.gain_mode == "manual" else None,
        "duration_s": args.duration,
        "samples": int(len(iq)),
        "dtype": "complex64",
        "expected_voice_offset_hz": 100000.0,
        "capture_path": str(npy_path.relative_to(ROOT)),
        "plot_path": str(png_path.relative_to(ROOT)),
        "noise_floor_db_relative": floor,
        "peak_db_relative": peak_db,
        "peak_offset_hz": peak_offset,
        "rf_status": "RX ONLY, NO TRANSMISSION FROM THIS SCRIPT",
    }
    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    append_testlog(
        "PASS",
        str(png_path.relative_to(ROOT)),
        f"label={safe_label} rx_id={args.rx_id} uri={rx_uri} serial={rx_serial} "
        f"samples={len(iq)} peak_offset={peak_offset/1e3:+.1f}kHz",
    )

    print("[+] IQ saved:       " + str(npy_path))
    print("[+] Metadata saved: " + str(json_path))
    print("[+] Plot saved:     " + str(png_path))
    print("Done.")


if __name__ == "__main__":
    main()