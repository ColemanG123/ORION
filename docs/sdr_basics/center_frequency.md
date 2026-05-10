# Center Frequency

## Definition

The center frequency (also called the LO frequency or carrier frequency) is the
frequency to which the radio hardware tunes its local oscillator (LO). In a
software-defined radio, all received or transmitted signals are measured as
offsets from this center point. A signal at exactly the center frequency appears
at 0 Hz offset in the baseband spectrum; a signal 100 kHz above the center
appears at +0.100 MHz offset.

The ADALM-PLUTO tunes its AD9363A/AD9364 transceiver chip to the requested
center frequency. The tuning range is approximately 70 MHz to 6 GHz.

## ORION Relevance

All Phase 2–4 tests use a center frequency of **915 MHz** (915,000,000 Hz), which
falls within the 902–928 MHz ISM band legal for low-power unlicensed operation
in the United States.

In Phase 4A, Pluto B's TX LO was set to 915 MHz and the transmitted tone was
placed at +100 kHz offset (absolute frequency: 915.100 MHz) to avoid LO leakage
at the center bin.

## Test Notes

- Both ADALM-PLUTOs support 915 MHz: the AD9364 (Pluto A) and AD9363A (Pluto B)
  both tune successfully to this frequency.
- The RX center frequency must match the TX LO for the tone to appear near the
  expected offset in the live GUI spectrum.
