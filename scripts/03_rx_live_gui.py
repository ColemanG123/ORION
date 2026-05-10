"""
ORION Phase 3 — RX-Only Live Spectrum GUI

Displays a continuously-updated FFT spectrum from one ADALM-PLUTO.

NO TX.  The script never calls sdr.tx() and never touches any TX attribute.
RX LO, sample rate, RX bandwidth, and RX gain mode are the only hardware
settings configured.

Preferred URIs (stable across USB reconnects — use these):
  Pluto A (AD9364,  fw v0.39):  ip:pluto.local   serial ends e9e
  Pluto B (AD9363A, fw v0.38):  ip:192.168.2.1   serial ends 149

Note: USB bus-path URIs (e.g. usb:1.8.5) are NOT stable — Windows
re-enumerates the hub on reconnect and reassigns paths. Historical test
logs reference them as recorded aliases only.

Usage:
  python scripts/03_rx_live_gui.py --uri ip:pluto.local --label pluto_a
  python scripts/03_rx_live_gui.py --uri ip:192.168.2.1 --label pluto_b
  python scripts/03_rx_live_gui.py --uri ip:pluto.local --freq 433.9e6 --label pluto_a
  python scripts/03_rx_live_gui.py --help

Keyboard shortcuts (window must have focus):
  s  — save screenshot to data/screenshots/
  q  — quit
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT            = Path(__file__).parent.parent
DIR_SCREENSHOTS = ROOT / "data" / "screenshots"
TEST_LOG        = ROOT / "docs" / "test_logs" / "TEST_LOG.md"

sys.path.insert(0, str(ROOT / "src"))

_PLUTO_ADC_FULLSCALE = 2048.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION Phase 3 — RX live spectrum GUI. No TX.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--uri",         required=True,
                   help="IIO context URI. Preferred: ip:pluto.local (Pluto A) or ip:192.168.2.1 (Pluto B).")
    p.add_argument("--label",       default=None,
                   help="Short device label, e.g. pluto_a. Derived from URI if omitted.")
    p.add_argument("--freq",        type=float, default=915e6,
                   help="Center frequency Hz.")
    p.add_argument("--rate",        type=float, default=1e6,
                   help="Sample rate Hz.")
    p.add_argument("--rx-bw",       type=float, default=1e6,
                   help="RX RF bandwidth Hz.")
    p.add_argument("--gain-mode",   default="slow_attack",
                   choices=["slow_attack", "fast_attack", "manual"],
                   help="AGC mode.")
    p.add_argument("--gain-db",     type=float, default=40.0,
                   help="Manual RX gain dB (only when --gain-mode manual).")
    p.add_argument("--samples",     type=int, default=32768,
                   help="IQ samples per frame.")
    p.add_argument("--interval-ms", type=int, default=500,
                   help="Animation update interval ms.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def check_deps() -> None:
    missing = []
    for pkg in ("adi", "numpy", "matplotlib"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("[!] Missing packages:")
        for m in missing:
            print(f"    pip install {m}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uri_to_label(uri: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", uri).strip("_").lower()


def _setup_sdr(uri: str, freq_hz: float, rate_hz: float, bw_hz: float,
               gain_mode: str, gain_db: float):
    """Connect and configure Pluto for RX only. Returns sdr object."""
    import adi  # type: ignore
    print(f"  Connecting:   {uri}")
    sdr = adi.Pluto(uri=uri)
    print(f"  RX LO:        {freq_hz/1e6:.6f} MHz")
    sdr.rx_lo = int(freq_hz)
    print(f"  Sample rate:  {rate_hz/1e6:.3f} Msps")
    sdr.sample_rate = int(rate_hz)
    print(f"  RX bandwidth: {bw_hz/1e6:.3f} MHz")
    try:
        sdr.rx_rf_bandwidth = int(bw_hz)
    except Exception as e:
        print(f"  [!] rx_rf_bandwidth skipped: {e}")
    print(f"  Gain mode:    {gain_mode}")
    sdr.gain_control_mode_chan0 = gain_mode
    if gain_mode == "manual":
        print(f"  Manual gain:  {gain_db:.1f} dB")
        sdr.rx_hardwaregain_chan0 = gain_db
    sdr.rx_buffer_size = 32768
    return sdr


def _compute_spectrum(samples, rate_hz: float):
    """Return (freqs_mhz, psd_dbfs, noise_floor, peak_dbfs, peak_offset_mhz)."""
    import numpy as np  # type: ignore
    N = len(samples)
    win = np.hanning(N)
    win_gain = np.mean(win)
    X = np.fft.fftshift(np.fft.fft(samples * win))
    amplitude = np.abs(X) / (N * win_gain * _PLUTO_ADC_FULLSCALE)
    psd = 20.0 * np.log10(amplitude + 1e-12)
    freqs = np.fft.fftshift(np.fft.fftfreq(N, d=1.0 / rate_hz)) / 1e6
    noise_floor = float(np.percentile(psd, 10))
    peak_idx    = int(np.argmax(psd))
    peak_dbfs   = float(psd[peak_idx])
    peak_offset = float(freqs[peak_idx])
    return freqs, psd, noise_floor, peak_dbfs, peak_offset


def _build_status(args, label: str, frames: int,
                  floor: float, peak: float, offset: float) -> str:
    center_mhz = args.freq / 1e6
    rate_mhz   = args.rate / 1e6
    lines = [
        "─" * 22,
        f"URI:    {args.uri}",
        f"Label:  {label}",
        "─" * 22,
        f"Freq:   {center_mhz:.3f} MHz",
        f"Rate:   {rate_mhz:.3f} Msps",
        f"Gain:   {args.gain_mode}",
        "─" * 22,
        f"Frame:  {frames}",
        "─" * 22,
        f"Floor:  {floor:.1f} dBFS",
        f"Peak:   {peak:.1f} dBFS",
        f"Offset: {offset:+.4f} MHz",
        f"AbvFlr: {peak - floor:.1f} dB",
        "─" * 22,
        "s = screenshot",
        "q = quit",
    ]
    return "\n".join(lines)


def _save_screenshot(fig, label: str) -> None:
    DIR_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DIR_SCREENSHOTS / f"live_{label}_{ts}.png"
    try:
        fig.savefig(path, dpi=120, bbox_inches="tight")
        print(f"\n[+] Screenshot saved: {path}")
    except Exception as e:
        print(f"\n[!] Screenshot failed: {e}")


def _append_testlog(phase: str, result: str, notes: str) -> None:
    try:
        ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        row = (
            f"| {ts} | {phase} | RX live GUI | "
            f"03_rx_live_gui.py | {result} | — | {notes} |"
        )
        existing = TEST_LOG.read_text(encoding="utf-8")
        TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[!] TEST_LOG write failed: {e}")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def run_gui(sdr, args, label: str) -> None:
    import numpy as np  # type: ignore
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt  # type: ignore
    import matplotlib.gridspec as gridspec  # type: ignore
    from matplotlib.animation import FuncAnimation  # type: ignore

    center_mhz = args.freq / 1e6
    rate_mhz   = args.rate / 1e6

    # --- initial frame to size axes before the window opens ---------------
    sdr.rx_buffer_size = args.samples
    raw     = sdr.rx()
    samples = np.array(raw, dtype=np.complex128)
    freqs_mhz, psd_dbfs, noise_floor, peak_dbfs, peak_offset = _compute_spectrum(
        samples, args.rate
    )

    # --- figure layout ----------------------------------------------------
    fig = plt.figure(figsize=(15, 6))
    fig.suptitle(
        f"ORION RX Live Spectrum — {label}  ·  {center_mhz:.3f} MHz  ·  {rate_mhz:.3f} Msps",
        fontsize=10, fontweight="bold",
    )

    # Window title (best-effort; not all backends expose manager before show())
    try:
        fig.canvas.manager.set_window_title(f"ORION RX Live Spectrum — {label}")
    except Exception:
        pass

    # Permanent RX-only safety badge — top-right of figure
    fig.text(
        0.995, 0.995, "RX ONLY — TX DISABLED",
        ha="right", va="top",
        fontsize=7.5, fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#B71C1C", alpha=0.88),
        transform=fig.transFigure,
        zorder=10,
    )

    gs      = gridspec.GridSpec(1, 2, width_ratios=[4, 1], wspace=0.12,
                                left=0.06, right=0.97, top=0.91, bottom=0.10)
    ax_spec = fig.add_subplot(gs[0])
    ax_info = fig.add_subplot(gs[1])
    ax_info.axis("off")

    # --- spectrum artists -------------------------------------------------
    (line,) = ax_spec.plot(freqs_mhz, psd_dbfs,
                           color="#2196F3", lw=0.7, alpha=0.9, label="PSD (Hann)")

    hline = ax_spec.axhline(noise_floor, color="#F44336", lw=1.1, ls="--",
                            label=f"Floor: {noise_floor:.1f} dBFS")

    vline = ax_spec.axvline(peak_offset, color="#FF9800", lw=0.8, ls=":",
                            alpha=0.8)

    # Downward triangle marker at peak bin
    (peak_marker,) = ax_spec.plot(
        [peak_offset], [peak_dbfs], "v",
        color="#FF9800", markersize=9, zorder=5,
    )

    # Fixed-position peak info text (upper-left corner of spectrum axes)
    peak_text = ax_spec.text(
        0.01, 0.98,
        f"Peak: {peak_dbfs:.1f} dBFS  @  {peak_offset:+.4f} MHz",
        transform=ax_spec.transAxes,
        va="top", ha="left", fontsize=8, color="#FF9800",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.75),
    )

    ax_spec.set_xlabel(
        f"Frequency offset from {center_mhz:.3f} MHz (MHz)", fontsize=9
    )
    ax_spec.set_ylabel("Power (dBFS)", fontsize=9)
    ax_spec.set_xlim(freqs_mhz[0], freqs_mhz[-1])
    y_lo = noise_floor - 12
    y_hi = max(peak_dbfs + 8, 0)
    ax_spec.set_ylim(y_lo, y_hi)
    ax_spec.grid(True, alpha=0.25, lw=0.4)
    ax_spec.legend(fontsize=8, loc="upper right")

    # --- status text panel ------------------------------------------------
    status_obj = ax_info.text(
        0.05, 0.97,
        _build_status(args, label, 0, noise_floor, peak_dbfs, peak_offset),
        transform=ax_info.transAxes,
        va="top", ha="left",
        fontsize=8.5, color="#222222",
        fontfamily="monospace",
    )

    # --- mutable state (avoid nonlocal in nested def) --------------------
    state = {"frames": 0, "closed": False}

    # --- animation callback -----------------------------------------------
    def _update(_frame_num):
        try:
            raw     = sdr.rx()
            samples = np.array(raw, dtype=np.complex128)
            f_mhz, psd, floor, peak, offset = _compute_spectrum(samples, args.rate)

            line.set_ydata(psd)

            hline.set_ydata([floor, floor])
            hline.set_label(f"Floor: {floor:.1f} dBFS")

            vline.set_xdata([offset, offset])

            peak_marker.set_data([offset], [peak])
            peak_text.set_text(
                f"Peak: {peak:.1f} dBFS  @  {offset:+.4f} MHz"
            )

            # Smooth y-axis rescale
            y_lo = min(floor - 12, float(np.percentile(psd, 2)) - 5)
            y_hi = max(peak + 8, 0)
            ax_spec.set_ylim(y_lo, y_hi)

            state["frames"] += 1
            status_obj.set_text(
                _build_status(args, label, state["frames"], floor, peak, offset)
            )

            ax_spec.legend(fontsize=8, loc="upper right")

        except Exception as exc:
            # Don't crash the animation on a transient RX error
            print(f"\r[!] Frame {state['frames']} error: {exc}  ", end="", flush=True)

    # --- keyboard handler -------------------------------------------------
    def _on_key(event):
        if event.key == "s":
            _save_screenshot(fig, label)
        elif event.key in ("q", "escape"):
            plt.close(fig)

    # --- close handler ----------------------------------------------------
    def _on_close(_event):
        if state["closed"]:
            return
        state["closed"] = True
        n = state["frames"]
        _append_testlog(
            "Phase 3",
            f"CLOSED after {n} frame(s)",
            f"label={label} uri={args.uri} freq={center_mhz:.3f}MHz frames={n}",
        )
        print(f"\n[+] GUI closed — {n} frame(s) displayed.")

    fig.canvas.mpl_connect("key_press_event", _on_key)
    fig.canvas.mpl_connect("close_event",     _on_close)

    # Keep ani referenced so it is not garbage-collected
    _ani = FuncAnimation(  # noqa: F841
        fig, _update,
        interval=args.interval_ms,
        blit=False,
        cache_frame_data=False,
    )

    plt.show()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    args  = parse_args()
    label = args.label or _uri_to_label(args.uri)

    print("=" * 60)
    print("ORION Phase 3 — RX Live Spectrum GUI")
    print("=" * 60)
    print(f"  URI         : {args.uri}")
    print(f"  Label       : {label}")
    print(f"  Freq        : {args.freq/1e6:.3f} MHz")
    print(f"  Rate        : {args.rate/1e6:.3f} Msps")
    print(f"  RX BW       : {args.rx_bw/1e6:.3f} MHz")
    print(f"  Gain mode   : {args.gain_mode}" +
          (f"  ({args.gain_db:.0f} dB)" if args.gain_mode == "manual" else ""))
    print(f"  Samples/frm : {args.samples}")
    print(f"  Interval    : {args.interval_ms} ms")
    print()

    check_deps()

    # --- connect ----------------------------------------------------------
    print("Configuring SDR (RX only — no TX) ...")
    try:
        sdr = _setup_sdr(
            args.uri, args.freq, args.rate, args.rx_bw,
            args.gain_mode, args.gain_db,
        )
    except Exception as exc:
        print(f"\n[!] Connection failed: {exc}")
        _append_testlog(
            "Phase 3", f"FAIL — {exc}",
            f"label={label} uri={args.uri}",
        )
        sys.exit(1)

    print()
    print("SDR ready. Launching GUI ...")
    print("  Keyboard:  s = screenshot   q = quit")
    print()

    # --- log START --------------------------------------------------------
    _append_testlog(
        "Phase 3", "STARTED",
        f"label={label} uri={args.uri} freq={args.freq/1e6:.3f}MHz "
        f"rate={args.rate/1e6:.3f}Msps gain={args.gain_mode}",
    )

    # --- run GUI ----------------------------------------------------------
    try:
        run_gui(sdr, args, label)
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
    finally:
        try:
            del sdr
        except Exception:
            pass


if __name__ == "__main__":
    main()
