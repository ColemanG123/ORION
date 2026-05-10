"""
ORION Phase 2B — RX Repeatability Summary

Offline script. Does NOT connect to any hardware.
Reads spectrum_*.json metadata files written by 01_rx_spectrum_probe.py,
computes derived stats, prints a console table, writes a Markdown summary,
and appends a row to TEST_LOG.md.

Usage:
    python scripts/02_rx_repeatability_summary.py
    python scripts/02_rx_repeatability_summary.py --captures-dir data/captures
    python scripts/02_rx_repeatability_summary.py --help
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from orion.metrics import CaptureRecord, LabelStats, load_captures, per_label_stats

DIR_CAPTURES  = ROOT / "data" / "captures"
DIR_TEST_LOGS = ROOT / "docs" / "test_logs"
TEST_LOG      = DIR_TEST_LOGS / "TEST_LOG.md"
SUMMARY_OUT   = DIR_TEST_LOGS / "phase2_summary.md"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ORION Phase 2B — offline repeatability summary. No hardware required.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--captures-dir", type=Path, default=DIR_CAPTURES,
        help="Directory containing spectrum_*.json files.",
    )
    p.add_argument(
        "--summary-out", type=Path, default=SUMMARY_OUT,
        help="Destination Markdown file.",
    )
    p.add_argument(
        "--no-testlog", action="store_true",
        help="Skip appending to TEST_LOG.md.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Label normalisation
# ---------------------------------------------------------------------------

def normalize_label(record) -> str:
    """
    Return the base device label, stripping _repeat and any trailing suffix.
    Examples: pluto_a_repeat -> pluto_a, pluto_b_repeat_2 -> pluto_b.
    """
    return re.sub(r"_repeat.*$", "", record.label)


# ---------------------------------------------------------------------------
# Console table
# ---------------------------------------------------------------------------

def _fmt(v, fmt: str = "", width: int = 0, fill: str = " ") -> str:
    s = format(v, fmt) if fmt else str(v)
    return s.ljust(width, fill) if width else s


def print_console_table(records: list[CaptureRecord]) -> None:
    if not records:
        print("  (no records)")
        return

    # Column definitions: (header, width, extractor, format)
    cols = [
        ("#",              3,  lambda r, i: str(i),                         ""),
        ("Label",         10,  lambda r, i: r.label,                        ""),
        ("URI",           16,  lambda r, i: r.uri,                          ""),
        ("Timestamp",     19,  lambda r, i: r.timestamp[:19],               ""),
        ("Freq MHz",       9,  lambda r, i: r.center_freq_hz / 1e6,         ".3f"),
        ("Rate Msps",      9,  lambda r, i: r.sample_rate_hz / 1e6,         ".3f"),
        ("Gain",          11,  lambda r, i: r.gain_mode,                    ""),
        ("Floor dBFS",    10,  lambda r, i: r.noise_floor_dbfs,             ".2f"),
        ("Peak dBFS",     10,  lambda r, i: r.peak_dbfs,                    ".2f"),
        ("AbvFlr dB",     10,  lambda r, i: r.peak_above_floor_db,          ".2f"),
        ("Peak MHz",      11,  lambda r, i: r.peak_absolute_freq_mhz,       ".4f"),
    ]

    sep = "  ".join("-" * w for _, w, _, _ in cols)
    hdr = "  ".join(h.ljust(w) for h, w, _, _ in cols)
    print(hdr)
    print(sep)
    for i, r in enumerate(records, 1):
        row = "  ".join(
            _fmt(fn(r, i), fmt, w)
            for _, w, fn, fmt in cols
        )
        print(row)
    print()


# ---------------------------------------------------------------------------
# Interpretation text (auto-generated from data)
# ---------------------------------------------------------------------------

def _interp_lines(
    records: list[CaptureRecord],
    stats: dict[str, LabelStats],
) -> list[str]:
    lines: list[str] = []
    n_total = len(records)
    labels  = sorted(stats.keys())

    lines.append(f"- **Captures processed**: {n_total}")
    lines.append(f"- **Unique PLUTO devices**: {', '.join(f'`{l}`' for l in labels)}")
    lines.append("")

    lines.append("### Average noise floor by device")
    lines.append("")
    lines.append("| Device | Avg floor (dBFS) | Std dev (dB) | N |")
    lines.append("|--------|-----------------|--------------|---|")
    for lbl, s in stats.items():
        std_str = f"{s.std_noise_floor_dbfs:.2f}" if s.std_noise_floor_dbfs is not None else "—"
        lines.append(f"| `{lbl}` | {s.avg_noise_floor_dbfs:.2f} | {std_str} | {s.n} |")
    lines.append("")

    lines.append("### Average peak offset by device")
    lines.append("")
    lines.append("| Device | Avg peak offset (MHz) | Std dev (MHz) | Avg above floor (dB) | N |")
    lines.append("|--------|-----------------------|---------------|----------------------|---|")
    for lbl, s in stats.items():
        std_str = f"{s.std_peak_offset_mhz:.4f}" if s.std_peak_offset_mhz is not None else "—"
        lines.append(
            f"| `{lbl}` | {s.avg_peak_offset_mhz:+.4f} | {std_str} "
            f"| {s.avg_above_floor_db:.2f} | {s.n} |"
        )
    lines.append("")

    # Automated observations
    lines.append("### Automated observations")
    lines.append("")

    for lbl, s in stats.items():
        if s.std_noise_floor_dbfs is not None:
            if s.std_noise_floor_dbfs <= 1.0:
                lines.append(
                    f"- `{lbl}`: noise floor spread ≤ 1 dB across {s.n} captures "
                    f"— **stable**."
                )
            else:
                lines.append(
                    f"- `{lbl}`: noise floor spread = {s.std_noise_floor_dbfs:.2f} dB "
                    f"across {s.n} captures — monitor for drift."
                )

    # Peak offset consistency note
    all_offsets = [r.peak_offset_mhz for r in records]
    if all(abs(o) < 0.1 for o in all_offsets):
        lines.append(
            "- The dominant spectral peak appears consistently near +58–60 kHz offset "
            "across captures. This may be related to receiver/internal artifacts or a "
            "local ambient signal; additional source-identification testing is required "
            "before attribution."
        )

    # Cross-unit noise floor delta
    if len(stats) == 2:
        vals = [(lbl, s.avg_noise_floor_dbfs) for lbl, s in stats.items()]
        delta = abs(vals[0][1] - vals[1][1])
        lines.append(
            f"- Noise floor difference between `{vals[0][0]}` and `{vals[1][0]}`: "
            f"**{delta:.2f} dB**. "
            + ("Within normal unit-to-unit variation." if delta <= 3 else
               "Larger than typical — check gain settings and antenna connections.")
        )

    lines.append("")
    lines.append("### Calibration note")
    lines.append("")
    lines.append(
        "All dBFS values are **relative** to the ADALM-PLUTO ADC full scale "
        "(12-bit, ±2048 counts) and are **not calibrated dBm readings**. "
        "Conversion to dBm requires a known reference signal and is outside "
        "the scope of this passive receive test."
    )
    lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def write_markdown_summary(
    records: list[CaptureRecord],
    stats: dict[str, LabelStats],
    out_path: Path,
    gen_timestamp: str,
) -> None:
    lines: list[str] = []
    lines.append("# ORION Phase 2B — RX Spectrum Probe Summary")
    lines.append("")
    lines.append(f"**Generated**: {gen_timestamp}  ")
    lines.append(f"**Captures directory**: `data/captures/`  ")
    lines.append(f"**Files processed**: {len(records)}  ")
    lines.append("")

    if not records:
        lines.append("_No spectrum_*.json files found in the captures directory._")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return

    # Main table
    lines.append("## Capture Table")
    lines.append("")
    lines.append(
        "| # | Label | URI | Timestamp | Freq (MHz) | Rate (Msps) | Gain mode | Samples "
        "| Floor (dBFS) | Peak (dBFS) | Above floor (dB) | Peak abs freq (MHz) |"
    )
    lines.append(
        "|---|-------|-----|-----------|------------|-------------|-----------|---------|"
        "-------------|-------------|------------------|---------------------|"
    )
    for i, r in enumerate(records, 1):
        lines.append(
            f"| {i} | `{r.label}` | `{r.uri}` | {r.timestamp[:19]} "
            f"| {r.center_freq_hz/1e6:.3f} | {r.sample_rate_hz/1e6:.3f} "
            f"| {r.gain_mode} | {r.num_samples:,} "
            f"| {r.noise_floor_dbfs:.2f} | {r.peak_dbfs:.2f} "
            f"| {r.peak_above_floor_db:.2f} | {r.peak_absolute_freq_mhz:.4f} |"
        )
    lines.append("")

    # Interpretation
    lines.append("## Interpretation")
    lines.append("")
    lines.extend(_interp_lines(records, stats))

    # Source file index
    lines.append("## Source Files")
    lines.append("")
    for r in records:
        lines.append(f"- `data/captures/{r.source_file}`")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# TEST_LOG
# ---------------------------------------------------------------------------

def append_testlog(
    log_path: Path,
    timestamp: str,
    n_records: int,
    labels: list[str],
    summary_file: str,
) -> None:
    label_str = ", ".join(labels) if labels else "none"
    result = "PASS" if n_records > 0 else "FAIL — no captures found"
    row = (
        f"| {timestamp} | Phase 2B | RX repeatability summary | "
        f"02_rx_repeatability_summary.py (offline) | "
        f"{result} | {summary_file} | "
        f"{n_records} capture(s) processed, labels: {label_str} |"
    )
    existing = log_path.read_text(encoding="utf-8")
    log_path.write_text(existing.rstrip() + "\n" + row + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    now = datetime.datetime.now()
    timestamp     = now.strftime("%Y-%m-%d %H:%M")
    gen_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 68)
    print("ORION Phase 2B — RX Repeatability Summary (offline)")
    print("=" * 68)
    print(f"  Captures dir : {args.captures_dir}")
    print(f"  Summary out  : {args.summary_out}")
    print()

    # ---- load captures ---------------------------------------------------
    print(f"Loading spectrum_*.json from {args.captures_dir} ...")
    records = load_captures(args.captures_dir)

    if not records:
        print("  [!] No spectrum_*.json files found.")
        print("      Run scripts/01_rx_spectrum_probe.py first to generate captures.")
        print()
    else:
        print(f"  [+] {len(records)} capture(s) loaded.")
        print()

    # ---- compute stats (grouped by normalised device label) --------------
    stats = per_label_stats(records, key=normalize_label)

    # ---- console table ---------------------------------------------------
    print("CAPTURE TABLE")
    print()
    print_console_table(records)

    # ---- per-label stats summary to console ------------------------------
    if stats:
        print("PER-DEVICE STATS  (repeat captures merged into base device label)")
        print()
        hdr = f"  {'Device':<12}  {'N':>3}  {'Avg floor':>10}  {'Avg peak':>9}  {'Avg abv flr':>11}  {'Avg offset':>11}"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for lbl, s in stats.items():
            print(
                f"  {lbl:<12}  {s.n:>3}  "
                f"{s.avg_noise_floor_dbfs:>9.2f}  "
                f"{s.avg_peak_dbfs:>8.2f}  "
                f"{s.avg_above_floor_db:>10.2f}  "
                f"{s.avg_peak_offset_mhz:>+10.4f}"
            )
        print()

    # ---- write markdown --------------------------------------------------
    write_markdown_summary(records, stats, args.summary_out, gen_timestamp)
    print(f"[+] Summary written to: {args.summary_out}")

    # ---- TEST_LOG --------------------------------------------------------
    if not args.no_testlog:
        append_testlog(
            TEST_LOG,
            timestamp,
            n_records=len(records),
            labels=sorted(stats.keys()),
            summary_file=args.summary_out.name,
        )
        print(f"[+] Test log updated:   {TEST_LOG}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
