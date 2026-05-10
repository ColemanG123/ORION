# ORION IQ Sample Storage

The ADALM-PLUTO receives radio-frequency energy and converts it into complex baseband IQ samples. Each sample has two components:

- `I`: in-phase component
- `Q`: quadrature component

Together, one sample can be represented as:

`x[n] = I[n] + jQ[n]`

In ORION, received samples are saved as NumPy `.npy` files. The intended saved format is a complex-valued NumPy array, typically `complex64`, where each sample contains a real component and an imaginary component.

This format is useful because it preserves the received baseband signal for later re-analysis. A saved capture can be reloaded without needing to repeat the hardware test.

Example artifact:

`data/captures/spectrum_pluto_b_20260510_131349.npy`

This file contains the raw received IQ capture used to generate the corresponding spectrum plot and metadata file.