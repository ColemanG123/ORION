# ORION Phase 2B — RX Spectrum Probe Summary

**Generated**: 2026-05-10 13:38:54  
**Captures directory**: `data/captures/`  
**Files processed**: 4  

## Capture Table

| # | Label | URI | Timestamp | Freq (MHz) | Rate (Msps) | Gain mode | Samples | Floor (dBFS) | Peak (dBFS) | Above floor (dB) | Peak abs freq (MHz) |
|---|-------|-----|-----------|------------|-------------|-----------|---------|-------------|-------------|------------------|---------------------|
| 1 | `pluto_a` | `usb:1.8.5` | 2026-05-10T13:13:34 | 915.000 | 1.000 | slow_attack | 131,072 | -88.56 | -41.97 | 46.59 | 915.0582 |
| 2 | `pluto_b` | `usb:1.7.5` | 2026-05-10T13:13:49 | 915.000 | 1.000 | slow_attack | 131,072 | -90.56 | -43.39 | 47.17 | 915.0593 |
| 3 | `pluto_a_repeat` | `usb:1.8.5` | 2026-05-10T13:34:27 | 915.000 | 1.000 | slow_attack | 131,072 | -87.18 | -47.73 | 39.45 | 915.0595 |
| 4 | `pluto_b_repeat` | `usb:1.7.5` | 2026-05-10T13:34:33 | 915.000 | 1.000 | slow_attack | 131,072 | -88.45 | -43.93 | 44.52 | 915.0596 |

## Interpretation

- **Captures processed**: 4
- **Unique PLUTO devices**: `pluto_a`, `pluto_b`

### Average noise floor by device

| Device | Avg floor (dBFS) | Std dev (dB) | N |
|--------|-----------------|--------------|---|
| `pluto_a` | -87.87 | 0.98 | 2 |
| `pluto_b` | -89.50 | 1.49 | 2 |

### Average peak offset by device

| Device | Avg peak offset (MHz) | Std dev (MHz) | Avg above floor (dB) | N |
|--------|-----------------------|---------------|----------------------|---|
| `pluto_a` | +0.0588 | 0.0009 | 43.02 | 2 |
| `pluto_b` | +0.0595 | 0.0002 | 45.84 | 2 |

### Automated observations

- `pluto_a`: noise floor spread ≤ 1 dB across 2 captures — **stable**.
- `pluto_b`: noise floor spread = 1.49 dB across 2 captures — monitor for drift.
- The dominant spectral peak appears consistently near +58–60 kHz offset across captures. This may be related to receiver/internal artifacts or a local ambient signal; additional source-identification testing is required before attribution.
- Noise floor difference between `pluto_a` and `pluto_b`: **1.63 dB**. Within normal unit-to-unit variation.

### Calibration note

All dBFS values are **relative** to the ADALM-PLUTO ADC full scale (12-bit, ±2048 counts) and are **not calibrated dBm readings**. Conversion to dBm requires a known reference signal and is outside the scope of this passive receive test.

## Source Files

- `data/captures/spectrum_pluto_a_20260510_131334.json`
- `data/captures/spectrum_pluto_b_20260510_131349.json`
- `data/captures/spectrum_pluto_a_repeat_20260510_133427.json`
- `data/captures/spectrum_pluto_b_repeat_20260510_133433.json`
