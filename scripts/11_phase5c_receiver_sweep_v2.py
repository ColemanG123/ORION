#!/usr/bin/env python3
"""
11_phase5c_receiver_sweep_v2.py — ORION Phase 5C focused receiver sweep.

Purpose
-------
Focused follow-up sweep after v1 showed:

- p02_lp9_limited_clean was clearer/louder/crisper, but shriller.
- p10_lp12_clean3200 was more balanced, but still static.
- Heavy de-emphasis helped metrics but made voice too quiet/muffled.

This v2 sweep searches between p02 and p10:
- channel cutoff: 9–12 kHz
- clean highcut: 3000–3400 Hz
- light de-emphasis only: 0, 25, 50 us
- limiter on
- 2148 Hz notch on
- trim 0.8–1.1 s

Boundary
--------
Offline analysis only. No SDR. No RF.

Typical use from E:\\ORION
--------------------------
python scripts\\11_phase5c_receiver_sweep_v2.py --iq data\\captures\\voice_rx_e9e_149_comms_voice_rx_20260522_170524.npy

Then open:
data\\audio\\sweeps\\phase5c_receiver_sweep_v2_<timestamp>\\LISTENING_INDEX.md
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile


ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
CAPTURE_DIR = ROOT / "data" / "captures"
SCRIPT_10 = ROOT / "scripts" / "10_demod_voice_fm_capture.py"


@dataclass(frozen=True)
class ReceiverProfile:
    name: str
    expected_offset: float = 110000.0
    offset_span: float = 12000.0
    offset_step: float = 250.0
    analysis_band: float = 9000.0
    deviation: float = 5000.0
    channel_cutoff: float = 12000.0
    demod_rate: int = 100000
    lowcut: float = 100.0
    highcut: float = 3400.0
    force_start: float = 6.4
    force_stop: float = 12.0
    trim_active_start: float = 0.8
    notch_hz: tuple[float, ...] = (2148.0,)
    notch_q: float = 35.0
    clean_lowcut: float = 80.0
    clean_highcut: float = 3200.0
    deemphasis_us: float = 0.0
    no_limiter: bool = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Focused Phase 5C receiver sweep between p02 clarity and p10 balance.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--iq", default=None, help="Input e9e RX IQ .npy. Defaults to newest comms capture.")
    p.add_argument("--limit", type=int, default=0, help="Run only first N profiles. 0 = all.")
    p.add_argument("--python", default=sys.executable, help="Python executable.")
    p.add_argument("--dry-run", action="store_true", help="Print commands without running.")
    return p.parse_args()


def newest_capture() -> Path:
    candidates = sorted(
        CAPTURE_DIR.glob("voice_rx_e9e_149_comms_voice_rx_*.npy"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No voice_rx_e9e_149_comms_voice_rx_*.npy capture found.")
    return candidates[0]


def make_profiles() -> list[ReceiverProfile]:
    base = dict(
        expected_offset=110000.0,
        offset_span=12000.0,
        offset_step=250.0,
        deviation=5000.0,
        force_start=6.4,
        force_stop=12.0,
        notch_hz=(2148.0,),
        notch_q=35.0,
        clean_lowcut=80.0,
        no_limiter=False,
    )

    profiles: list[ReceiverProfile] = [
        # p02-like clarity, but tame shrillness.
        ReceiverProfile("v2_01_cut9_ch3000", analysis_band=8000, channel_cutoff=9000, demod_rate=100000,
                        lowcut=120, highcut=3000, clean_highcut=3000, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_02_cut9_ch3200", analysis_band=8000, channel_cutoff=9000, demod_rate=100000,
                        lowcut=120, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_03_cut9_ch3300", analysis_band=8000, channel_cutoff=9000, demod_rate=100000,
                        lowcut=100, highcut=3300, clean_highcut=3300, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_04_cut9_deemp25", analysis_band=8000, channel_cutoff=9000, demod_rate=100000,
                        lowcut=120, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=25, **base),
        ReceiverProfile("v2_05_cut9_deemp50", analysis_band=8000, channel_cutoff=9000, demod_rate=100000,
                        lowcut=120, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=50, **base),

        # Intermediate channel widths between p02 and p10.
        ReceiverProfile("v2_06_cut10_ch3200", analysis_band=8500, channel_cutoff=10000, demod_rate=100000,
                        lowcut=110, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_07_cut10_ch3300", analysis_band=8500, channel_cutoff=10000, demod_rate=100000,
                        lowcut=100, highcut=3300, clean_highcut=3300, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_08_cut10_deemp25", analysis_band=8500, channel_cutoff=10000, demod_rate=100000,
                        lowcut=110, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=25, **base),
        ReceiverProfile("v2_09_cut10_trim1p0", analysis_band=8500, channel_cutoff=10000, demod_rate=100000,
                        lowcut=110, highcut=3200, clean_highcut=3200, trim_active_start=1.0, deemphasis_us=0, **base),

        ReceiverProfile("v2_10_cut11_ch3200", analysis_band=9000, channel_cutoff=11000, demod_rate=100000,
                        lowcut=100, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_11_cut11_ch3300", analysis_band=9000, channel_cutoff=11000, demod_rate=100000,
                        lowcut=100, highcut=3300, clean_highcut=3300, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_12_cut11_deemp25", analysis_band=9000, channel_cutoff=11000, demod_rate=100000,
                        lowcut=100, highcut=3300, clean_highcut=3300, trim_active_start=0.8, deemphasis_us=25, **base),
        ReceiverProfile("v2_13_cut11_trim1p0", analysis_band=9000, channel_cutoff=11000, demod_rate=100000,
                        lowcut=100, highcut=3300, clean_highcut=3300, trim_active_start=1.0, deemphasis_us=0, **base),

        # p10-like balance; test if slight variants can keep clarity without shrillness.
        ReceiverProfile("v2_14_cut12_ch3200", analysis_band=9000, channel_cutoff=12000, demod_rate=100000,
                        lowcut=100, highcut=3400, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_15_cut12_ch3300", analysis_band=9000, channel_cutoff=12000, demod_rate=100000,
                        lowcut=100, highcut=3400, clean_highcut=3300, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_16_cut12_deemp25", analysis_band=9000, channel_cutoff=12000, demod_rate=100000,
                        lowcut=100, highcut=3400, clean_highcut=3300, trim_active_start=0.8, deemphasis_us=25, **base),
        ReceiverProfile("v2_17_cut12_trim1p0", analysis_band=9000, channel_cutoff=12000, demod_rate=100000,
                        lowcut=100, highcut=3400, clean_highcut=3200, trim_active_start=1.0, deemphasis_us=0, **base),

        # One demod-rate check in the promising region.
        ReceiverProfile("v2_18_cut10_demod80k", analysis_band=8500, channel_cutoff=10000, demod_rate=80000,
                        lowcut=110, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=0, **base),
        ReceiverProfile("v2_19_cut10_demod160k", analysis_band=8500, channel_cutoff=10000, demod_rate=160000,
                        lowcut=110, highcut=3200, clean_highcut=3200, trim_active_start=0.8, deemphasis_us=0, **base),
    ]
    return profiles


def build_command(py: str, iq_path: Path, profile: ReceiverProfile) -> list[str]:
    cmd = [
        py,
        str(SCRIPT_10),
        "--iq", str(iq_path),
        "--label", profile.name,
        "--rate", "1000000",
        "--expected-offset", str(profile.expected_offset),
        "--offset-span", str(profile.offset_span),
        "--offset-step", str(profile.offset_step),
        "--analysis-band", str(profile.analysis_band),
        "--deviation", str(profile.deviation),
        "--channel-cutoff", str(profile.channel_cutoff),
        "--demod-rate", str(profile.demod_rate),
        "--lowcut", str(profile.lowcut),
        "--highcut", str(profile.highcut),
        "--force-start", str(profile.force_start),
        "--force-stop", str(profile.force_stop),
        "--trim-active-start", str(profile.trim_active_start),
        "--notch-q", str(profile.notch_q),
        "--clean-lowcut", str(profile.clean_lowcut),
        "--clean-highcut", str(profile.clean_highcut),
        "--deemphasis-us", str(profile.deemphasis_us),
    ]
    for hz in profile.notch_hz:
        cmd += ["--notch-hz", str(hz)]
    if profile.no_limiter:
        cmd.append("--no-limiter")
    return cmd


def newest_output_json(label: str, before: set[Path]) -> Path | None:
    after = set(AUDIO_DIR.glob(f"rx_voice_fm_{label}_*.json"))
    new = list(after - before)
    candidates = new if new else list(after)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def read_wav_float(path: Path) -> tuple[int, np.ndarray]:
    sr, x = wavfile.read(path)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if np.issubdtype(x.dtype, np.integer):
        x = x.astype(np.float32) / np.iinfo(x.dtype).max
    else:
        x = x.astype(np.float32)
    return int(sr), x


def integrate_power(y: np.ndarray, x: np.ndarray) -> float:
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    return float(np.trapz(y, x))


def band_power(f: np.ndarray, P: np.ndarray, lo: float, hi: float) -> float:
    mask = (f >= lo) & (f < hi)
    if not np.any(mask):
        return 0.0
    return integrate_power(P[mask], f[mask])


def db(x: float) -> float:
    return float(10.0 * np.log10(max(float(x), 1e-30)))


def audio_metrics(wav_path: Path) -> dict[str, float | str]:
    if not wav_path.exists():
        return {"error": f"missing {wav_path}"}

    sr, x = read_wav_float(wav_path)
    if len(x) < sr // 2:
        return {"error": "too short"}

    x = x - float(np.mean(x))
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x * x)))
    crest = peak / rms if rms > 0 else 0.0

    nperseg = min(8192, len(x))
    f, P = signal.welch(x, fs=sr, nperseg=nperseg)

    speech = (
        band_power(f, P, 100, 300)
        + band_power(f, P, 300, 1000)
        + band_power(f, P, 1000, 2200)
        + band_power(f, P, 2200, 3400)
    )
    hi_noise = band_power(f, P, 3400, 7000)
    drone = band_power(f, P, 2100, 2190)
    upper_speech = band_power(f, P, 1800, 3400)
    low_cloud = band_power(f, P, 100, 700)

    return {
        "peak": peak,
        "rms": rms,
        "crest": crest,
        "speech_to_hi_noise_db": db(speech) - db(hi_noise),
        "drone_to_speech_db": db(drone) - db(speech),
        "upper_speech_to_total_speech_db": db(upper_speech) - db(speech),
        "low_cloud_to_speech_db": db(low_cloud) - db(speech),
    }


def copy_artifacts(meta: dict, outdir: Path, profile_name: str) -> dict[str, str]:
    copied: dict[str, str] = {}
    keys = ["raw_active_wav", "limited_active_wav", "limited_cleaned_active_wav", "plot_path"]
    for key in keys:
        rel = meta.get(key)
        if not rel:
            continue
        src = ROOT / rel
        if not src.exists():
            continue
        dst = outdir / f"{profile_name}_{key}{src.suffix}"
        shutil.copy2(src, dst)
        copied[key] = str(dst.relative_to(ROOT))
    return copied


def main() -> None:
    args = parse_args()

    if not SCRIPT_10.exists():
        raise FileNotFoundError(f"Missing {SCRIPT_10}")

    iq_path = Path(args.iq) if args.iq else newest_capture()
    if not iq_path.is_absolute():
        iq_path = (ROOT / iq_path).resolve()
    if not iq_path.exists():
        raise FileNotFoundError(f"Missing IQ capture: {iq_path}")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = AUDIO_DIR / "sweeps" / f"phase5c_receiver_sweep_v2_{timestamp}"
    outdir.mkdir(parents=True, exist_ok=True)

    profiles = make_profiles()
    if args.limit and args.limit > 0:
        profiles = profiles[: args.limit]

    print("=" * 72)
    print("ORION Phase 5C Receiver Sweep V2")
    print("=" * 72)
    print(f"IQ capture : {iq_path}")
    print(f"Profiles   : {len(profiles)}")
    print(f"Output dir : {outdir}")
    print("Goal       : p02 clarity without p02 shrillness")
    print()

    rows: list[dict] = []
    report: dict = {
        "timestamp": timestamp,
        "iq_capture": str(iq_path),
        "profiles": [],
        "note": "Focused offline receiver sweep between p02 clarity and p10 balance. No SDR. No RF.",
    }

    for i, profile in enumerate(profiles, start=1):
        print(f"\n[{i}/{len(profiles)}] {profile.name}")
        before_jsons = set(AUDIO_DIR.glob(f"rx_voice_fm_{profile.name}_*.json"))
        cmd = build_command(args.python, iq_path, profile)
        print(" ".join(f'"{c}"' if " " in c else c for c in cmd))

        if args.dry_run:
            continue

        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            rows.append({"profile": profile.name, "status": "FAIL", "error": result.stderr[-1200:]})
            continue

        json_path = newest_output_json(profile.name, before_jsons)
        if json_path is None:
            rows.append({"profile": profile.name, "status": "NO_JSON"})
            continue

        meta = json.loads(json_path.read_text(encoding="utf-8"))
        wav_rel = meta.get("limited_cleaned_active_wav")
        wav_path = ROOT / wav_rel if wav_rel else None
        metrics = audio_metrics(wav_path) if wav_path else {"error": "no cleaned wav"}

        copied = copy_artifacts(meta, outdir, profile.name)

        row = {
            "profile": profile.name,
            "status": "OK",
            "best_offset_hz": meta.get("best_offset_hz"),
            "channel_snr_db": meta.get("channel_snr_db_active_vs_baseline"),
            "channel_cutoff_hz": profile.channel_cutoff,
            "analysis_band": profile.analysis_band,
            "demod_rate": profile.demod_rate,
            "deemphasis_us": profile.deemphasis_us,
            "clean_highcut": profile.clean_highcut,
            "trim_active_start": profile.trim_active_start,
            "notch_hz": ";".join(str(x) for x in profile.notch_hz),
            "json": str(json_path.relative_to(ROOT)),
            "limited_cleaned_active_wav": wav_rel,
            **metrics,
            **{f"copied_{k}": v for k, v in copied.items()},
        }
        rows.append(row)

        report["profiles"].append({
            "profile": asdict(profile),
            "metadata": meta,
            "metrics": metrics,
            "copied_artifacts": copied,
        })

    ok_rows = [r for r in rows if r.get("status") == "OK" and "error" not in r]

    for r in ok_rows:
        # This score is only a listening-order hint.
        # It avoids over-rewarding heavy de-emphasis, and gives a small penalty to profiles
        # likely to sound shrill (too much upper speech energy).
        speech_noise = float(r.get("speech_to_hi_noise_db", 0.0))
        drone = float(r.get("drone_to_speech_db", 0.0))
        upper = float(r.get("upper_speech_to_total_speech_db", 0.0))
        r["auto_score_v2"] = speech_noise - 0.18 * max(drone, -60.0) - 0.10 * max(upper + 3.0, 0.0)

    ranked = sorted(ok_rows, key=lambda r: float(r.get("auto_score_v2", -999)), reverse=True)

    csv_path = outdir / "receiver_sweep_v2_summary.csv"
    if rows:
        fieldnames = sorted({k for r in rows for k in r.keys()})
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    json_path = outdir / "receiver_sweep_v2_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_path = outdir / "LISTENING_INDEX.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# ORION Phase 5C Receiver Sweep V2 Listening Index\n\n")
        f.write(f"- IQ capture: `{iq_path}`\n")
        f.write(f"- Generated: `{timestamp}`\n")
        f.write("- Goal: p02 clarity without p02 shrillness.\n\n")
        f.write("## Suggested listening order\n\n")
        if ranked:
            for rank, r in enumerate(ranked[:10], start=1):
                wav = r.get("copied_limited_cleaned_active_wav") or r.get("limited_cleaned_active_wav")
                f.write(f"{rank}. **{r['profile']}** — `{wav}`\n")
                f.write(
                    f"   - cutoff={float(r.get('channel_cutoff_hz', 0))/1000:.1f} kHz, "
                    f"deemp={float(r.get('deemphasis_us', 0)):.0f} us, "
                    f"clean_highcut={float(r.get('clean_highcut', 0)):.0f} Hz, "
                    f"offset={float(r.get('best_offset_hz', 0))/1000:+.2f} kHz\n"
                )
                f.write(
                    f"   - speech/noise={float(r.get('speech_to_hi_noise_db', 0)):.1f} dB, "
                    f"drone/speech={float(r.get('drone_to_speech_db', 0)):.1f} dB, "
                    f"upper/speech={float(r.get('upper_speech_to_total_speech_db', 0)):.1f} dB\n"
                )
        else:
            f.write("No successful profiles.\n")

        f.write("\n## Human scoring notes\n\n")
        f.write("For the top 5–8 files, write quick notes:\n\n")
        f.write("| Profile | Voice volume | Clarity | Shrillness | Static cloud | Overall |\n")
        f.write("|---|---:|---:|---:|---:|---:|\n")
        for r in ranked[:8]:
            f.write(f"| {r['profile']} |  |  |  |  |  |\n")

    print("\n" + "=" * 72)
    print("SWEEP V2 COMPLETE")
    print("=" * 72)
    print(f"Summary CSV      : {csv_path}")
    print(f"Full JSON report : {json_path}")
    print(f"Listening index  : {md_path}")
    print("\nTop candidates:")
    for r in ranked[:8]:
        print(
            f"  {r['profile']:<22} "
            f"score={float(r.get('auto_score_v2', 0)):.2f} "
            f"SNR={float(r.get('channel_snr_db', 0)):.2f}dB "
            f"speech/noise={float(r.get('speech_to_hi_noise_db', 0)):.1f}dB "
            f"drone/speech={float(r.get('drone_to_speech_db', 0)):.1f}dB "
            f"upper/speech={float(r.get('upper_speech_to_total_speech_db', 0)):.1f}dB"
        )


if __name__ == "__main__":
    main()
