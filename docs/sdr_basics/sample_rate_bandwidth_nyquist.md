# Sample Rate, Bandwidth, and Nyquist

## Definitions

**Sample rate**: the number of complex IQ samples captured per second, in samples
per second (sps) or mega-samples per second (Msps). Determines the observable
bandwidth of the baseband spectrum.

**Nyquist theorem**: a bandlimited signal can be perfectly reconstructed if the
sample rate is at least twice the highest frequency component. For complex
(IQ) sampling, a sample rate of *f_s* captures a two-sided bandwidth of *f_s*
centered on the LO frequency — so the observable range is [LO − f_s/2, LO + f_s/2].

**RF bandwidth**: the analog filter bandwidth applied before the ADC. Should be
set close to the sample rate to avoid aliasing while rejecting out-of-band
interference.

## ORION Relevance

All Phase 2–4 tests use:
- Sample rate: **1.000 Msps** (1,000,000 samples/second)
- RX/TX RF bandwidth: **1.000 MHz**
- Observable span: 915 MHz ± 0.5 MHz = **914.5 – 915.5 MHz**

The +100 kHz tone offset used in Phase 4A falls well within this span and avoids
the LO leakage typically visible at 0 Hz offset.

## Test Notes

- The AD9363A (Pluto B) and AD9364 (Pluto A) both support 1 Msps without issue.
- Increasing sample rate widens the observable spectrum but increases USB
  bandwidth demand and may cause buffer overruns on some systems.
- FFT resolution at 1 Msps with 32,768 samples ≈ 30.5 Hz per bin. With 131,072
  samples (Phase 2 static captures) ≈ 7.6 Hz per bin.
