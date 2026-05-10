#!/usr/bin/env python3
"""
04_tx_tone_low_power.py — Phase 4A: low-power over-air CW tone TX.

Transmits a single continuous-wave tone from PLUTO B at very low power.
No modulation, no encoding, no packets. The only goal is to produce a
narrowband spectral peak that PLUTO A's live GUI can observe and confirm.

Safety gate: --yes-i-understand-rf-tx must be passed to actually transmit.
Omit it for a dry run that prints the planned configuration and exits.

Stable device identity:
  PLUTO A  RX observer  ip:pluto.local   serial ends e9e  (AD9364,  fw v0.39)
  PLUTO B  TX device    ip:192.168.2.1   serial ends 149  (AD9363A, fw v0.38)

Usage:
  # Dry run — prints config, no RF output:
  python scripts\\04_tx_tone_low_power.py

  # 10-second transmit after operator verification:
  python scripts\\04_tx_tone_low_power.py --yes-i-understand-rf-tx

  # Custom parameters + transmit:
  python scripts\\04_tx_tone_low_power.py --tx-gain-db -35 --duration 30 --yes-i-understand-rf-tx
"""

from __future__ import annotations

import argparse
import datetime
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

TEST_LOG = ROOT / "docs" / "test_logs" / "TEST_LOG.md"

# pyadi-iio PlutoSDR DAC headroom: int16 range scaled to 2^14
_DAC_FULL_SCALE = 2 ** 14   # 16384
_MAX_AMPLITUDE  = 0.9        # conservative ceiling; 1.0 clips the DAC


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Phase 4A: low-power over-air CW tone from PLUTO B. "
            "Requires --yes-i-understand-rf-tx to actually transmit."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--uri", default="ip:192.168.2.1",
        help="IIO context URI for TX device (Pluto B, serial ends 149)",
    )
    p.add_argument(
        "--label", default="pluto_b_tx_tone",
        help="Short label used in TEST_LOG entries and console output",
    )
    p.add_argument(
        "--freq", type=float, default=915e6,
        help="TX center frequency Hz — TX LO is set to this value",
    )
    p.add_argument(
        "--rate", type=float, default=1e6,
        help="Sample rate Hz",
    )
    p.add_argument(
        "--tx-bw", type=float, default=1e6,
        help="TX RF bandwidth Hz",
    )
    p.add_argument(
        "--tone-offset", type=float, default=100e3,
        help="Tone offset from center frequency Hz — +100 kHz avoids LO leakage",
    )
    p.add_argument(
        "--duration", type=float, default=10.0,
        help="Transmission duration seconds",
    )
    p.add_argument(
        "--tx-gain-db", type=float, default=-40.0,
        help=(
            "TX hardware gain dB. Must be ≤ −20 for Phase 4 initial tests. "
            "Start at −40 and increase in +5 dB steps only if tone is not visible."
        ),
    )
    p.add_argument(
        "--amplitude", type=float, default=0.1,
        help="IQ amplitude as fraction of DAC full scale — 0.0 to 1.0",
    )
    p.add_argument(
        "--yes-i-understand-rf-tx", action="store_true",
        help=(
            "Required safety gate. Pass this flag only after completing the "
            "pre-test checklist (docs/test_logs/phase4_prep_checklist.md). "
            "Without it the script prints configuration and exits."
        ),
    )
    return p.parse_args()


# ── Tone synthesis ─────────────────────────────────────────────────────────────

def _make_tone_buffer(
    tone_offset_hz: float,
    sample_rate: float,
    amplitude_fraction: float,
) -> "np.ndarray":
    """
    Return a complex64 IQ buffer sized to an integer number of tone cycles.
    Integer-cycle sizing eliminates the phase discontinuity at the cyclic
    buffer wrap-around point, keeping the spectral peak narrow and clean.
    """
    import numpy as np

    samples_per_cycle = sample_rate / abs(tone_offset_hz)
    # Target ~65536 samples; round to nearest integer number of full cycles
    n_cycles = max(1, round(65536 / samples_per_cycle))
    n = round(samples_per_cycle * n_cycles)

    t = np.arange(n, dtype=np.float64) / sample_rate
    scale = amplitude_fraction * _DAC_FULL_SCALE
    iq = scale * np.exp(1j * 2.0 * math.pi * tone_offset_hz * t)
    return iq.astype(np.complex64)


# ── TEST_LOG ──────────────────────────────────────────────────────────────────

def _append_testlog(status: str, label: str, notes: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 4A | TX tone (low power over-air) | "
        f"04_tx_tone_low_power.py | {status} | — | {notes} |"
    )
    try:
        existing = TEST_LOG.read_text(encoding="utf-8")
        TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"[warn] Could not write TEST_LOG: {exc}")


# ── TX hardware ────────────────────────────────────────────────────────────────

def _setup_tx(
    uri: str,
    freq: float,
    rate: float,
    tx_bw: float,
    tx_gain_db: float,
    n_samples: int,
):
    """Connect to PLUTO B and configure TX-only parameters. Does not touch RX."""
    import adi  # type: ignore

    sdr = adi.Pluto(uri=uri)
    sdr.tx_lo                 = int(freq)
    sdr.sample_rate           = int(rate)
    sdr.tx_rf_bandwidth       = int(tx_bw)
    sdr.tx_hardwaregain_chan0 = tx_gain_db
    sdr.tx_cyclic_buffer      = True
    sdr.tx_buffer_size        = n_samples
    return sdr


def _stop_tx(sdr) -> None:
    """Stop cyclic TX and release the DMA buffer. Safe to call at any time."""
    try:
        sdr.tx_destroy_buffer()
    except Exception as exc:
        print(f"[warn] tx_destroy_buffer: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import numpy as np  # imported here so missing-dep error is clear

    args = parse_args()
    will_tx = args.yes_i_understand_rf_tx

    # ── guard: amplitude ─────────────────────────────────────────────────────
    if not (0.0 < args.amplitude <= _MAX_AMPLITUDE):
        print(
            f"[error] --amplitude {args.amplitude} is out of range.\n"
            f"        Allowed: (0.0, {_MAX_AMPLITUDE}]"
        )
        sys.exit(1)

    # ── guard: TX gain ───────────────────────────────────────────────────────
    if args.tx_gain_db > -20.0:
        print(
            f"[error] --tx-gain-db {args.tx_gain_db} dB exceeds the Phase 4 limit of −20 dB.\n"
            "        Start at −40 dB. Increase in +5 dB steps only if the tone is not visible."
        )
        sys.exit(1)

    # ── configuration summary ────────────────────────────────────────────────
    center_mhz   = args.freq / 1e6
    tone_abs_mhz = (args.freq + args.tone_offset) / 1e6
    offset_khz   = args.tone_offset / 1e3

    print()
    print("=" * 66)
    print("  ORION Phase 4A — Low-Power Over-Air Tone TX")
    print("=" * 66)
    print(f"  TX device URI    : {args.uri}")
    print(f"  Label            : {args.label}")
    print(f"  TX LO (center)   : {center_mhz:.3f} MHz")
    print(f"  Tone offset      : +{offset_khz:.1f} kHz")
    print(f"  Tone absolute    : {tone_abs_mhz:.3f} MHz")
    print(f"  Sample rate      : {args.rate / 1e6:.3f} Msps")
    print(f"  TX bandwidth     : {args.tx_bw / 1e6:.3f} MHz")
    print(f"  TX hardware gain : {args.tx_gain_db:.1f} dB")
    print(f"  IQ amplitude     : {args.amplitude:.3f}  (DAC full scale = 1.0)")
    print(f"  Duration         : {args.duration:.1f} s")
    print()
    print("  ┌── PRE-TX SAFETY CHECKLIST (verify before transmitting) ─────────┐")
    print("  │  ✓  Small stock bench antenna installed on PLUTO B               │")
    print("  │  ✓  No coax cable between PLUTO A and PLUTO B                   │")
    print("  │  ✓  No amplifier, LNA, or external antenna connected             │")
    print("  │  ✓  No connection to IC-9100, rotator, or ground-station rack    │")
    print("  │  ✓  PLUTO A RX GUI running with a stable baseline spectrum       │")
    print("  │  ✓  Device spacing 1–3 m, no person within 30 cm of antennas    │")
    print("  └──────────────────────────────────────────────────────────────────┘")
    print()

    # ── dry run exit ─────────────────────────────────────────────────────────
    if not will_tx:
        print("  [DRY RUN] --yes-i-understand-rf-tx not set. No RF output.")
        print()
        print("  To transmit with these exact settings, run:")
        print(f"    python scripts\\04_tx_tone_low_power.py --yes-i-understand-rf-tx")
        print()
        print("  To override parameters:")
        print(
            f"    python scripts\\04_tx_tone_low_power.py"
            f" --tx-gain-db {args.tx_gain_db:.0f}"
            f" --duration {args.duration:.0f}"
            f" --yes-i-understand-rf-tx"
        )
        print()
        sys.exit(0)

    # ── generate tone buffer ─────────────────────────────────────────────────
    print("[init] Generating tone buffer ...")
    samples = _make_tone_buffer(args.tone_offset, args.rate, args.amplitude)
    peak_val = float(np.abs(samples).max())
    print(
        f"       {len(samples)} samples  |  "
        f"peak DAC value: {peak_val:.0f} / {_DAC_FULL_SCALE}  "
        f"({peak_val / _DAC_FULL_SCALE * 100:.1f}% of full scale)"
    )

    # ── TX sequence ──────────────────────────────────────────────────────────
    sdr = None
    aborted = False
    log_notes_started = (
        f"label={args.label} uri={args.uri} "
        f"freq={center_mhz:.3f}MHz offset=+{offset_khz:.0f}kHz "
        f"gain={args.tx_gain_db:.0f}dB amp={args.amplitude:.3f} "
        f"dur={args.duration:.1f}s"
    )

    try:
        print(f"[init] Connecting to {args.uri} ...")
        sdr = _setup_tx(
            args.uri, args.freq, args.rate,
            args.tx_bw, args.tx_gain_db, len(samples),
        )

        print(f"[init] Loading cyclic buffer ({len(samples)} samples) ...")
        sdr.tx(samples)

        ts_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print()
        print(f"  *** TX STARTED  {ts_start} ***")
        print(f"      Tone: {tone_abs_mhz:.3f} MHz  |  gain: {args.tx_gain_db:.0f} dB  |  {args.duration:.0f} s")
        print(f"      Watch PLUTO A GUI for a new peak near +{offset_khz:.0f} kHz offset.")
        print(f"      Press Ctrl+C to abort early.")
        print()
        _append_testlog("STARTED", args.label, log_notes_started)

        # ── timed wait ───────────────────────────────────────────────────────
        deadline = time.monotonic() + args.duration
        bar_width = 30
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            elapsed = args.duration - remaining
            filled = int(elapsed / args.duration * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(
                f"\r  [{bar}]  {elapsed:5.1f} / {args.duration:.0f} s",
                end="", flush=True,
            )
            time.sleep(min(0.25, remaining))

        print()  # end progress line

    except KeyboardInterrupt:
        aborted = True
        print()
        print("  [ABORT] Ctrl+C — stopping TX.")

    except Exception as exc:
        aborted = True
        print(f"\n  [error] {exc}")

    finally:
        if sdr is not None:
            print("[cleanup] Stopping cyclic TX buffer ...")
            _stop_tx(sdr)
            del sdr

        status = "ABORTED" if aborted else "STOPPED"
        ts_end = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"  *** TX {status}  {ts_end} ***")
        _append_testlog(status, args.label, f"label={args.label}")

    sys.exit(1 if aborted else 0)


if __name__ == "__main__":
    main()
