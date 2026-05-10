# SNR and Noise Floor

## Definitions

**Noise floor**: the lowest power level at which a signal can be distinguished
from background thermal and receiver noise. In ORION's FFT spectra it is
estimated as the 10th percentile of the power spectral density across all
frequency bins, expressed in dBFS.

**SNR (Signal-to-Noise Ratio)**: the ratio of signal power to noise power,
typically expressed in dB. In ORION context: `SNR ≈ peak_dbfs − noise_floor_dbfs`.

**dBFS**: decibels relative to ADC full scale. A value of 0 dBFS means the
signal is at the ADC's maximum representable amplitude. All ORION measurements
are in dBFS and are **not** calibrated to dBm without a known reference signal.

## ORION Relevance

Phase 2 static captures measured noise floors of approximately −88 to −91 dBFS
at 915 MHz with `slow_attack` AGC. A persistent ambient peak was observed at
roughly +58–60 kHz offset with approximately 40–47 dB above the noise floor.
The source of this peak was not definitively identified (see `phase2_summary.md`).

Phase 4A success criterion S2 required the TX tone to be at least 10 dB above
the noise floor when visible. The test was declared PASS.

## Test Notes

- dBFS values depend on AGC state. `slow_attack` mode was used for all RX tests.
- No calibrated attenuators or reference signals were available to convert dBFS
  to absolute dBm. All SNR figures are relative and indicative only.
- Noise floor varies slightly between captures (std dev ≤ 1.5 dB across Phase 2
  repeatability runs) — within normal thermal variation.
