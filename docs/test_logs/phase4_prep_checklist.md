# Phase 4 Pre-Test Checklist — Low-Power Over-Air Tone Test

Complete every item before starting the TX script. Items marked **HARD STOP**
must be satisfied; the test must not proceed if they cannot be confirmed.

**Date completed:** _______________  
**Operator:** _______________  
**Location:** Innovation Lab / Toomey Hall, Missouri S&T

---

## A. Hardware — Physical Inspection

- [ ] **HARD STOP** — No coax cable is connected between Pluto A and Pluto B.
- [ ] **HARD STOP** — Neither PLUTO is connected to an amplifier, LNA, or external antenna.
- [ ] **HARD STOP** — Neither PLUTO is connected to the IC-9100, rotator system, or ground-station rack.
- [ ] Both PLUTOs have their small stock bench antennas installed and finger-tight.
- [ ] Both antennas are vertical and facing each other.
- [ ] Device spacing is 1–3 meters on a clear bench surface.
- [ ] No metal objects are directly between the two antennas.
- [ ] The powered ONN USB hub is connected and both PLUTOs show power LEDs on.

---

## B. Software — Device Detection

> ⚠ **USB bus-path URIs** (e.g. `usb:1.x.x`) are not stable identifiers and may
> change after reconnecting devices. Confirm device identity using `hw_serial`,
> not USB path. Use IP URIs for all commands in this checklist.

- [ ] Run `python scripts\00_list_plutos.py` immediately before the test.
- [ ] Pluto A (`ip:pluto.local`) appears as connected with `hw_serial` ending `e9e`.
- [ ] Pluto B (`ip:192.168.2.1`) appears as connected with `hw_serial` ending `149`.
- [ ] Both PLUTOs show `TWO_UNIQUE_DEVICES_CONFIRMED` conclusion.

```
Expected serials:
  Pluto A (RX, ip:pluto.local):  1044734c9605000308000b003535507e9e  (ends e9e)
  Pluto B (TX, ip:192.168.2.1):  1044734c96050007e9ff160082b24f2149  (ends 149)
```

---

## C. RX Baseline — Live GUI

- [ ] Launch `python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a_rx_baseline`.
- [ ] GUI window opens with title `ORION RX Live Spectrum — pluto_a`.
- [ ] **RX ONLY — TX DISABLED** badge is visible in the top-right corner.
- [ ] Spectrum is updating (frame counter incrementing).
- [ ] Noise floor is in the expected range (approximately −85 to −92 dBFS at 915 MHz).
- [ ] No unexpected large peaks are present in the baseline spectrum.
- [ ] Save a baseline screenshot now (`s` key). Filename recorded: `_______________`

---

## D. TX Configuration — Confirm Before Enabling TX

- [ ] **HARD STOP** — TX script has been read and understood before execution.
- [ ] TX URI is `ip:192.168.2.1` (Pluto B).
- [ ] TX center frequency is **915.000 MHz**.
- [ ] Tone offset is **+100 kHz** (absolute tone at 915.100 MHz).
- [ ] TX hardware gain is **−40 dB or lower** for the first attempt.
- [ ] TX script uses a cyclic buffer (continuous tone, not a single burst).
- [ ] TX script logs a Phase 4 STARTED row to `docs/test_logs/TEST_LOG.md`.

---

## E. Environment

- [ ] Test area is clear of bystanders.
- [ ] No person's hand or body is within 30 cm of either antenna.
- [ ] No other active radio transmitters (Wi-Fi routers, phones) are within 0.5 m of the test setup. *(note: complete RF isolation is not required; this is a precaution against interference masking the tone)*
- [ ] Room is quiet enough to notice if a USB device disconnects.

---

## F. Abort Plan — Confirmed Before Starting

- [ ] Operator knows which terminal window runs the TX script and can stop it with Ctrl+C.
- [ ] Operator knows to unplug Pluto B's USB cable as a secondary abort if Ctrl+C fails.
- [ ] Operator knows the abort criteria (see `docs/benchmark_plans/phase4_low_power_tone_plan.md`, Section 8).

---

## G. Evidence Plan — Ready Before Starting

- [ ] `data/screenshots/` directory exists and is writable.
- [ ] `data/captures/` directory exists and is writable.
- [ ] `docs/test_logs/TEST_LOG.md` is accessible and recent entries are visible.
- [ ] Plan is to save at least three screenshots: baseline, tone-on, tone-off.

---

## Sign-off

All items above confirmed. Proceeding to Phase 4 test execution.

**Signature / initials:** _______________  
**Time:** _______________

---

## Post-Test Notes

*(fill in after the test)*

TX gain used: ___ dB  
Device spacing: ___ m  
Tone visible at RX: YES / NO  
Approximate tone SNR: ___ dB  
Tone disappeared on TX stop: YES / NO  
USB stability: STABLE / UNSTABLE  
Heating observed: YES / NO  
Result: PASS / FAIL / ABORT  

Screenshots saved:
- Baseline: _______________
- Tone on:  _______________
- Tone off: _______________

Additional notes:

_______________
