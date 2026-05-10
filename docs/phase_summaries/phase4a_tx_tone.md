# Phase 4A — Low-Power Over-Air Tone Visibility Test

**Status:** PASS  
**Date:** 2026-05-10  
**Prerequisite:** Phase 3B complete; pre-test checklist signed off

---

## What was done

Pluto B transmitted a continuous-wave (CW) tone at low power over-air on the
915 MHz ISM band. Pluto A received and confirmed the spectral peak via the live
GUI. This was the first intentional RF transmission in the ORION project.

Three TX runs were performed:
- 14:17 — 10-second run (STARTED / STOPPED)
- 14:18 — 10-second run (STARTED / STOPPED)
- 14:21 — 30-second run (STARTED / STOPPED)

The RX GUI ran for 881 frames during the main observation window, confirming
live spectrum updates throughout. Baseline, tone-on, and tone-off screenshots
were saved.

---

## Configuration

| Parameter | Value |
|-----------|-------|
| TX script | `scripts/04_tx_tone_low_power.py` |
| RX script | `scripts/03_rx_live_gui.py` |
| TX device | Pluto B — `ip:192.168.2.1` — serial ends 149 |
| RX device | Pluto A — `ip:pluto.local` — serial ends e9e |
| TX center frequency (LO) | 915.000 MHz |
| Tone offset | +100 kHz |
| Tone absolute frequency | 915.100 MHz |
| TX hardware gain | −40 dB |
| IQ amplitude | 0.100 (10% of DAC full scale) |
| Sample rate | 1.000 Msps |
| TX bandwidth | 1.000 MHz |
| Device spacing | 1–3 m, benchtop, free-space |
| Antenna | Small stock ADALM-PLUTO bench antennas |
| Coax | None — over-air only |

---

## Evidence

| Artifact | Path |
|----------|------|
| Baseline screenshot (pre-TX) | `data/screenshots/ORION_RX_Live_Spectrum_—_pluto_a_phase4_observer_BASELINE.png` |
| Tone-on screenshots | `data/screenshots/ORION_RX_Live_Spectrum_—_pluto_a_phase4_observer_RXing1LIVE.png`, `RXing2LIVE.png` |
| Post-TX screenshot | `data/screenshots/ORION_RX_Live_Spectrum_—_pluto_a_phase4_observer_POSTBASELINE.png` |
| Timestamped GUI saves | `data/screenshots/live_pluto_a_phase4_observer_20260510_141131.png`, `_141754.png`, `_141830.png` |
| Test log entries | `docs/test_logs/TEST_LOG.md` (Phase 4A STARTED / STOPPED rows) |
| Pre-test checklist | `docs/test_logs/phase4_prep_checklist.md` |
| Test plan | `docs/benchmark_plans/phase4_low_power_tone_plan.md` |

---

## Key findings

- A new narrowband spectral peak appeared at approximately +0.100 MHz offset
  when TX was active, consistent with the expected tone frequency.
- The peak was visible above the noise floor when TX was running and absent (or
  reduced) when TX stopped, confirming the observed feature was the transmitted tone.
- Both PLUTOs remained connected throughout; no USB drops or unexpected heating.
- TX safety gate (`--yes-i-understand-rf-tx` flag) functioned correctly — the
  script performs a dry-run configuration print without transmitting unless the
  flag is explicitly passed.
- TX cleanup (`tx_destroy_buffer`) executed correctly on normal exit and on
  Ctrl+C abort.

---

## Limitations

- **Not a calibrated power measurement.** Peak dBFS levels are relative to ADC
  full scale; no dBm conversion was performed.
- **Not a link budget measurement.** Path loss at 1–3 m benchtop is not
  representative of any operational link.
- **Not a packet or data test.** No modulation, encoding, or data payload was
  transmitted. The tone carries no information.
- **Single frequency and gain setting.** All runs used 915 MHz, −40 dB, 0.1 amplitude.
- **Free-space only.** No conducted (coax) testing; no attenuators available.

---

## Next step

Phase 5: burst packet TX/RX with CRC validation, still using low-power over-air
configuration at 915 MHz. Conducted testing deferred pending attenuator acquisition.
