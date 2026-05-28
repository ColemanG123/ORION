#!/usr/bin/env python3
"""
09_tx_play_voice_fm_iq.py — ORION Phase 5C voice-FM TX from 149.

Purpose:
  Safety-gated RF playback of a pre-generated complex FM voice IQ message from 149.

Default behavior:
  Dry-run only. No RF unless --yes-i-understand-rf-tx is supplied.

Identity rule:
  Use stable serial identity, not unstable USB paths.

  Default:
    --tx-id 149

  Optional debug override:
    --uri <current IIO URI>

TX modes:
  1. chunked
     - Streams fixed-size chunks from Python.
     - Preserves full message order and wraps in software.
     - Useful for debugging, but may create underruns/gaps.

  2. cyclic-full
     - Loads the entire IQ message as one cyclic TX buffer.
     - 149 hardware repeats the complete message until tx_destroy_buffer().
     - Preferred for Phase 5C voice-FM quality testing.

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
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion.pluto_identity import canonical_suffix, resolve_pluto_uri

TEST_LOG = ROOT / "docs" / "test_logs" / "TEST_LOG.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION Phase 5C safety-gated voice-FM TX from 149.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--iq", required=True, help="Input complex64 IQ .npy file.")

    p.add_argument(
        "--tx-id",
        default="149",
        help="Stable TX identity or serial suffix. Default is 149.",
    )
    p.add_argument(
        "--uri",
        default=None,
        help="Optional direct TX URI override for debugging. Normally omit this.",
    )
    p.add_argument(
        "--expect-serial-suffix",
        default=None,
        help="Optional expected TX serial suffix. Defaults to suffix implied by --tx-id.",
    )

    p.add_argument(
        "--tx-mode",
        choices=["chunked", "cyclic-full"],
        default="chunked",
        help="TX strategy. cyclic-full loads the entire message into one cyclic buffer.",
    )

    p.add_argument("--freq", type=float, default=915e6, help="TX LO frequency in Hz.")
    p.add_argument("--rate", type=int, default=1_000_000, help="TX sample rate in samples/s.")
    p.add_argument("--bandwidth", type=int, default=1_000_000, help="TX RF bandwidth in Hz.")
    p.add_argument("--gain-db", type=float, default=-40.0, help="TX hardware gain in dB.")

    p.add_argument("--tx-duration", type=float, default=8.0, help="RF-on duration in seconds.")
    p.add_argument("--chunk-samples", type=int, default=65_536, help="Samples per streamed TX chunk.")
    p.add_argument("--max-amplitude", type=float, default=0.20, help="Maximum allowed normalized IQ abs amplitude.")
    p.add_argument("--dac-scale", type=float, default=16_384.0, help="Scale normalized IQ to Pluto DAC units before TX.")
    p.add_argument("--max-tx-duration", type=float, default=20.0, help="Safety cap for TX duration.")

    p.add_argument(
        "--max-cyclic-samples",
        type=int,
        default=6_000_000,
        help="Safety cap for cyclic-full buffer length.",
    )

    p.add_argument("--yes-i-understand-rf-tx", action="store_true", help="Actually enable RF TX.")
    return p.parse_args()


def append_testlog(status: str, evidence: str, notes: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {ts} | Phase 5C TX | Voice-FM TX from 149 | "
        f"09_tx_play_voice_fm_iq.py | {status} | {evidence} | {notes} |"
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


def resolve_tx_uri(args: argparse.Namespace) -> tuple[str, str, str, str]:
    """
    Return (tx_uri, serial, model, expected_suffix).

    Normal path:
      --tx-id 149 -> resolve current URI by serial suffix.

    Debug path:
      --uri usb:x.y.z -> still verify serial suffix before any TX.
    """
    expected_suffix = args.expect_serial_suffix or canonical_suffix(args.tx_id)

    if args.uri:
        uri = args.uri
        serial, model = check_serial(uri, expected_suffix)
        return uri, serial, model, expected_suffix

    match = resolve_pluto_uri(args.tx_id, verbose=True)

    if not match.full_serial.lower().endswith(expected_suffix.lower()):
        raise RuntimeError(
            f"Resolver returned wrong serial for {args.tx_id}. "
            f"Expected ...{expected_suffix}, got {match.full_serial!r}."
        )

    return match.uri, match.full_serial, match.hw_model, expected_suffix


def load_iq(path: Path) -> np.ndarray:
    iq = np.load(path).astype(np.complex64).ravel()
    if len(iq) == 0:
        raise ValueError("Input IQ file is empty.")
    return iq


def next_chunk(iq: np.ndarray, start: int, chunk_samples: int) -> tuple[np.ndarray, int, bool]:
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


def configure_sdr(uri: str, freq: float, rate: int, bandwidth: int, gain_db: float):
    import adi

    sdr = adi.Pluto(uri)

    try:
        sdr.tx_destroy_buffer()
    except Exception:
        pass

    sdr.tx_lo = int(freq)
    sdr.sample_rate = int(rate)
    sdr.tx_rf_bandwidth = int(bandwidth)
    sdr.tx_hardwaregain_chan0 = float(gain_db)

    return sdr


def scaled_for_dac(iq: np.ndarray, dac_scale: float) -> np.ndarray:
    return (iq.astype(np.complex64) * float(dac_scale)).astype(np.complex64)


def print_summary(
    args: argparse.Namespace,
    iq_path: Path,
    iq: np.ndarray,
    tx_uri: str,
    tx_serial: str,
    tx_model: str,
    expected_suffix: str,
) -> None:
    full_duration = len(iq) / args.rate
    chunk_duration = args.chunk_samples / args.rate
    peak = float(np.max(np.abs(iq))) if len(iq) else 0.0
    expected_chunks = int(np.ceil(args.tx_duration / chunk_duration))

    print("=" * 72)
    print("ORION Phase 5C — Voice-FM TX from 149")
    print("=" * 72)
    print("Default is dry-run. RF requires explicit confirmation.")
    print()
    print(f"IQ file             : {iq_path}")
    print(f"TX identity         : {args.tx_id}")
    print(f"Resolved TX URI     : {tx_uri}")
    print(f"Resolved serial     : {tx_serial}")
    print(f"Resolved model      : {tx_model}")
    print(f"Expected serial     : ...{expected_suffix}")
    print(f"TX mode             : {args.tx_mode}")
    print(f"TX LO               : {args.freq/1e6:.6f} MHz")
    print(f"Sample rate         : {args.rate/1e6:.3f} Msps")
    print(f"Bandwidth           : {args.bandwidth/1e6:.3f} MHz")
    print(f"TX gain             : {args.gain_db:.1f} dB")
    print()
    print(f"Full IQ samples     : {len(iq)}")
    print(f"Full message length : {full_duration:.3f} s")
    print(f"TX duration target  : {args.tx_duration:.3f} s")
    print(f"Approx. message reps: {args.tx_duration / full_duration:.2f}x")
    print(f"Peak |IQ| normalized: {peak:.4f}")
    print(f"Peak DAC estimate   : {peak * args.dac_scale:.1f} / 16384")
    print()

    if args.tx_mode == "chunked":
        print(f"Chunk samples       : {args.chunk_samples}")
        print(f"Chunk duration      : {chunk_duration*1000:.2f} ms")
        print(f"Approx. chunks      : {expected_chunks}")
        print()
    else:
        approx_bytes = len(iq) * np.dtype(np.complex64).itemsize
        print("Cyclic buffer       : full message")
        print(f"Cyclic samples      : {len(iq)}")
        print(f"Cyclic payload      : {approx_bytes/1024/1024:.1f} MiB before driver handling")
        print()


def validate_args(args: argparse.Namespace, iq: np.ndarray) -> None:
    peak = float(np.max(np.abs(iq))) if len(iq) else 0.0

    if args.chunk_samples < 4096:
        raise ValueError("chunk-samples too small for this test. Use >=4096.")

    if peak > args.max_amplitude:
        raise ValueError(f"IQ peak {peak:.4f} exceeds safety max {args.max_amplitude:.4f}")

    if args.gain_db > -30.0:
        raise ValueError("Refusing TX gain above -30 dB for this Phase 5C test.")

    if args.tx_duration <= 0 or args.tx_duration > args.max_tx_duration:
        raise ValueError(f"TX duration must be >0 and <= {args.max_tx_duration:.1f} seconds.")

    if args.tx_mode == "cyclic-full" and len(iq) > args.max_cyclic_samples:
        raise ValueError(
            f"cyclic-full IQ length {len(iq)} exceeds max-cyclic-samples "
            f"{args.max_cyclic_samples}. Increase only after intentional review."
        )


def tx_chunked(args: argparse.Namespace, iq: np.ndarray, iq_path: Path, tx_uri: str, notes: str) -> None:
    sdr = None
    sent_chunks = 0
    wraps = 0
    start_idx = 0

    try:
        print("[tx] Connecting to 149...")
        sdr = configure_sdr(tx_uri, args.freq, args.rate, args.bandwidth, args.gain_db)
        sdr.tx_cyclic_buffer = False

        append_testlog("STARTED", str(iq_path), notes)

        print("[tx] Streaming full message in Python chunks...")
        tx_start = time.perf_counter()
        deadline = tx_start + args.tx_duration

        while time.perf_counter() < deadline:
            chunk, start_idx, wrapped = next_chunk(iq, start_idx, args.chunk_samples)
            if wrapped:
                wraps += 1

            tx_chunk = scaled_for_dac(chunk, args.dac_scale)
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


def tx_cyclic_full(args: argparse.Namespace, iq: np.ndarray, iq_path: Path, tx_uri: str, notes: str) -> None:
    sdr = None

    try:
        print("[tx] Connecting to 149...")
        sdr = configure_sdr(tx_uri, args.freq, args.rate, args.bandwidth, args.gain_db)

        print("[tx] Preparing full-message cyclic buffer...")
        tx_full = scaled_for_dac(iq, args.dac_scale)

        sdr.tx_cyclic_buffer = True

        append_testlog("STARTED", str(iq_path), notes)

        print("[tx] Loading full IQ message as cyclic buffer...")
        sdr.tx(tx_full)

        tx_start = time.perf_counter()
        deadline = tx_start + args.tx_duration

        print("[tx] Cyclic full-message RF is active.")
        while time.perf_counter() < deadline:
            elapsed = time.perf_counter() - tx_start
            remaining = max(0.0, deadline - time.perf_counter())
            reps = elapsed / (len(iq) / args.rate)
            print(
                f"  elapsed={elapsed:6.2f}s  approx_reps={reps:5.2f}  "
                f"remaining={remaining:5.2f}s",
                end="\r",
            )
            time.sleep(0.25)

        elapsed = time.perf_counter() - tx_start
        print()
        print("[tx] Stop time reached. Destroying cyclic TX buffer...")

        try:
            sdr.tx_destroy_buffer()
        except Exception:
            pass

        reps = elapsed / (len(iq) / args.rate)
        append_testlog(
            "STOPPED",
            str(iq_path),
            notes + f" cyclic_full elapsed={elapsed:.3f}s approx_reps={reps:.3f}",
        )

        print("[tx] Complete. Cyclic TX buffer destroyed.")
        print(f"[tx] Elapsed      : {elapsed:.3f} s")
        print(f"[tx] Approx reps  : {reps:.2f}")

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

    try:
        validate_args(args, iq)
    except Exception as exc:
        print(f"[error] {exc}")
        sys.exit(1)

    try:
        tx_uri, tx_serial, tx_model, expected_suffix = resolve_tx_uri(args)
    except Exception as exc:
        print(f"[error] {exc}")
        append_testlog("FAIL", str(iq_path), f"tx_id={args.tx_id} uri={args.uri} resolve_failed={exc}")
        sys.exit(1)

    print_summary(args, iq_path, iq, tx_uri, tx_serial, tx_model, expected_suffix)
    print(f"[+] 149 serial check passed: {tx_serial}")

    full_duration = len(iq) / args.rate
    peak = float(np.max(np.abs(iq))) if len(iq) else 0.0

    notes = (
        f"mode={args.tx_mode} tx_id={args.tx_id} resolved_uri={tx_uri} "
        f"serial={tx_serial} gain={args.gain_db:.1f}dB "
        f"tx_duration={args.tx_duration:.3f}s message={full_duration:.3f}s "
        f"peak_norm={peak:.4f} dac_scale={args.dac_scale:.0f}"
    )

    if args.tx_mode == "chunked":
        notes += f" chunk={args.chunk_samples}"

    if not args.yes_i_understand_rf_tx:
        print()
        print("[dry-run] RF TX NOT ENABLED.")
        print("To transmit, rerun with:")
        print("  --yes-i-understand-rf-tx")
        append_testlog("DRY RUN", str(iq_path), notes)
        return

    print()
    print("[tx] RF WILL ENABLE from 149. Confirm e9e observer/capture is running.")
    print("[tx] Ctrl+C aborts; tx_destroy_buffer() will be called.")
    for k in range(5, 0, -1):
        print(f"  TX starts in {k}...")
        time.sleep(1.0)

    if args.tx_mode == "chunked":
        tx_chunked(args, iq, iq_path, tx_uri, notes)
    elif args.tx_mode == "cyclic-full":
        tx_cyclic_full(args, iq, iq_path, tx_uri, notes)
    else:
        print(f"[error] Unknown tx-mode: {args.tx_mode}")
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()