#!/usr/bin/env python3
"""
13_phase5c_hifi_receiver_sweep.py — ORION Phase 5C hi-fi receiver sweep.

Purpose
-------
Focused software-side sweep for the hi-fi voice-FM capture after the first
hi-fi result sounded significantly clearer than comms-grade but had:

- crackle on loud consonants/vowels,
- high-pitched ringing,
- subtle static.

Diagnostic from the first hi-fi run showed:
- no final WAV clipping,
- best offset around +126.75 kHz,
- strong tone candidates around ~4043 Hz and ~4603 Hz,
- deviation setting used: 15 kHz,
- channel cutoff used: 35 kHz.

This sweep keeps the same RF capture and tests receiver-side hypotheses:
- deviation mismatch: 12k / 15k / 18k / 20k
- channel bandwidth: 25k / 30k / 35k / 45k
- light de-emphasis: 0 / 25 / 50 / 75 us
- ringing notches: none / 4043 / 4603 / both
- clean highcut: 6000 / 7000 / 8000 Hz

Boundary
--------
Offline analysis only. No SDR. No RF.

Typical use from E:\\ORION
--------------------------
python scripts\\13_phase5c_hifi_receiver_sweep.py --iq data\\captures\\voice_rx_e9e_149_loop20_hifi_voice_rx_g25_tx32_<timestamp>.npy

Or, if the latest matching capture is correct:
python scripts\\13_phase5c_hifi_receiver_sweep.py

Then open:
data\\audio\\sweeps\\phase5c_hifi_receiver_sweep_<timestamp>\\LISTENING_INDEX.md
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
class HifiProfile:
    name: str
    expected_offset: float = 127000.0
    offset_span: float = 20000.0
    offset_step: float = 250.0
    analysis_band: float = 25000.0
    deviation: float = 15000.0
    channel_cutoff: float = 35000.0
    demod_rate: int = 200000
    lowcut: float = 60.0
    highcut: float = 8000.0
    force_start: float = 6.0
    force_stop: float = 28.0
    trim_active_start: float = 0.4
    notch_hz: tuple[float, ...] = ()
    notch_q: float = 35.0
    clean_lowcut: float = 60.0
    clean_highcut: float = 8000.0
    deemphasis_us: float = 0.0
    no_limiter: bool = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sweep Phase 5C hi-fi receiver profiles against one existing e9e hi-fi capture.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--iq", default=None, help="Input e9e hi-fi RX IQ .npy. Defaults to newest hi-fi loop20 capture.")
    p.add_argument("--limit", type=int, default=0, help="Run only first N profiles. 0 = all.")
    p.add_argument("--python", default=sys.executable, help="Python executable.")
    p.add_argument("--dry-run", action="store_true", help="Print commands without running.")
    return p.parse_args()


def newest_hifi_capture() -> Path:
    candidates = sorted(
        CAPTURE_DIR.glob("voice_rx_e9e_149_loop20_hifi_voice_rx_g25_tx32_*.npy"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No voice_rx_e9e_149_loop20_hifi_voice_rx_g25_tx32_*.npy capture found.")
    return candidates[0]


def make_profiles() -> list[HifiProfile]:
    base = dict(
        expected_offset=127000.0,
        offset_span=20000.0,
        offset_step=250.0,
        force_start=6.0,
        force_stop=28.0,
        trim_active_start=0.4,
        clean_lowcut=60.0,
        notch_q=35.0,
    )

    profiles: list[HifiProfile] = [
        # Baseline controls around first successful hi-fi demod.
        HifiProfile("h01_base_no_extra_notch", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(), deemphasis_us=0, **base),
        HifiProfile("h02_base_notch4043", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043,), deemphasis_us=0, **base),
        HifiProfile("h03_base_notch4603", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4603,), deemphasis_us=0, **base),
        HifiProfile("h04_base_notch_both", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=0, **base),

        # Deviation mismatch tests. Crackle can appear if the assumed deviation scales demod audio poorly.
        HifiProfile("h05_dev12_notch_both", deviation=12000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=0, **base),
        HifiProfile("h06_dev18_notch_both", deviation=18000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=0, **base),
        HifiProfile("h07_dev20_notch_both", deviation=20000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=0, **base),

        # Channel width tests. Wider can preserve clarity; narrower can reduce static/crackle.
        HifiProfile("h08_cut25_notch_both", deviation=15000, channel_cutoff=25000, analysis_band=20000,
                    demod_rate=160000, lowcut=60, highcut=7000, clean_highcut=7000, notch_hz=(4043, 4603), deemphasis_us=0, **base),
        HifiProfile("h09_cut30_notch_both", deviation=15000, channel_cutoff=30000, analysis_band=22000,
                    demod_rate=200000, lowcut=60, highcut=7500, clean_highcut=7500, notch_hz=(4043, 4603), deemphasis_us=0, **base),
        HifiProfile("h10_cut45_notch_both", deviation=15000, channel_cutoff=45000, analysis_band=30000,
                    demod_rate=250000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=0, **base),

        # Light de-emphasis. Heavy de-emphasis muffled comms-grade; keep hi-fi tests light.
        HifiProfile("h11_deemp25_notch_both", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=25, **base),
        HifiProfile("h12_deemp50_notch_both", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=50, **base),
        HifiProfile("h13_deemp75_notch_both", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=75, **base),

        # Less high-frequency output to tame shrillness/ringing while preserving hi-fi advantage.
        HifiProfile("h14_clean7000_notch_both", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=7000, notch_hz=(4043, 4603), deemphasis_us=0, **base),
        HifiProfile("h15_clean6000_notch_both", deviation=15000, channel_cutoff=30000, analysis_band=22000,
                    demod_rate=200000, lowcut=60, highcut=7000, clean_highcut=6000, notch_hz=(4043, 4603), deemphasis_us=0, **base),

        # Limiter control. If limiter creates crackle, this will reveal it.
        HifiProfile("h16_no_limiter_notch_both", deviation=15000, channel_cutoff=35000, analysis_band=25000,
                    demod_rate=200000, lowcut=60, highcut=8000, clean_highcut=8000, notch_hz=(4043, 4603), deemphasis_us=0,
                    no_limiter=True, **base),
    ]
    return profiles


def build_command(py: str, iq_path: Path, profile: HifiProfile) -> list[str]:
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

    speech = band_power(f, P, 60, 8000)
    speech_core = band_power(f, P, 100, 3400)
    presence = band_power(f, P, 2000, 5000)
    hiss = band_power(f, P, 8000, 14000)
    ring4043 = band_power(f, P, 3980, 4100)
    ring4603 = band_power(f, P, 4540, 4660)
    low_cloud = band_power(f, P, 60, 700)

    return {
        "peak": peak,
        "rms": rms,
        "crest": crest,
        "clip_0p98": float(np.mean(np.abs(x) > 0.98)),
        "clip_0p90": float(np.mean(np.abs(x) > 0.90)),
        "speech_to_hiss_db": db(speech) - db(hiss),
        "presence_to_speech_db": db(presence) - db(speech),
        "core_to_full_speech_db": db(speech_core) - db(speech),
        "ring4043_to_speech_db": db(ring4043) - db(speech),
        "ring4603_to_speech_db": db(ring4603) - db(speech),
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

    iq_path = Path(args.iq) if args.iq else newest_hifi_capture()
    if not iq_path.is_absolute():
        iq_path = (ROOT / iq_path).resolve()
    if not iq_path.exists():
        raise FileNotFoundError(f"Missing IQ capture: {iq_path}")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = AUDIO_DIR / "sweeps" / f"phase5c_hifi_receiver_sweep_{timestamp}"
    outdir.mkdir(parents=True, exist_ok=True)

    profiles = make_profiles()
    if args.limit and args.limit > 0:
        profiles = profiles[: args.limit]

    print("=" * 72)
    print("ORION Phase 5C Hi-Fi Receiver Sweep")
    print("=" * 72)
    print(f"IQ capture : {iq_path}")
    print(f"Profiles   : {len(profiles)}")
    print(f"Output dir : {outdir}")
    print("Goal       : keep hi-fi clarity while reducing crackle/ringing")
    print()

    rows: list[dict] = []
    report: dict = {
        "timestamp": timestamp,
        "iq_capture": str(iq_path),
        "profiles": [],
        "note": "Offline hi-fi receiver sweep. No SDR. No RF.",
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
            "deviation": profile.deviation,
            "channel_cutoff_hz": profile.channel_cutoff,
            "analysis_band": profile.analysis_band,
            "demod_rate": profile.demod_rate,
            "deemphasis_us": profile.deemphasis_us,
            "clean_highcut": profile.clean_highcut,
            "notch_hz": ";".join(str(x) for x in profile.notch_hz),
            "no_limiter": profile.no_limiter,
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
        # Listening-order hint, not truth. Favor speech/hiss and penalize ringing.
        speech_hiss = float(r.get("speech_to_hiss_db", 0.0))
        ring4043 = float(r.get("ring4043_to_speech_db", 0.0))
        ring4603 = float(r.get("ring4603_to_speech_db", 0.0))
        presence = float(r.get("presence_to_speech_db", 0.0))
        r["auto_score_hifi"] = speech_hiss - 0.25 * max(ring4043, -60.0) - 0.25 * max(ring4603, -60.0) + 0.05 * presence

    ranked = sorted(ok_rows, key=lambda r: float(r.get("auto_score_hifi", -999)), reverse=True)

    csv_path = outdir / "hifi_receiver_sweep_summary.csv"
    if rows:
        fieldnames = sorted({k for r in rows for k in r.keys()})
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    json_path = outdir / "hifi_receiver_sweep_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_path = outdir / "LISTENING_INDEX.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# ORION Phase 5C Hi-Fi Receiver Sweep Listening Index\n\n")
        f.write(f"- IQ capture: `{iq_path}`\n")
        f.write(f"- Generated: `{timestamp}`\n")
        f.write("- Goal: keep hi-fi clarity while reducing crackle/ringing.\n\n")
        f.write("## Suggested listening order\n\n")
        if ranked:
            for rank, r in enumerate(ranked[:10], start=1):
                wav = r.get("copied_limited_cleaned_active_wav") or r.get("limited_cleaned_active_wav")
                f.write(f"{rank}. **{r['profile']}** — `{wav}`\n")
                f.write(
                    f"   - deviation={float(r.get('deviation', 0))/1000:.1f} kHz, "
                    f"cutoff={float(r.get('channel_cutoff_hz', 0))/1000:.1f} kHz, "
                    f"deemp={float(r.get('deemphasis_us', 0)):.0f} us, "
                    f"notch={r.get('notch_hz', '')}, "
                    f"offset={float(r.get('best_offset_hz', 0))/1000:+.2f} kHz\n"
                )
                f.write(
                    f"   - speech/hiss={float(r.get('speech_to_hiss_db', 0)):.1f} dB, "
                    f"ring4043/speech={float(r.get('ring4043_to_speech_db', 0)):.1f} dB, "
                    f"ring4603/speech={float(r.get('ring4603_to_speech_db', 0)):.1f} dB\n"
                )
        else:
            f.write("No successful profiles.\n")

        f.write("\n## Human notes\n\n")
        f.write("| Profile | Clarity | Crackle | Ringing | Static | Overall |\n")
        f.write("|---|---:|---:|---:|---:|---:|\n")
        for r in ranked[:8]:
            f.write(f"| {r['profile']} |  |  |  |  |  |\n")

    print("\n" + "=" * 72)
    print("HI-FI SWEEP COMPLETE")
    print("=" * 72)
    print(f"Summary CSV      : {csv_path}")
    print(f"Full JSON report : {json_path}")
    print(f"Listening index  : {md_path}")
    print("\nTop candidates:")
    for r in ranked[:8]:
        print(
            f"  {r['profile']:<24} "
            f"score={float(r.get('auto_score_hifi', 0)):.2f} "
            f"SNR={float(r.get('channel_snr_db', 0)):.2f}dB "
            f"speech/hiss={float(r.get('speech_to_hiss_db', 0)):.1f}dB "
            f"r4043/speech={float(r.get('ring4043_to_speech_db', 0)):.1f}dB "
            f"r4603/speech={float(r.get('ring4603_to_speech_db', 0)):.1f}dB"
        )


if __name__ == "__main__":
    main()
