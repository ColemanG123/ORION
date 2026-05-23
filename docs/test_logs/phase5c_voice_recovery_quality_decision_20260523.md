# ORION Phase 5C Voice Recovery Quality Decision — 2026-05-23

## Purpose

This note records the Phase 5C receiver-quality decision before moving from software-side demodulation tuning back to RF/link-quality testing.

## Current Verified State

- `e9e` is the receive/default observer.
- `149` is the transmit/secondary unit.
- Phase 5C has achieved rough over-air voice recovery from `149` to `e9e`.
- The received voice is intelligible but not clean.
- The remaining defect is mainly broadband/static-like noise plus some muffling, not a single removable tone.

## Existing Capture Used for Software Tuning

Primary comms-grade RF capture:

`data/captures/voice_rx_e9e_149_comms_voice_rx_20260522_170524.npy`

Useful discovered parameters:

- received voice-FM offset: approximately `+107 to +108.5 kHz`
- useful active window: approximately `6.4 s` to `12.0 s`
- notch target for high-pitched drone: approximately `2148 Hz`
- best subjective software candidates came from the p02/p10 family

## Receiver Sweep Conclusion

A receiver sweep was run after implementing a stronger NBFM-style receiver chain:

1. frequency translation,
2. channel filtering,
3. decimation,
4. amplitude limiting,
5. quadrature FM demodulation,
6. optional de-emphasis,
7. notch/general speech cleanup.

The first sweep showed:

- `p02_lp9_limited_clean` sounded clearer, louder, and crisper, but somewhat shrill.
- `p10_lp12_clean3200` sounded more balanced, but retained static.
- heavy de-emphasis reduced high-frequency noise numerically but made the voice quieter and more muffled.
- the v2 focused sweep did not produce a clear improvement beyond the p02/p10 trade space.

## Final Software-Side Decision for This Capture

Stop tuning receiver profiles on the existing capture.

Best evidence candidate for intelligibility:

`p02_lp9_limited_clean`

Reason:

- clearest voice recovery when static is ignored,
- louder and crisper than most other candidates,
- better practical intelligibility than quieter/more muffled de-emphasis profiles.

Balanced comparison candidate:

`p10_lp12_clean3200`

Reason:

- less shrill than p02,
- useful comparison artifact,
- but not as clear as p02.

## Engineering Interpretation

The current capture has likely reached its practical software-cleanup ceiling.

Software-side processing improved:

- offset locking,
- active-window isolation,
- tonal artifact reduction,
- repeatable recovered audio generation.

However, the remaining static/muffling appears to be primarily RF/link/capture limited. Additional receiver tuning on this capture mostly trades clarity, shrillness, muffling, and static rather than producing a decisive quality jump.

## Next Path: RF/Link Quality

The next improvement should come from a fresh RF capture with better link conditions.

Recommended next experiment:

1. Use comms-grade voice waveform.
2. Use full-message chunked TX from `149`.
3. Use manual RX gain on `e9e`.
4. Increase `149` TX gain cautiously, staying within the existing safety cap.
5. Capture a TX-active-only window when possible.
6. Demodulate the fresh capture using locked p02-like and p10-like receiver profiles.
7. Compare against the existing p02/p10 evidence.

## Locked Demod Profiles for Next Capture

### Primary intelligibility profile: p02-like

- `expected-offset`: `110000`
- `offset-span`: `12000`
- `offset-step`: `250`
- `analysis-band`: `8000`
- `deviation`: `5000`
- `channel-cutoff`: `9000`
- `demod-rate`: `100000`
- `lowcut`: `120`
- `highcut`: `3000`
- `clean-lowcut`: `80`
- `clean-highcut`: `3200`
- `notch-hz`: `2148`
- `notch-q`: `35`
- `trim-active-start`: `0.8`

### Balanced comparison profile: p10-like

- `expected-offset`: `110000`
- `offset-span`: `12000`
- `offset-step`: `250`
- `analysis-band`: `9000`
- `deviation`: `5000`
- `channel-cutoff`: `12000`
- `demod-rate`: `100000`
- `lowcut`: `100`
- `highcut`: `3400`
- `clean-lowcut`: `90`
- `clean-highcut`: `3200`
- `notch-hz`: `2148`
- `notch-q`: `35`
- `trim-active-start`: `0.8`

## Documentation Language for Reports

Safe wording:

> Phase 5C demonstrated rough over-air voice recovery from `149` to `e9e`. The best recovered audio was intelligible but not clean. Receiver-side tuning improved offset selection, active-window isolation, and tonal-artifact reduction, but the remaining static and muffling were not fully removed from the existing capture. The result supports the conclusion that the next quality improvement should target RF/link conditions and fresh capture quality rather than further tuning of the same recording.

Avoid claiming:

- clean voice recovery,
- final voice-link quality,
- ISS-ready audio quality,
- optimized receiver performance.

## Immediate Next Step

Run one fresh RF capture with improved RF conditions and demodulate it with the locked p02-like profile first.
