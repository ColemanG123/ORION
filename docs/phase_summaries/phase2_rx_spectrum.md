# Phase 2 — Receive-Only Static Spectrum Captures

**Status:** PASS  
**Date:** 2026-05-10  
**Prerequisite:** Phase 1B complete — both PLUTOs confirmed, IP URIs known

---

## What was done

Pluto A and Pluto B each received 131,072 IQ samples at 915 MHz. A Hann-windowed
FFT was computed, the noise floor estimated as the 10th-percentile bin, and the
dominant spectral peak located. Results were saved as PNG plots, raw `.npy`
captures, and `.json` metadata files. The test log was updated automatically.

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Script | `scripts/01_rx_spectrum_probe.py` |
| Center frequency | 915.000 MHz |
| Sample rate | 1.000 Msps |
| RX bandwidth | 1.000 MHz |
| Gain mode | `slow_attack` (AGC) |
| Samples per capture | 131,072 |
| FFT window | Hann |

---

## Evidence

| Artifact | Path |
|----------|------|
| Pluto A spectrum PNG | `data/screenshots/spectrum_pluto_a_20260510_131334.png` |
| Pluto B spectrum PNG | `data/screenshots/spectrum_pluto_b_20260510_131349.png` |
| Pluto A metadata | `data/captures/spectrum_pluto_a_20260510_131334.json` |
| Pluto B metadata | `data/captures/spectrum_pluto_b_20260510_131349.json` |
| Test log entries | `docs/test_logs/TEST_LOG.md` (Phase 2 rows) |

---

## Key findings

- Pluto A noise floor: −88.6 dBFS; peak: −42.0 dBFS at +0.058 MHz offset
- Pluto B noise floor: −90.6 dBFS; peak: −43.4 dBFS at +0.059 MHz offset
- An ambient spectral peak near +58–60 kHz was visible on both devices before
  any TX was enabled. Its source was not identified (internal artifact or local
  ambient signal — see `phase2_summary.md`).
- Both devices functional and stable at 915 MHz.

---

## Limitations

- All dBFS values are relative to the 12-bit ADC full scale. No calibrated dBm
  conversion was performed — no reference signal or attenuator was available.
- Two captures per device; insufficient for robust statistical confidence.
- The +58–60 kHz ambient peak is unattributed.

---

## Next step

Phase 2B: offline repeatability summary across all captures; Phase 3: live GUI.
