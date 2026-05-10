# ORION FFT Spectrum Calculation

The receive-only spectrum probe estimates the frequency content of a captured IQ signal using a Fast Fourier Transform (FFT).

The processing sequence is:

1. Capture `N` complex IQ samples from the selected ADALM-PLUTO.
2. Apply a Hann window (a type of tapered window function that tapers the beginning and ending of a sampled signal towards zero, minimizing discontinuities at the boundaries) to reduce spectral leakage .
3. Compute the FFT of the windowed samples.
4. Shift the FFT so that zero-frequency offset appears in the center of the plot.
5. Convert FFT magnitude into a relative dBFS scale.
6. Identify the strongest spectral peak.
7. Report that peak as an offset from the configured center frequency.

For the Phase 2 receive-only probe, the center frequency was 915 MHz and the sample rate was 1.000 Msps. Therefore, the displayed frequency axis spans approximately:

`-0.5 MHz to +0.5 MHz`

relative to the 915 MHz center frequency.

A reported peak offset of `+0.059 MHz` means the strongest observed spectral feature appeared near:

`915.059 MHz`