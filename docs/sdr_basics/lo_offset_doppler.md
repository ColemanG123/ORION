# LO Offset and Doppler

## Definitions

**LO leakage**: imperfect IQ balance in the mixer causes a residual carrier
signal to appear at exactly 0 Hz offset (the center bin) in the baseband
spectrum. This artifact is present in all direct-conversion SDRs including the
ADALM-PLUTO. It is not a received signal; it is a hardware artifact.

**LO offset technique**: to avoid the LO leakage bin, the transmitter places the
desired signal at a deliberate offset from the center frequency. The receiver
tunes to the same center frequency and observes the signal at the expected offset.

**Doppler shift**: a relative velocity between transmitter and receiver causes a
frequency shift proportional to velocity and carrier frequency:
`Δf = (v/c) × f_carrier`. For a 915 MHz carrier and typical satellite orbital
velocities (~7.5 km/s), the Doppler shift can reach ±23 kHz. For stationary
benchtop tests, Doppler is negligible.

## ORION Relevance

Phase 4A used a +100 kHz LO offset to place the transmitted tone away from the
LO leakage bin. The expected tone appeared at +0.100 MHz offset in the live GUI.

Future satellite-link work (Phase 6, planning only) would require real-time
Doppler correction. No Doppler correction is implemented in the current codebase.

## Test Notes

- The ambient spectral peak observed at ~+58–60 kHz in Phase 2 baseline captures
  was present before any TX was enabled and is distinct from the Phase 4A tone.
  Its source is unattributed (see `phase2_summary.md`).
- Doppler considerations for ISS passes are documented as future work in
  `docs/benchmark_plans/benchmark_4_iss_path.md`.
