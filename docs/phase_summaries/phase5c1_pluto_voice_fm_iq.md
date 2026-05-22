# ORION Phase 5C-1 — Pluto-Ready Voice FM IQ Generation Summary

## Objective

Generate a Pluto-ready complex FM voice IQ waveform from the Phase 5A Scarlett/SV200 microphone recording before attempting any SDR transmission.

## Setup

- Input audio: `data/audio/audio_scarlett_sv200_test_20260522_160706.wav`
- Script: `scripts/07_generate_pluto_voice_fm_iq.py`
- SDR/RF status: no SDR, no RF, no transmission
- Intended future RF center: 915.000 MHz
- Baseband carrier offset: +100 kHz

## Configuration

- IQ sample rate: 1.000 Msps
- FM deviation: 15 kHz
- Speech band: 60 Hz to 8000 Hz
- IQ amplitude: 0.100
- IQ dtype: complex64

## Result

Phase 5C-1 passed. The script generated a finite complex FM IQ waveform suitable for later controlled Pluto playback, along with a conditioned WAV, preview recovered WAV, JSON metadata, and plot.

## Key Metrics

- Preview correlation, conditioned vs. recovered: 0.9995
- Preview error RMS: 0.00420
- Verdict: PASS

## Interpretation

The generated waveform preserves the Phase 5B high-fidelity voice path while shifting the complex FM signal to a +100 kHz baseband offset. This offset matches the earlier Phase 4A tone-test strategy and gives the receiver a clear expected location in the spectrum. The waveform has not yet been transmitted.

## Evidence

- `data/audio/pluto_voice_fm_scarlett_sv200_pluto_hifi_20260522_162330_iq.npy`
- `data/audio/pluto_voice_fm_scarlett_sv200_pluto_hifi_20260522_162330_conditioned.wav`
- `data/audio/pluto_voice_fm_scarlett_sv200_pluto_hifi_20260522_162330_preview_recovered.wav`
- `data/audio/pluto_voice_fm_scarlett_sv200_pluto_hifi_20260522_162330.json`
- `data/audio/pluto_voice_fm_scarlett_sv200_pluto_hifi_20260522_162330.png`

## Next Step

Proceed to Phase 5C-2 receive-only baseline on PLUTO A before any RF playback. Transmission should remain disabled until the receive baseline, transmit script dry run, and safety checklist are complete.
