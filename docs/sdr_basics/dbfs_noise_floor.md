# ORION dBFS, Noise Floor, and Peak Estimates

ORION reports spectrum power in dBFS, or decibels relative to full scale. This is a digital relative-power measurement, not an absolute RF power measurement in dBm.

A value near `0 dBFS` would indicate a signal close to the maximum representable digital amplitude. More negative values indicate weaker digital signal levels.

For the Phase 2 probe, ORION estimated:

- noise floor using the 10th percentile of FFT-bin power values
- peak level using the maximum FFT-bin power value
- peak offset using the frequency bin corresponding to the maximum value

Example:

- Noise floor: `-90.6 dBFS`
- Peak: `-43.4 dBFS`
- Peak offset: `+0.059 MHz`

This means the strongest spectral bin was approximately 47.2 dB above the 10th-percentile floor in the plotted spectrum. This is not yet a calibrated SNR measurement because it does not account for receiver gain, antenna response, absolute calibration, or signal bandwidth.