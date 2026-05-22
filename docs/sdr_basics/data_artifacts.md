# ORION Data Artifacts

Each ORION receive-only spectrum probe produces three primary evidence artifacts:

## PNG Spectrum Plot

A human-readable plot showing the FFT spectrum, estimated noise floor, and strongest detected peak.

Example:

`data/screenshots/spectrum_pluto_b_20260510_131349.png`

## NPY Raw IQ Capture

A NumPy binary file containing the raw complex IQ samples captured from the SDR.

Example:

`data/captures/spectrum_pluto_b_20260510_131349.npy`

## JSON Metadata

A machine-readable summary of the test configuration and computed metrics.

Example fields:

- URI
- label
- timestamp
- center frequency
- sample rate
- receive bandwidth
- gain mode
- number of samples
- estimated noise floor
- detected peak level
- detected peak frequency offset

The JSON file makes each plot traceable back to the hardware configuration and analysis settings used to generate it.