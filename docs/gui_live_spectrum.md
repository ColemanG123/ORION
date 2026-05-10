# ORION Live Spectrum GUI

**Script:** `scripts/03_rx_live_gui.py`  
**Phase:** 3 / 3B  
**Mode:** Receive-only. No transmission.

---

## Purpose

Provides a continuously-updated FFT spectrum display from one ADALM-PLUTO.
Intended as a real-time diagnostic and demonstration tool, not a calibrated
RF measurement instrument.

---

## Launch commands

> ⚠ **USB bus-path URIs** (e.g. `usb:1.x.x`) are not stable identifiers and may
> change after reconnecting devices. Use the IP URIs below and verify device
> identity via `hw_serial` (run `scripts/00_list_plutos.py`) if in doubt.

```powershell
cd E:\ORION

# Pluto A (AD9364, fw v0.39) — preferred stable URI
python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a

# Pluto B (AD9363A, fw v0.38) — preferred stable URI
python scripts\03_rx_live_gui.py --uri ip:192.168.2.1 --label pluto_b
```

### All arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--uri` | *(required)* | IIO context URI |
| `--label` | derived from URI | Short device label used in filenames |
| `--freq` | `915e6` | Center frequency (Hz) |
| `--rate` | `1e6` | Sample rate (Hz) |
| `--rx-bw` | `1e6` | RX RF bandwidth (Hz) |
| `--gain-mode` | `slow_attack` | AGC mode: `slow_attack`, `fast_attack`, `manual` |
| `--gain-db` | `40.0` | Manual gain dB (only with `--gain-mode manual`) |
| `--samples` | `32768` | IQ samples per frame |
| `--interval-ms` | `500` | Animation update interval (ms) |

### Examples with overrides

```powershell
# Different frequency
python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a --freq 433.9e6

# Faster refresh, more samples
python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a --interval-ms 250 --samples 65536

# Manual gain
python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a --gain-mode manual --gain-db 50
```

---

## What the GUI shows

The window is divided into two panels.

### Left panel — live FFT spectrum

| Element | Description |
|---------|-------------|
| Blue line | FFT power spectral density, Hann-windowed, updated every frame |
| Red dashed line | 10th-percentile noise floor (updates each frame) |
| Orange dotted vertical line | Position of the spectral peak |
| Orange downward triangle | Marker at the peak bin |
| Orange text box (upper-left) | Peak level (dBFS) and peak frequency offset (MHz) |

X-axis: frequency offset in MHz from the center LO frequency.  
Y-axis: power in dBFS (relative to 12-bit ADC full scale — **not calibrated dBm**).

### Right panel — status readout

Updated every frame:

```
──────────────────────
URI:    ip:pluto.local
Label:  pluto_a
──────────────────────
Freq:   915.000 MHz
Rate:   1.000 Msps
Gain:   slow_attack
──────────────────────
Frame:  42
──────────────────────
Floor:  -88.5 dBFS
Peak:   -47.7 dBFS
Offset: +0.0582 MHz
AbvFlr: 40.8 dB
──────────────────────
s = screenshot
q = quit
```

### Safety badge

A permanent **RX ONLY — TX DISABLED** badge appears in the top-right corner
of the figure at all times.

---

## Keyboard controls

| Key | Action |
|-----|--------|
| `s` | Save a screenshot to `data/screenshots/live_<label>_<timestamp>.png` |
| `q` | Close the window and quit |
| `Escape` | Close the window and quit |

The window close button also works normally.

---

## Evidence produced

| Artifact | Path | When created |
|----------|------|--------------|
| Screenshot PNG | `data/screenshots/live_<label>_<YYYYMMDD_HHMMSS>.png` | On `s` keypress |
| TEST_LOG STARTED row | `docs/test_logs/TEST_LOG.md` | On launch |
| TEST_LOG CLOSED row | `docs/test_logs/TEST_LOG.md` | On window close |

No IQ captures are saved automatically during live operation. Use
`scripts/01_rx_spectrum_probe.py` for saved `.npy` captures.

---

## Limitations

- **Not a calibrated instrument.** dBFS values are relative to the ADC full
  scale. They cannot be directly compared to dBm without a calibrated
  reference signal.
- **Single-device.** One GUI instance connects to one PLUTO. To monitor both
  devices simultaneously, open two PowerShell windows.
- **Blocking RX.** Each animation frame calls `sdr.rx()` on the main thread.
  If the device stalls, the GUI freezes until the call returns or times out.
- **USB path stability.** USB bus-path URIs (e.g. `usb:1.x.x`) are not stable
  identifiers — Windows re-enumerates the hub on reconnect and reassigns paths.
  Always use `ip:pluto.local` (Pluto A) and `ip:192.168.2.1` (Pluto B) as the
  preferred runtime URIs. Run `scripts/00_list_plutos.py` to confirm identity
  via `hw_serial` if a device cannot be reached.
- **Backend dependency.** Requires TkAgg matplotlib backend (tkinter). If the
  window does not open, run `$env:MPLBACKEND="QtAgg"` before launching.

---

## Safety note

**This script is receive-only.** It never calls `sdr.tx()` and never sets any
TX hardware attribute (TX LO, TX gain, TX bandwidth, TX buffer). The ADALM-PLUTO
antenna port is in receive mode only. No RF energy is transmitted by this script.

TX capability is deferred to Phase 4 and will require explicit opt-in flags
and a separate safety review before any transmission occurs.
