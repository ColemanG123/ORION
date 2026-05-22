# ORION Phase 5C Handoff — 2026-05-22

## Current Verified State

- `e9e` is the receive/default observer.
- `149` is the transmit/secondary unit.
- Serial-suffix naming is mandatory. Do not use unstable USB paths as identities.
- `e9e` RX works.
- `149` TX works.
- A +100 kHz tone from `149` is clearly visible on `e9e`.
- Phase 5A audio capture passed.
- Phase 5B offline FM modulation/demodulation passed.
- Phase 5C-1 Pluto-ready IQ generation passed.
- DAC scaling was required for voice TX visibility.
- Full-message chunked TX from `149` produced visible comms-grade voice-FM energy near +100 kHz on `e9e`.
- Received voice is recoverable, but currently muffled and contaminated with static/droning artifacts.

## Current Best Capture / Demod Notes

Latest useful comms-grade RX capture:

`data/captures/voice_rx_e9e_149_comms_voice_rx_20260522_170524.npy`

Useful demod candidate family:

`rx_voice_fm_e9e_149_comms_scan_trim_*`

Best subjective candidate so far:

- `lp12 cleaned` sounded slightly clearer than the others.
- `lp9 cleaned` had stronger objective speech/noise metrics.
- All candidates remain semi-muffled with residual static.

Important discovered values:

- Useful received offset is around `107–108.5 kHz`, not exactly `100 kHz`.
- Active window used for best trims: `6.4–12.0 s`.
- High-pitched drone near `2148 Hz` was reduced by notch filtering.
- Remaining issue is mostly broadband/static-like noise and comms-grade muffling, not one single tone.

## Current Engineering Interpretation

Phase 5C has achieved rough RF voice recovery, but not final clean-quality recovery.

The next improvement should focus on a more complete NBFM receiver chain:

1. Frequency translate to chosen offset.
2. Channel filter.
3. Decimate.
4. Limit/amplitude-normalize before FM demod.
5. Quadrature demod.
6. Optional de-emphasis.
7. General speech cleanup.
8. Candidate sweep over receiver parameters.

## Next Recommended Work

1. Rewrite `scripts/10_demod_voice_fm_capture.py` into a stronger NBFM-style receiver.
2. Create `scripts/11_phase5c_receiver_sweep.py`.
3. Use the existing capture first; do not retransmit until software ceiling is checked.
4. Then run one fresh improved RF capture if needed.
5. Only document Phase 5C as final after receiver quality is understood.

## Do Not Forget

Do not commit every experimental artifact. Keep the repo readable.
Commit code, plans, logs, and this handoff first.
