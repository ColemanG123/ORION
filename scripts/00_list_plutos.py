"""
ORION Phase 1B — ADALM-PLUTO detection and unique-device identification.

Read-only. No transmission. No hardware reconfiguration.
No frequency, gain, sample rate, bandwidth, or buffer settings are touched.

Usage:
    python scripts/00_list_plutos.py
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orion.devices import (
    CANDIDATE_URIS,
    disambiguate,
    discover_plutos,
    print_comparison_table,
    probe_imports,
    print_import_status,
    results_to_markdown,
    scan_iio_contexts,
    testlog_row,
    _conclusion_note,
)

HARDWARE_STATUS = Path(__file__).parent.parent / "docs" / "test_logs" / "hardware_status.md"
TEST_LOG        = Path(__file__).parent.parent / "docs" / "test_logs" / "TEST_LOG.md"


def main() -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------------
    # 1. Import availability
    # ------------------------------------------------------------------
    print("=" * 72)
    print("ORION Phase 1B — ADALM-PLUTO Unique-Device Identification")
    print("=" * 72)
    print()
    print("Checking Python package availability ...")
    availability = probe_imports()
    print_import_status(availability)
    print()

    if not availability.get("iio"):
        print("[!] iio not available — cannot probe IIO contexts.")
        print("    Install libiio and pylibiio, then re-run.")
        print()

    # ------------------------------------------------------------------
    # 2. IIO context scan (passive)
    # ------------------------------------------------------------------
    print("Scanning for IIO contexts (passive) ...")
    scanned = scan_iio_contexts()
    if scanned:
        print(f"  [+] iio_scan found {len(scanned)} context(s):")
        for u in scanned:
            print(f"        {u}")
    else:
        print("  [-] iio_scan returned no contexts")
    print()

    # ------------------------------------------------------------------
    # 3. Probe all candidate URIs
    # ------------------------------------------------------------------
    print(f"Probing {len(CANDIDATE_URIS)} candidate URI(s) "
          f"(+ {len(scanned)} from scan) ...")
    print()
    results = discover_plutos()

    for r in results:
        if r.connected:
            print(f"  [+] {r.uri}")
            if r.hw_serial:
                print(f"        hw_serial   : {r.hw_serial}  ← primary ID")
            if r.hw_model:
                print(f"        hw_model    : {r.hw_model}")
            if r.dna:
                print(f"        dna         : {r.dna}")
            if r.serial:
                print(f"        serial      : {r.serial}")
            if r.firmware:
                print(f"        firmware    : {r.firmware}")
            if r.usb_path:
                print(f"        USB path    : {r.usb_path}")
            if r.ip_addr:
                print(f"        IP/hostname : {r.ip_addr}")
            if r.ctx_attrs:
                print(f"        ctx attrs   : {dict(sorted(r.ctx_attrs.items()))}")
            if r.device_name:
                print(f"        description : {r.device_name}")
            if r.fingerprint:
                print(f"        fingerprint : {r.fingerprint}")
        else:
            msg = f"  [-] {r.uri}"
            if r.error:
                msg += f"  ({r.error})"
            print(msg)
        print()

    # ------------------------------------------------------------------
    # 4. Comparison table
    # ------------------------------------------------------------------
    print("-" * 72)
    print("COMPARISON TABLE")
    print()
    print_comparison_table(results)
    print()

    # ------------------------------------------------------------------
    # 5. Disambiguation
    # ------------------------------------------------------------------
    conclusion, groups = disambiguate(results)

    print("-" * 72)
    print(f"CONCLUSION:  {conclusion}")
    print()
    print(_conclusion_note(conclusion, groups))
    print()

    if groups:
        print("Physical device groups:")
        for i, (fp, uris) in enumerate(groups.items(), 1):
            print(f"  Device {i}  fingerprint={fp}")
            for u in uris:
                print(f"    alias: {u}")
        print()

    # ------------------------------------------------------------------
    # 6. Write hardware_status.md
    # ------------------------------------------------------------------
    md_content = results_to_markdown(availability, results, conclusion, groups, timestamp)
    HARDWARE_STATUS.write_text(md_content, encoding="utf-8")
    print(f"[+] Hardware status written to: {HARDWARE_STATUS}")

    # ------------------------------------------------------------------
    # 7. Append to TEST_LOG.md
    # ------------------------------------------------------------------
    row = testlog_row(results, conclusion, timestamp)
    existing = TEST_LOG.read_text(encoding="utf-8")
    TEST_LOG.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")
    print(f"[+] Test log entry appended to:  {TEST_LOG}")
    print()


if __name__ == "__main__":
    main()
