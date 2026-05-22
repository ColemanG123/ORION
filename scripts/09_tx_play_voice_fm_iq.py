#!/usr/bin/env python3
"""
09_tx_play_voice_fm_iq.py — ORION Phase 5C full-message chunked voice-FM TX.

Purpose:
  Safety-gated RF playback of a pre-generated complex FM voice IQ message from 149.

Default behavior:
  Dry-run only. No RF unless --yes-i-understand-rf-tx is supplied.

Operating model:
  - Load the full IQ message.
  - Verify the connected transmit device has serial suffix 149.
  - Stream fixed-size chunks in original message order.
  - When the full message ends, wrap back to the beginning.
  - Continue until --tx-duration expires.
  - Always call tx_destroy_buffer() on stop/error/abort.

This preserves the whole voice message instead of looping an arbitrary segment.

Boundary:
  Local 149-to-e9e bench testing only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEST_LOG = ROOT / "docs" / "test_logs" / "TEST_LOG.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION Phase 5C safety-gated full-message chunked voice-FM TX from 149.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--iq", required=True, help="Input complex64 IQ .npy file.")
    p.add_argument("--uri", default="usb:1.6.5", help="149 TX URI for this session.")
    p.add_argument("--expect-serial-suffix", default="149", help="Expected 149 serial suffix.")

    p.add_argument("--freq", type=float, default=915e6, help="TX LO frequency in Hz.")
    p.add_argument("--rate", type=int, default=1_000_000, help="TX sample rate in samples/s.")
    p.add_argument("--bandwidth", type=int, default=1_000_000, help="TX RF bandwidth in Hz.")
    p.add_argument("--gain-db", type=float, default=-40.0, help="TX hardware gain in dB.")

    p.add_argument("--tx-duration", type=float, default=8.0, help="RF-on duration in seconds.")
    p.add_argument("--chunk-samples", type=int, default=65536, help="Samples per streamed TX chunk.")
    p.add_argument("--max-amplitude", type=float, default=0.20, help="Maximum allowed normalized IQ abs amplitude.")
    p.add_argument("--dac-scale", type=float, default=16384.0, help="Scale normalized IQ to Pluto DAC units before TX.")
    p.add_argument("--max-tx-duration", type=float, default=20.0, help="Safety cap for TX duration.")

    p.add_argument("--yes-i-understand-rf-tx", action="store_true", help="Actually enable RF TX.")
    return p.parse_args()


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5C TX | Full-message chunked voice-FM TX from 149 | "
        f"09_tx_play_voice_fm_iq.py | {status} | {evidence} | {notes} |"
    )
    existing = TEST_LOG.read_text(encoding="utf-8") if TEST_LOG.exists() else ""
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


def check_serial(uri: str, expected_suffix: str) -> str:
    try:
        import iio
        ctx = iio.Context(uri)
        serial = ctx.attrs.get("hw_serial", "")
    except Exception as exc:
        raise RuntimeError(f"Could not open IIO context for serial check: {exc}")

    if not serial.endswith(expected_suffix):
        raise RuntimeError(
            f"Serial mismatch for {uri}. Expected suffix {expected_suffix}, got {serial!r}."
        )

    return serial


def load_iq(path: Path) -> np.ndarray:
    iq = np.load(path).astype(np.complex64).ravel()
    if len(iq) == 0:
        raise ValueError("Input IQ file is empty.")
    return iq


def next_chunk(iq: np.ndarray, start: int, chunk_samples: int) -> tuple[np.ndarray, int, bool]:
    """
    Return the next chunk in message order.

    If the chunk crosses the end of the message, wrap to the beginning and
    concatenate so the output chunk remains continuous in the intended message loop.

    Returns:
      chunk, next_start, wrapped
    """
    n = len(iq)
    stop = start + chunk_samples

    if stop < n:
        return iq[start:stop].astype(np.complex64), stop, False

    if stop == n:
        return iq[start:stop].astype(np.complex64), 0, True

    first = iq[start:n]
    remaining = stop - n
    second = iq[0:remaining]
    chunk = np.concatenate([first, second]).astype(np.complex64)
    return chunk, remaining, True


def main() -> None:
    args = parse_args()
    iq_path = Path(args.iq)

    if not iq_path.exists():
        print(f"[error] IQ file not found: {iq_path}")
        sys.exit(1)

    try:
        iq = load_iq(iq_path)
    except Exception as exc:
        print(f"[error] Could not load IQ: {exc}")
        sys.exit(1)

    full_duration = len(iq) / args.rate
    chunk_duration = args.chunk_samples / args.rate
    peak = float(np.max(np.abs(iq))) if len(iq) else 0.0
    expected_chunks = int(np.ceil(args.tx_duration / chunk_duration))

    print("=" * 72)
    print("ORION Phase 5C — Full-Message Chunked Voice-FM TX from 149")
    print("=" * 72)
    print("Default is dry-run. RF requires explicit confirmation.")
    print()
    print(f"IQ file             : {iq_path}")
    print(f"149 URI             : {args.uri}")
    print(f"Expected serial     : ...{args.expect_serial_suffix}")
    print(f"TX LO               : {args.freq/1e6:.6f} MHz")
    print(f"Sample rate         : {args.rate/1e6:.3f} Msps")
    print(f"Bandwidth           : {args.bandwidth/1e6:.3f} MHz")
    print(f"TX gain             : {args.gain_db:.1f} dB")
    print()
    print(f"Full IQ samples     : {len(iq)}")
    print(f"Full message length : {full_duration:.3f} s")
    print(f"Chunk samples       : {args.chunk_samples}")
    print(f"Chunk duration      : {chunk_duration*1000:.2f} ms")
    print(f"TX duration target  : {args.tx_duration:.3f} s")
    print(f"Approx. chunks      : {expected_chunks}")
    print(f"Approx. message reps: {args.tx_duration / full_duration:.2f}x")
    print(f"Peak |IQ| normalized: {peak:.4f}")
    print(f"Peak DAC estimate   : {peak * args.dac_scale:.1f} / 16384")
    print()

    if args.chunk_samples < 4096:
        print("[error] chunk-samples too small for this test. Use >=4096.")
        sys.exit(1)

    if args.chunk_samples > len(iq):
        print("[warn] chunk-samples is larger than the full message; using full message length.")
        args.chunk_samples = len(iq)

    if peak > args.max_amplitude:
        print(f"[error] IQ peak {peak:.4f} exceeds safety max {args.max_amplitude:.4f}")
        sys.exit(1)

    if args.gain_db > -30.0:
        print("[error] Refusing TX gain above -30 dB for this Phase 5C test.")
        sys.exit(1)

    if args.tx_duration <= 0 or args.tx_duration > args.max_tx_duration:
        print(f"[error] TX duration must be >0 and <= {args.max_tx_duration:.1f} seconds.")
        sys.exit(1)

    try:
        serial = check_serial(args.uri, args.expect_serial_suffix)
        print(f"[+] 149 serial check passed: {serial}")
    except Exception as exc:
        print(f"[error] {exc}")
        append_testlog("FAIL", str(iq_path), f"uri={args.uri} serial_check_failed={exc}")
        sys.exit(1)

    notes = (
        f"uri={args.uri} gain={args.gain_db:.1f}dB "
        f"tx_duration={args.tx_duration:.3f}s chunk={args.chunk_samples} "
        f"message={full_duration:.3f}s peak_norm={peak:.4f} dac_scale={args.dac_scale:.0f}"
    )

    if not args.yes_i_understand_rf_tx:
        print()
        print("[dry-run] RF TX NOT ENABLED.")
        print("To transmit, rerun with:")
        print("  --yes-i-understand-rf-tx")
        append_testlog("DRY RUN", str(iq_path), notes)
        return

    print()
    print("[tx] RF WILL ENABLE from 149. Confirm e9e observer is running.")
    print("[tx] Ctrl+C aborts; tx_destroy_buffer() will be called.")
    for k in range(5, 0, -1):
        print(f"  TX starts in {k}...")
        time.sleep(1.0)

    sdr = None
    sent_chunks = 0
    wraps = 0
    start_idx = 0
    tx_start = None

    try:
        import adi

        print("[tx] Connecting to 149...")
        sdr = adi.Pluto(args.uri)

        try:
            sdr.tx_destroy_buffer()
        except Exception:
            pass

        sdr.tx_lo = int(args.freq)
        sdr.sample_rate = int(args.rate)
        sdr.tx_rf_bandwidth = int(args.bandwidth)
        sdr.tx_hardwaregain_chan0 = float(args.gain_db)

        # Full-message streaming uses non-cyclic buffers.
        sdr.tx_cyclic_buffer = False

        append_testlog("STARTED", str(iq_path), notes)

        print("[tx] Streaming full message in chunks...")
        tx_start = time.perf_counter()
        deadline = tx_start + args.tx_duration

        while time.perf_counter() < deadline:
            chunk, start_idx, wrapped = next_chunk(iq, start_idx, args.chunk_samples)
            if wrapped:
                wraps += 1

            tx_chunk = (chunk * 16384).astype(np.complex64)
            sdr.tx(tx_chunk)
            sent_chunks += 1

            elapsed = time.perf_counter() - tx_start
            if sent_chunks % 10 == 0:
                print(
                    f"  elapsed={elapsed:6.2f}s  chunks={sent_chunks:4d}  "
                    f"wraps={wraps:3d}  next_idx={start_idx}",
                    end="\r",
                )

        elapsed = time.perf_counter() - tx_start
        print()
        print("[tx] Stop time reached. Destroying TX buffer...")

        try:
            sdr.tx_destroy_buffer()
        except Exception:
            pass

        append_testlog(
            "STOPPED",
            str(iq_path),
            notes + f" sent_chunks={sent_chunks} wraps={wraps} elapsed={elapsed:.3f}s",
        )

        print("[tx] Complete. TX buffer destroyed.")
        print(f"[tx] Elapsed      : {elapsed:.3f} s")
        print(f"[tx] Sent chunks  : {sent_chunks}")
        print(f"[tx] Message wraps: {wraps}")

    except KeyboardInterrupt:
        print()
        print("[tx] Operator abort.")
        if sdr is not None:
            try:
                sdr.tx_destroy_buffer()
            except Exception:
                pass
        append_testlog("ABORTED", str(iq_path), notes)
        sys.exit(1)

    except Exception as exc:
        print()
        print(f"[error] TX failed: {exc}")
        if sdr is not None:
            try:
                sdr.tx_destroy_buffer()
            except Exception:
                pass
        append_testlog("FAIL", str(iq_path), notes + f" error={exc}")
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
