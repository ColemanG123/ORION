"""
ORION — offline metrics helpers for RX spectrum probe captures.

No hardware access. Reads JSON metadata files written by 01_rx_spectrum_probe.py.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class CaptureRecord:
    # --- from JSON ---
    source_file: str
    label: str
    uri: str
    timestamp: str
    center_freq_hz: int
    sample_rate_hz: int
    rx_bw_hz: int
    gain_mode: str
    gain_db_manual: Optional[float]
    num_samples: int
    noise_floor_dbfs: float
    peak_dbfs: float
    peak_offset_mhz: float

    # --- derived ---
    peak_absolute_freq_mhz: float = field(init=False)
    peak_above_floor_db: float = field(init=False)

    def __post_init__(self) -> None:
        self.peak_absolute_freq_mhz = self.center_freq_hz / 1e6 + self.peak_offset_mhz
        self.peak_above_floor_db = self.peak_dbfs - self.noise_floor_dbfs


def _require(d: dict, key: str, src: str):
    if key not in d:
        raise KeyError(f"{src}: missing required field '{key}'")
    return d[key]


def load_captures(captures_dir: Path) -> list[CaptureRecord]:
    """
    Read all spectrum_*.json files from *captures_dir*.
    Returns records sorted by timestamp (ascending).
    Silently skips files that are missing required fields.
    """
    records: list[CaptureRecord] = []
    pattern = sorted(captures_dir.glob("spectrum_*.json"))

    for path in pattern:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            src = path.name
            rec = CaptureRecord(
                source_file      = src,
                label            = _require(raw, "label", src),
                uri              = _require(raw, "uri", src),
                timestamp        = _require(raw, "timestamp", src),
                center_freq_hz   = int(_require(raw, "center_freq_hz", src)),
                sample_rate_hz   = int(_require(raw, "sample_rate_hz", src)),
                rx_bw_hz         = int(_require(raw, "rx_bw_hz", src)),
                gain_mode        = _require(raw, "gain_mode", src),
                gain_db_manual   = raw.get("gain_db_manual"),
                num_samples      = int(_require(raw, "num_samples", src)),
                noise_floor_dbfs = float(_require(raw, "noise_floor_dbfs", src)),
                peak_dbfs        = float(_require(raw, "peak_dbfs", src)),
                peak_offset_mhz  = float(_require(raw, "peak_offset_mhz", src)),
            )
            records.append(rec)
        except Exception as exc:
            print(f"  [!] Skipping {path.name}: {exc}")

    records.sort(key=lambda r: r.timestamp)
    return records


@dataclass
class LabelStats:
    label: str
    n: int
    avg_noise_floor_dbfs: float
    std_noise_floor_dbfs: Optional[float]  # None when n < 2
    avg_peak_dbfs: float
    avg_above_floor_db: float
    avg_peak_offset_mhz: float
    std_peak_offset_mhz: Optional[float]
    uris: list[str]
    freq_mhz_set: list[float]


def per_label_stats(
    records: list[CaptureRecord],
    key: Callable[[CaptureRecord], str] | None = None,
) -> dict[str, LabelStats]:
    """
    Group records by label and compute summary statistics.

    Pass *key* to group by a derived name instead of the raw label, e.g.
    to collapse pluto_a_repeat → pluto_a while keeping capture table labels intact.
    """
    groups: dict[str, list[CaptureRecord]] = {}
    for r in records:
        group_key = key(r) if key else r.label
        groups.setdefault(group_key, []).append(r)

    result: dict[str, LabelStats] = {}
    for label, recs in sorted(groups.items()):
        floors  = [r.noise_floor_dbfs for r in recs]
        peaks   = [r.peak_dbfs for r in recs]
        aboves  = [r.peak_above_floor_db for r in recs]
        offsets = [r.peak_offset_mhz for r in recs]

        result[label] = LabelStats(
            label                = label,
            n                    = len(recs),
            avg_noise_floor_dbfs = statistics.mean(floors),
            std_noise_floor_dbfs = statistics.stdev(floors) if len(floors) >= 2 else None,
            avg_peak_dbfs        = statistics.mean(peaks),
            avg_above_floor_db   = statistics.mean(aboves),
            avg_peak_offset_mhz  = statistics.mean(offsets),
            std_peak_offset_mhz  = statistics.stdev(offsets) if len(offsets) >= 2 else None,
            uris                 = sorted(set(r.uri for r in recs)),
            freq_mhz_set         = sorted(set(r.center_freq_hz / 1e6 for r in recs)),
        )
    return result
