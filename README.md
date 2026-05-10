# ORION

**ORION: An ADALM-PLUTO SDR Test Kit for Message Transmission, Signal Characterization, and Satellite-Link Readiness**

> We created a reproducible ADALM-PLUTO SDR test kit that demonstrates basic digital signal transmission, validates received spectral signatures, quantifies link quality, and defines a scalable path from benchtop PLUTO testing toward handheld-radio and ISS-oriented amateur satellite communications.

---

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | ADALM-PLUTO device detection | **Complete** |
| Phase 1B | Unique-device identification (two PLUTOs confirmed) | **Complete** |
| Phase 2 | Receive-only static spectrum captures | **Complete** |
| Phase 2B | Offline repeatability summary | **Complete** |
| Phase 3 | RX-only live spectrum GUI | **Complete** |
| Phase 3B | GUI polish and documentation | **Complete** |
| Phase 4A | Low-power over-air tone visibility test (first TX) | **Complete — PASS** |
| Phase 5 | Burst packet TX/RX with CRC validation | Not started — future work |
| Phase 6 | Handheld-radio and satellite-link readiness | Not started — future work |

Phase 4A confirmed that Pluto B can transmit a low-power CW tone and Pluto A
can detect it in the live spectrum GUI. A narrowband peak appeared at
+0.100 MHz offset when TX was active and disappeared when TX stopped.

---

## Installation

Tested on Python 3.13 (Windows 11). Python 3.10 or later is recommended.

```powershell
pip install -r requirements.txt
```

Dependencies: `pyadi-iio`, `pylibiio`, `numpy`, `matplotlib`.

The TkAgg matplotlib backend is required for the live GUI. Tkinter is included
with standard Python distributions on Windows. If the GUI does not open, try:

```powershell
$env:MPLBACKEND = "QtAgg"
```

---

## Hardware

| Label | Role | Preferred URI | Serial (last 3 hex) | Full serial | Chip | Firmware |
|-------|------|--------------|---------------------|-------------|------|----------|
| Pluto A | RX observer | `ip:pluto.local` | `e9e` | `1044734c9605000308000b003535507e9e` | AD9364 | v0.39 |
| Pluto B | TX / RX | `ip:192.168.2.1` | `149` | `1044734c96050007e9ff160082b24f2149` | AD9363A | v0.38 |

Both connected via powered ONN USB hub to ASUS ProArt P16 laptop.
Location: Innovation Lab / Toomey Hall, Missouri S&T.

> ⚠ **USB bus-path URIs** (e.g. `usb:1.x.x`) are **not** stable identifiers —
> Windows re-enumerates the hub on reconnect and reassigns paths. Always use
> the IP URIs above. Run `scripts/00_list_plutos.py` to confirm identity via
> `hw_serial` if a device cannot be reached.

---

## Quickstart

All commands run from the repository root `E:\ORION`.

### 1 — Detect PLUTOs

```powershell
python scripts\00_list_plutos.py
```

Scans for ADALM-PLUTO devices, reads `hw_serial` and `hw_model`, groups URIs
by physical device, confirms two unique devices, and writes
`docs/test_logs/hardware_status.md`.

### 2 — Static RX spectrum probe

```powershell
python scripts\01_rx_spectrum_probe.py --uri ip:pluto.local --label pluto_a
python scripts\01_rx_spectrum_probe.py --uri ip:192.168.2.1 --label pluto_b
```

Captures 131,072 IQ samples, computes a Hann-windowed FFT, saves a PNG plot
and `.npy`/`.json` files to `data/`, and appends a row to `TEST_LOG.md`.

### 3 — Offline repeatability summary

```powershell
python scripts\02_rx_repeatability_summary.py
```

Reads all `spectrum_*.json` files in `data/captures/`, computes per-device
statistics (noise floor, peak offset, repeatability), and writes
`docs/test_logs/phase2_summary.md`.

### 4 — Live spectrum GUI (RX only)

```powershell
python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a
python scripts\03_rx_live_gui.py --uri ip:192.168.2.1 --label pluto_b
```

Opens a real-time FFT spectrum window. The **RX ONLY — TX DISABLED** badge is
always visible. Press `s` to save a screenshot, `q` to quit.
See `docs/gui_live_spectrum.md` for full details.

### 5 — Low-power over-air tone TX (Phase 4A)

**Terminal 1 — start RX observer first:**

```powershell
python scripts\03_rx_live_gui.py --uri ip:pluto.local --label pluto_a_rx_baseline
```

**Terminal 2 — dry run (no RF, prints configuration):**

```powershell
python scripts\04_tx_tone_low_power.py
```

**Terminal 2 — actual 10-second transmit (after completing the pre-test checklist):**

```powershell
python scripts\04_tx_tone_low_power.py --yes-i-understand-rf-tx
```

Transmits a CW tone at 915.100 MHz (−40 dB hardware gain, 10% amplitude).
Complete `docs/test_logs/phase4_prep_checklist.md` before transmitting.
The `--yes-i-understand-rf-tx` flag is required; omitting it is a safe dry run.

---

## Receive-only safety

All RX scripts (`00_list_plutos.py`, `01_rx_spectrum_probe.py`,
`02_rx_repeatability_summary.py`, `03_rx_live_gui.py`) are **receive-only**.
None call `sdr.tx()` or set any TX hardware attribute.

The TX script (`04_tx_tone_low_power.py`) requires an explicit safety flag and
enforces a maximum gain of −20 dB during Phase 4 initial tests.

---

## Artifact paths

| Artifact | Path |
|----------|------|
| PNG spectrum plots | `data/screenshots/` |
| Raw IQ captures (`.npy`) | `data/captures/` — excluded from Git (see `.gitignore`) |
| Capture metadata (`.json`) | `data/captures/` |
| Test log | `docs/test_logs/TEST_LOG.md` |
| Hardware status | `docs/test_logs/hardware_status.md` |
| Phase summaries | `docs/phase_summaries/` |
| Phase 2B summary | `docs/test_logs/phase2_summary.md` |
| Live GUI documentation | `docs/gui_live_spectrum.md` |
| Engineering decisions | `docs/test_logs/decisions.md` |
| Phase 4 test plan | `docs/benchmark_plans/phase4_low_power_tone_plan.md` |
| Phase 4 pre-test checklist | `docs/test_logs/phase4_prep_checklist.md` |

---

## Phase 4A result summary

| Parameter | Value |
|-----------|-------|
| TX device | Pluto B (`ip:192.168.2.1`, serial `...149`) |
| RX device | Pluto A (`ip:pluto.local`, serial `...e9e`) |
| Center frequency | 915.000 MHz |
| Tone offset | +100 kHz |
| TX hardware gain | −40 dB |
| IQ amplitude | 0.1 (10% full scale) |
| Device spacing | 1–3 m benchtop, free-space |
| Tone visible at RX | **YES** |
| Tone disappeared on TX stop | **YES** |
| USB stability | Stable |
| Result | **PASS** |

See `docs/phase_summaries/phase4a_tx_tone.md` for the full summary.

---

## Planned capability (Phase 5+)

- Burst packet message transmission with CRC validation
- Signal-quality metrics (SNR, EVM, PER)
- Over-air link test at extended range
- Benchmark plans for handheld-radio and ISS-oriented amateur satellite comms
  (planning only — see `docs/benchmark_plans/`)
- Conducted coax testing deferred pending verified attenuator acquisition
