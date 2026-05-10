# Phase 3 / 3B — RX-Only Live Spectrum GUI

**Status:** COMPLETE (PASS)  
**Date:** 2026-05-10  
**Prerequisite:** Phase 2 complete; matplotlib with TkAgg backend available

---

## What was done

A real-time FFT spectrum display was implemented using `matplotlib.FuncAnimation`.
Each animation frame acquires 32,768 IQ samples from the Pluto, computes a
Hann-windowed FFT, and updates the spectrum plot, noise floor line, peak marker,
and status readout. The GUI includes a permanent **RX ONLY — TX DISABLED** safety
badge.

Phase 3B added: window title, plot title including label and parameters, `s` key
screenshot saving (timestamped to `data/screenshots/`), and `q`/Escape quit. The
GUI was successfully run on both Pluto A and Pluto B in multiple sessions.

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Script | `scripts/03_rx_live_gui.py` |
| Center frequency | 915.000 MHz (default) |
| Sample rate | 1.000 Msps |
| Samples per frame | 32,768 |
| Animation interval | 500 ms |
| Gain mode | `slow_attack` |
| Preferred URIs | `ip:pluto.local` (Pluto A), `ip:192.168.2.1` (Pluto B) |

---

## Evidence

| Artifact | Path |
|----------|------|
| Phase 4 observer baseline screenshot | `data/screenshots/live_pluto_a_rx_baseline_20260510_140427.png` |
| GUI session screenshots (Phase 3 runs) | `data/screenshots/live_pluto_a_20260510_134557.png`, `live_pluto_b_20260510_134633.png` |
| Test log entries | `docs/test_logs/TEST_LOG.md` (Phase 3 STARTED / CLOSED rows) |
| GUI documentation | `docs/gui_live_spectrum.md` |

---

## Key findings

- GUI successfully ran on both PLUTOs across multiple sessions totalling hundreds of frames.
- A Phase 3 session using `usb:1.8.5` failed at 14:00 when the USB bus path had
  changed. Switching to `ip:pluto.local` immediately resolved it — this prompted
  the project-wide migration to IP URIs (Decision 15).
- The RX-only safety badge provides a visible reminder that no transmission occurs
  during GUI use.
- The `_on_close` handler writes a `CLOSED after N frame(s)` row to `TEST_LOG.md`
  automatically.

---

## Limitations

- Single-device: one GUI instance per PLUTO.
- Not a calibrated instrument — dBFS is relative to ADC full scale.
- TkAgg backend required; headless systems need an alternative backend.
- GUI freezes if `sdr.rx()` stalls (blocking call on main thread).

---

## Next step

Phase 4A: use the live GUI as the RX observer while Pluto B transmits a CW tone.
