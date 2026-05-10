"""
ORION Phase 2 — RX Spectrum Probe

Receive IQ samples from a named PLUTO URI, compute an FFT noise-floor
spectrum, save a PNG plot, save raw IQ samples, and log the result.

NO TX. The script never calls sdr.tx() and never touches any TX attribute.
The only hardware state changes are the RX LO, sample rate, RX bandwidth,
and RX gain mode — all required for the receiver to function.

Preferred URIs (stable across USB reconnects — use these):
  Pluto A (AD9364,  fw v0.39):  ip:pluto.local   serial ends e9e
  Pluto B (AD9363A, fw v0.38):  ip:192.168.2.1   serial ends 149

Note: USB bus-path URIs (e.g. usb:1.8.5) are NOT stable — Windows
re-enumerates the hub on reconnect and reassigns paths. Historical test
logs reference them as recorded aliases only.

Usage:
  python scripts/01_rx_spectrum_probe.py --uri ip:pluto.local  --label pluto_a
  python scripts/01_rx_spectrum_probe.py --uri ip:192.168.2.1  --label pluto_b
  python scripts/01_rx_spectrum_probe.py --help
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

# Allow running from repo root without installing the package
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

TEST_LOG        = ROOT / "docs" / "test_logs" / "TEST_LOG.md"
DIR_SCREENSHOTS = ROOT / "data" / "screenshots"
DIR_CAPTURES    = ROOT / "data" / "captures"

# 12-bit ADC — pyadi-iio returns raw int16 IQ codes in this range
_PLUTO_ADC_FULLSCALE = 2048.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION RX spectrum probe — no TX, read-only hardware query.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--uri", required=True,
        help="IIO context URI. Preferred: ip:pluto.local (Pluto A) or ip:192.168.2.1 (Pluto B).",
    )
    p.add_argument(
        "--label", default=None,
        help="Short name for output files, e.g. pluto_a. Derived from URI if omitted.",
    )
    p.add_argument(
        "--freq", type=float, default=915e6,
        help="Center frequency in Hz. 915 MHz is within range of both AD9364 and AD9363A.",
    )
    p.add_argument(
        "--rate", type=float, default=1e6,
        help="Sample rate in Hz.",
    )
    p.add_argument(
        "--bw", type=float, default=1e6,
        help="RX RF bandwidth in Hz.",
    )
    p.add_argument(
        "--gain-mode", default="slow_attack",
        choices=["slow_attack", "fast_attack", "manual"],
        help="AGC mode. Use slow_attack for safe general reception.",
    )
    p.add_argument(
        "--gain-db", type=float, default=40.0,
        help="Manual RX gain in dB. Only applied when --gain-mode manual.",
    )
    p.add_argument(
        "--samples", type=int, default=131072,
        help="Number of IQ samples to capture (must be a power of 2 for clean FFT).",
    )
    p.add_argument(
        "--no-plot", action="store_true",
        help="Skip matplotlib plot (useful in headless environments).",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def check_deps(need_plot: bool) -> dict[str, bool]:
    deps = {}
    for name in ("adi", "iio", "numpy"):
        try:
            __import__(name)
            deps[name] = True
        except ImportError:
            deps[name] = False

    if need_plot:
        try:
            import matplotlib  # noqa: F401
            deps["matplotlib"] = True
        except ImportError:
            deps["matplotlib"] = False
    else:
        deps["matplotlib"] = None  # not required

    return deps


def _assert_deps(deps: dict[str, bool]) -> None:
    missing = [k for k, v in deps.items() if v is False]
    if missing:
        print("\n[!] Missing required packages:")
        for m in missing:
            print(f"    pip install {m}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Label helper
# ---------------------------------------------------------------------------

def uri_to_label(uri: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", uri).strip("_").lower()


# ---------------------------------------------------------------------------
# SDR setup (RX only)
# ---------------------------------------------------------------------------

def setup_sdr(
    uri: str,
    freq_hz: float,
    rate_hz: float,
    bw_hz: float,
    gain_mode: str,
    gain_db: float,
):
    """Configure the Pluto for RX. Returns the adi.Pluto instance."""
    import adi  # type: ignore

    print(f"  Connecting to {uri} ...")
    sdr = adi.Pluto(uri=uri)

    print(f"  Setting RX LO:        {freq_hz / 1e6:.6f} MHz")
    sdr.rx_lo = int(freq_hz)

    print(f"  Setting sample rate:  {rate_hz / 1e6:.3f} Msps")
    sdr.sample_rate = int(rate_hz)

    print(f"  Setting RX bandwidth: {bw_hz / 1e6:.3f} MHz")
    try:
        sdr.rx_rf_bandwidth = int(bw_hz)
    except Exception as e:
        print(f"  [!] rx_rf_bandwidth: {e} — continuing with device default")

    print(f"  Setting gain mode:    {gain_mode}")
    sdr.gain_control_mode_chan0 = gain_mode

    if gain_mode == "manual":
        print(f"  Setting manual gain:  {gain_db:.1f} dB")
        sdr.rx_hardwaregain_chan0 = gain_db

    sdr.rx_buffer_size = 65536  # pre-fill buffer; overridden below by actual capture count
    return sdr


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def capture_samples(sdr, n_samples: int):
    """Return a numpy complex array of n_samples IQ samples. No TX."""
    import numpy as np  # type: ignore

    sdr.rx_buffer_size = n_samples
    raw = sdr.rx()
    samples = np.array(raw, dtype=np.complex128)
    print(f"  Captured {len(samples)} samples  "
          f"(I range [{samples.real.min():.0f}, {samples.real.max():.0f}]  "
          f"Q range [{samples.imag.min():.0f}, {samples.imag.max():.0f}])")
    return samples


# ---------------------------------------------------------------------------
# Spectrum computation
# ---------------------------------------------------------------------------

def compute_spectrum(
    samples,
    rate_hz: float,
) -> tuple:
    """
    Returns (freqs_mhz, psd_dbfs, noise_floor_dbfs, peak_dbfs, peak_offset_mhz).

    psd_dbfs is calibrated so that a full-scale sinusoid (amplitude = ADC_FULLSCALE)
    would read 0 dBFS. Pluto ADC is 12-bit so full scale = 2048 raw counts.
    """
    import numpy as np  # type: ignore

    N = len(samples)
    win = np.hanning(N)
    # Coherent amplitude gain of the Hann window ≈ 0.5
    win_coherent_gain = np.mean(win)

    windowed = samples * win
    X = np.fft.fftshift(np.fft.fft(windowed))

    # Amplitude spectrum normalised to window coherent gain and full-scale reference
    amplitude = np.abs(X) / (N * win_coherent_gain * _PLUTO_ADC_FULLSCALE)
    psd_dbfs = 20.0 * np.log10(amplitude + 1e-12)

    freqs_hz = np.fft.fftshift(np.fft.fftfreq(N, d=1.0 / rate_hz))
    freqs_mhz = freqs_hz / 1e6

    noise_floor_dbfs = float(np.percentile(psd_dbfs, 10))
    peak_idx = int(np.argmax(psd_dbfs))
    peak_dbfs = float(psd_dbfs[peak_idx])
    peak_offset_mhz = float(freqs_mhz[peak_idx])

    return freqs_mhz, psd_dbfs, noise_floor_dbfs, peak_dbfs, peak_offset_mhz


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def save_plot(
    freqs_mhz,
    psd_dbfs,
    noise_floor_dbfs: float,
    peak_dbfs: float,
    peak_offset_mhz: float,
    uri: str,
    freq_hz: float,
    rate_hz: float,
    gain_mode: str,
    timestamp_str: str,
    outdir: Path,
    stem: str,
) -> Path:
    import matplotlib  # type: ignore
    matplotlib.use("Agg")  # non-interactive backend; safe on headless machines
    import matplotlib.pyplot as plt  # type: ignore
    import numpy as np  # type: ignore

    fig, ax = plt.subplots(figsize=(13, 5))

    ax.plot(freqs_mhz, psd_dbfs, color="#2196F3", linewidth=0.6, alpha=0.85,
            label="PSD (Hann window)")

    ax.axhline(noise_floor_dbfs, color="#F44336", linewidth=1.2, linestyle="--",
               label=f"10th-pct noise floor: {noise_floor_dbfs:.1f} dBFS")

    ax.axvline(peak_offset_mhz, color="#FF9800", linewidth=0.8, linestyle=":",
               alpha=0.7)
    ax.annotate(
        f"Peak: {peak_dbfs:.1f} dBFS\n@ {peak_offset_mhz:+.3f} MHz offset",
        xy=(peak_offset_mhz, peak_dbfs),
        xytext=(peak_offset_mhz + rate_hz / 1e6 * 0.08, peak_dbfs - 6),
        fontsize=7.5,
        color="#FF9800",
        arrowprops=dict(arrowstyle="->", color="#FF9800", lw=0.8),
    )

    center_mhz = freq_hz / 1e6
    ax.set_xlabel(f"Frequency offset from {center_mhz:.3f} MHz (MHz)", fontsize=9)
    ax.set_ylabel("Power (dBFS)", fontsize=9)
    ax.set_title(
        f"ORION RX Spectrum — {uri}\n"
        f"{center_mhz:.3f} MHz · {rate_hz/1e6:.3f} Msps · gain={gain_mode} · {timestamp_str}",
        fontsize=9,
    )
    ax.set_xlim(freqs_mhz[0], freqs_mhz[-1])
    # Floor the y-axis 10 dB below noise floor for clean headroom
    y_min = min(noise_floor_dbfs - 10, float(np.percentile(psd_dbfs, 2)) - 5)
    y_max = max(peak_dbfs + 6, 0)
    ax.set_ylim(y_min, y_max)
    ax.grid(True, alpha=0.3, linewidth=0.4)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()

    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"{stem}.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Save raw IQ capture
# ---------------------------------------------------------------------------

def save_capture(
    samples,
    meta: dict,
    outdir: Path,
    stem: str,
) -> tuple[Path, Path]:
    import numpy as np  # type: ignore

    outdir.mkdir(parents=True, exist_ok=True)
    npy_path  = outdir / f"{stem}.npy"
    json_path = outdir / f"{stem}.json"

    np.save(npy_path, samples.astype(np.complex64))
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return npy_path, json_path


# ---------------------------------------------------------------------------
# TEST_LOG append
# ---------------------------------------------------------------------------

def append_testlog(
    log_path: Path,
    timestamp: str,
    uri: str,
    freq_hz: float,
    rate_hz: float,
    gain_mode: str,
    result_str: str,
    evidence_file: str,
    notes: str,
) -> None:
    row = (
        f"| {timestamp} | Phase 2 | RX spectrum probe | "
        f"{uri} @ {freq_hz/1e6:.3f}MHz {rate_hz/1e6:.3f}Msps {gain_mode} | "
        f"{result_str} | {evidence_file} | {notes} |"
    )
    existing = log_path.read_text(encoding="utf-8")
    log_path.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    label = args.label or uri_to_label(args.uri)
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")
    file_ts   = now.strftime("%Y%m%d_%H%M%S")
    stem = f"spectrum_{label}_{file_ts}"

    print("=" * 68)
    print("ORION Phase 2 — RX Spectrum Probe")
    print("=" * 68)
    print(f"  URI        : {args.uri}")
    print(f"  Label      : {label}")
    print(f"  Freq       : {args.freq/1e6:.3f} MHz")
    print(f"  Rate       : {args.rate/1e6:.3f} Msps")
    print(f"  Bandwidth  : {args.bw/1e6:.3f} MHz")
    print(f"  Gain mode  : {args.gain_mode}" +
          (f"  ({args.gain_db:.0f} dB)" if args.gain_mode == "manual" else ""))
    print(f"  N samples  : {args.samples}")
    print(f"  Plot       : {'disabled' if args.no_plot else 'enabled'}")
    print()

    # ---- dependency check ------------------------------------------------
    deps = check_deps(need_plot=not args.no_plot)
    for k, v in deps.items():
        if v is True:
            print(f"  [+] {k}")
        elif v is False:
            print(f"  [!] {k}  MISSING")
    _assert_deps(deps)
    print()

    # ---- SDR setup (RX only) ---------------------------------------------
    print("Configuring SDR (RX only — no TX) ...")
    try:
        sdr = setup_sdr(
            args.uri, args.freq, args.rate, args.bw,
            args.gain_mode, args.gain_db,
        )
    except Exception as exc:
        print(f"\n[!] Failed to connect: {exc}")
        append_testlog(
            TEST_LOG, timestamp, args.uri, args.freq, args.rate,
            args.gain_mode, f"FAIL — {exc}", "none", f"label={label}",
        )
        sys.exit(1)
    print()

    # ---- capture ---------------------------------------------------------
    print(f"Capturing {args.samples} IQ samples ...")
    try:
        samples = capture_samples(sdr, args.samples)
    except Exception as exc:
        print(f"\n[!] Capture failed: {exc}")
        del sdr
        append_testlog(
            TEST_LOG, timestamp, args.uri, args.freq, args.rate,
            args.gain_mode, f"FAIL — {exc}", "none", f"label={label}",
        )
        sys.exit(1)
    del sdr  # release IIO context — no close() needed in pylibiio
    print()

    # ---- spectrum --------------------------------------------------------
    print("Computing spectrum ...")
    freqs_mhz, psd_dbfs, noise_floor, peak_dbfs, peak_offset_mhz = compute_spectrum(
        samples, args.rate
    )
    print(f"  Noise floor (10th pct) : {noise_floor:.1f} dBFS")
    print(f"  Peak                   : {peak_dbfs:.1f} dBFS  at {peak_offset_mhz:+.3f} MHz offset")
    print()

    # ---- save raw IQ -----------------------------------------------------
    meta = {
        "uri":             args.uri,
        "label":           label,
        "timestamp":       now.isoformat(),
        "center_freq_hz":  int(args.freq),
        "sample_rate_hz":  int(args.rate),
        "rx_bw_hz":        int(args.bw),
        "gain_mode":       args.gain_mode,
        "gain_db_manual":  args.gain_db if args.gain_mode == "manual" else None,
        "num_samples":     len(samples),
        "noise_floor_dbfs": round(noise_floor, 2),
        "peak_dbfs":       round(peak_dbfs, 2),
        "peak_offset_mhz": round(peak_offset_mhz, 4),
    }
    npy_path, json_path = save_capture(samples, meta, DIR_CAPTURES, stem)
    print(f"[+] Raw IQ saved:  {npy_path}")
    print(f"[+] Metadata:      {json_path}")

    # ---- plot ------------------------------------------------------------
    plot_path: Path | None = None
    if not args.no_plot:
        print("Rendering plot ...")
        try:
            plot_path = save_plot(
                freqs_mhz, psd_dbfs, noise_floor, peak_dbfs, peak_offset_mhz,
                uri=args.uri,
                freq_hz=args.freq,
                rate_hz=args.rate,
                gain_mode=args.gain_mode,
                timestamp_str=timestamp,
                outdir=DIR_SCREENSHOTS,
                stem=stem,
            )
            print(f"[+] Plot saved:    {plot_path}")
        except Exception as exc:
            print(f"[!] Plot failed:   {exc}")
    print()

    # ---- TEST_LOG --------------------------------------------------------
    evidence = plot_path.name if plot_path else npy_path.name
    notes = (
        f"label={label}  peak={peak_dbfs:.1f}dBFS  "
        f"floor={noise_floor:.1f}dBFS  "
        f"peak_off={peak_offset_mhz:+.3f}MHz"
    )
    append_testlog(
        TEST_LOG, timestamp, args.uri, args.freq, args.rate,
        args.gain_mode, "PASS", evidence, notes,
    )
    print(f"[+] Test log updated: {TEST_LOG}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
