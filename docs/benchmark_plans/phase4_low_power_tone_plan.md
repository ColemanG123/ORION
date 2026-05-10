# Phase 4 — Low-Power Over-Air Tone Visibility Test Plan

**Status:** Pre-test planning complete. No code written. No transmission performed.  
**Date drafted:** 2026-05-10  
**Prerequisite:** Phase 3B complete (both PLUTOs receiving, live GUI verified).

---

## 1. Objective

Confirm that Pluto B can transmit a single continuous-wave (CW) tone that is
visibly detectable in Pluto A's live RX spectrum at low power and short range.

This is the first intentional transmit test. It is **not** a packet communication
test. There is no modulation, framing, encoding, or data payload. The only goal
is to observe a known spectral feature appear and disappear on command.

---

## 2. Physical Setup

| Parameter | Value |
|-----------|-------|
| TX device | Pluto B — `ip:192.168.2.1` — serial `...149` (AD9363A, fw v0.38) |
| RX device | Pluto A — `ip:pluto.local` — serial `...e9e` (AD9364, fw v0.39) |
| TX antenna | Small stock ADALM-PLUTO antenna |
| RX antenna | Small stock ADALM-PLUTO antenna |
| Antenna orientation | Both vertical, facing each other on the bench |
| Initial device spacing | 1–3 meters, open bench, no obstructions between antennas |
| Connection to hub | Both connected to powered ONN USB hub as in Phases 1–3 |

**No coax connection between PLUTOs.** Over-air only.

> ⚠ **USB bus-path URIs** (e.g. `usb:1.x.x`) are not stable identifiers and may
> change after reconnecting devices. Use the IP URIs above and verify identity
> via `hw_serial` before starting the test.

---

## 3. Safety Constraints

The following constraints apply without exception during Phase 4.

**RF connections**
- No coax cable between Pluto A and Pluto B at any point.
- No connection to amplifiers, LNAs, or any powered RF equipment.
- No connection to the IC-9100, rotator system, ground-station rack, or external antennas.
- Use only the small stock bench antennas included with each PLUTO.
- 915 MHz ISM band: legal for low-power unlicensed operation in the United States.

**Power and gain**
- Initial TX hardware gain: −40 dB or lower. Increase only in small steps if the
  tone is not visible at 3 meters.
- Do not exceed −20 dB TX hardware gain during initial testing at short range.
- If the RX noise floor rises abnormally or the receiver appears to saturate
  (spectrum becomes flat, clipped, or all-noise), reduce TX gain or increase
  spacing immediately.

**Abort triggers — stop transmission immediately if any of the following occur:**
- RX spectrum becomes flat or clipped (possible saturation)
- Live GUI freezes or stops updating
- Unexpected heating of either PLUTO body or USB hub
- USB device drop or reconnect event during transmission
- Observed signal cannot be made to disappear by stopping the TX script
- Any concern about regulatory compliance or unintended interference

**Personnel**
- No person should be within 30 cm of either antenna during active transmission.
- This is a benchtop test; keep the test area clear of bystanders.

---

## 4. Configuration

### TX (Pluto B)

| Parameter | Value | Notes |
|-----------|-------|-------|
| URI | `ip:192.168.2.1` | Preferred stable URI; serial `...149` confirmed in Phase 1B |
| Center frequency (TX LO) | 915.000 MHz | 915 MHz ISM band |
| Tone offset from LO | +100 kHz | Avoids LO leakage; within RX bandwidth |
| Tone absolute frequency | 915.100 MHz | |
| Sample rate | 1.000 Msps | Matches RX |
| TX RF bandwidth | 1.000 MHz | |
| TX hardware gain | −40 dB (initial) | Increase in 5 dB steps only if needed |
| Waveform | CW tone (continuous complex sinusoid) | No modulation, no packet |
| Cyclic buffer | Yes | Repeat the tone buffer continuously |

### RX (Pluto A)

| Parameter | Value | Notes |
|-----------|-------|-------|
| URI | `ip:pluto.local` | Preferred stable URI; serial `...e9e` confirmed in Phase 1B |
| Center frequency (RX LO) | 915.000 MHz | Same as TX LO |
| Sample rate | 1.000 Msps | |
| RX RF bandwidth | 1.000 MHz | |
| Gain mode | `slow_attack` (AGC) | Passive adaptation |
| Live GUI | `scripts/03_rx_live_gui.py` | Visual confirmation |

The expected tone appears at **+0.100 MHz offset** on the RX spectrum.

---

## 5. Pre-Test Checklist

See `docs/test_logs/phase4_prep_checklist.md` for the complete operator checklist.

Key items:
- [ ] Phase 4 TX script reviewed and understood before execution
- [ ] Both PLUTOs detected by `00_list_plutos.py` immediately before the test
- [ ] Pluto A RX live GUI running and showing a stable baseline spectrum
- [ ] No coax connected between PLUTOs
- [ ] No amplifier, LNA, or external antenna connected to either PLUTO
- [ ] TX gain initialized at −40 dB or lower
- [ ] Operator hand is not near either antenna during transmission

---

## 6. Test Procedure

> **Note:** The TX script (`scripts/04_tx_tone_test.py`) does not yet exist.
> This procedure describes the intended sequence; implementation follows
> after this planning document is reviewed and approved.

**Step 1 — Baseline capture (RX only)**

```powershell
# Terminal 1: run live GUI on Pluto A (preferred stable URI)
python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a
```

Observe the baseline spectrum for 30–60 seconds. Note the noise floor level and
any ambient peaks. Press `s` to save a baseline screenshot before proceeding.

**Step 2 — Start TX (Pluto B, low power)**

```powershell
# Terminal 2 (future command — not yet implemented):
# python scripts\04_tx_tone_test.py --uri ip:192.168.2.1 --label pluto_b \
#     --freq 915e6 --tone-offset 100e3 --rate 1e6 --tx-gain -40
```

The TX script will:
- Connect to Pluto B
- Generate a cyclic CW tone buffer at +100 kHz offset
- Begin continuous transmission at −40 dB hardware gain
- Print status to console and log a Phase 4 STARTED row to TEST_LOG.md

**Step 3 — Observe RX spectrum**

On the Pluto A live GUI:
- Watch for a new narrowband peak near +0.100 MHz offset.
- If no peak appears within 30 seconds at −40 dB, increase TX gain by +5 dB
  and wait again. Do not exceed −20 dB.
- Once the tone is visible, press `s` to save a screenshot with TX active.

**Step 4 — Stop TX**

Stop the TX script (Ctrl+C in Terminal 2). Observe the RX spectrum:
- The tone should disappear or drop clearly within one or two frames.
- Press `s` on the GUI to save a "TX off" screenshot.

**Step 5 — Save capture**

```powershell
# Terminal 1: also run static probe to save a .npy capture with TX active (optional)
python scripts\01_rx_spectrum_probe.py --uri ip:pluto.local --label pluto_a_phase4_tone_on
```

**Step 6 — Log and close**

Close the live GUI (`q`). The TEST_LOG CLOSED row is appended automatically.
Record observations in TEST_LOG.md manually if needed.

---

## 7. Success Criteria

All of the following must be satisfied for Phase 4 to be declared PASS:

| # | Criterion |
|---|-----------|
| S1 | A new narrowband spectral peak appears within ±10 kHz of the expected +100 kHz offset while TX is active |
| S2 | The peak is at least 10 dB above the noise floor as measured in the live GUI |
| S3 | The peak disappears or drops ≥ 10 dB below its TX-active level within two GUI frames after TX stops |
| S4 | A screenshot is saved with the tone visible (TX active) |
| S5 | A screenshot is saved after TX stops (tone absent or reduced) |
| S6 | Both PLUTOs remain connected throughout (no USB drop) |
| S7 | Neither device shows unexpected heating or instability |
| S8 | TEST_LOG.md receives at least one Phase 4 PASS entry |

---

## 8. Abort Criteria

Stop transmission immediately and do not restart without reviewing the cause:

| Condition | Action |
|-----------|--------|
| RX spectrum flattens or clips | Reduce TX gain by 20 dB or stop TX |
| Live GUI stops updating | Stop TX; restart GUI; investigate |
| USB device drop on either PLUTO | Stop TX; reconnect; re-run `00_list_plutos.py` |
| Unexpected heat on PLUTO body or hub | Stop TX; unplug; inspect |
| Tone visible but cannot be removed by stopping TX | Unplug Pluto B; investigate source |
| Any concern about interference or regulatory limit | Stop all transmission immediately |

---

## 9. Evidence to Save

| Artifact | Filename pattern | Method |
|----------|-----------------|--------|
| Baseline screenshot (no TX) | `live_pluto_a_<ts>_baseline.png` | `s` key in GUI |
| TX-active screenshot | `live_pluto_a_<ts>_tone_on.png` | `s` key in GUI |
| TX-off screenshot | `live_pluto_a_<ts>_tone_off.png` | `s` key in GUI |
| Static RX capture (optional) | `spectrum_pluto_a_phase4_tone_on_<ts>.npy/.json` | `01_rx_spectrum_probe.py` |
| TEST_LOG entries | `docs/test_logs/TEST_LOG.md` | Automatic (STARTED/CLOSED) + manual |

All PNG screenshots go to `data/screenshots/`.  
All `.npy` captures go to `data/captures/`.

---

## 10. Report-Ready Summary Template

Once the test is complete, fill in and save this block as part of the test log:

```
Phase 4 — Low-Power Tone Visibility Test
Date/Time:         _______________
TX device:         Pluto B (ip:192.168.2.1, serial ...149)
RX device:         Pluto A (ip:pluto.local, serial ...e9e)
Center frequency:  915.000 MHz
Tone offset:       +100 kHz
TX gain used:      ___ dB
Device spacing:    ___ m
Tone visible:      YES / NO
Tone SNR (approx): ___ dB above floor
Tone disappears on TX stop: YES / NO
USB stability:     STABLE / UNSTABLE
Heating observed:  YES / NO
Result:            PASS / FAIL / ABORT
Screenshots saved: YES / NO
Notes:             _______________
```

---

## 11. Limitations

- **Not a link budget measurement.** Observed dBFS levels are relative, not
  calibrated dBm. The test confirms tone visibility only.
- **Not a range test.** 1–3 meters on a benchtop is not representative of any
  operational link distance.
- **Not a modulation or packet test.** A CW tone carries no data. Packet
  communication testing begins in Phase 5.
- **No attenuation.** The absence of verified attenuators means coax-connected
  testing cannot be performed safely. This test uses free-space path loss at
  1–3 m as the only attenuation mechanism.
- **Single frequency.** This test is performed at 915 MHz only.

---

## 12. Next Step After Success

If Phase 4 PASS criteria are met:

1. Document observations and save all evidence artifacts.
2. Run `scripts/02_rx_repeatability_summary.py` to incorporate any new captures.
3. Proceed to **Phase 5 design**: burst packet TX/RX with CRC validation,
   still using low-power over-air configuration.
4. Revisit conducted testing (coax) only after verified attenuators are obtained.
