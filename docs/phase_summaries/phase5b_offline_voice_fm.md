# ORION Phase 5B — Offline Voice FM Test Summary

## Objective

Verify the voice waveform processing path in software before involving any SDR hardware or RF transmission.

## Setup

- Input audio: Phase 5A Scarlett/SV200 microphone WAV
- Script: `scripts/06_offline_voice_fm_test.py`
- SDR/RF status: no SDR, no RF, no transmission

## Method

The Phase 5B script loads the captured WAV, conditions the speech audio, generates a simulated complex FM IQ waveform, demodulates the FM waveform, saves the recovered audio, and produces comparison plots and JSON metadata.

Two offline cases were tested:

1. Communications-grade voice:
   - Speech band: 100 Hz to 3400 Hz
   - FM deviation: 5 kHz
   - IQ rate: 240 kHz

2. Higher-fidelity demo voice:
   - Speech band: 60 Hz to 8000 Hz
   - FM deviation: 15 kHz
   - IQ rate: 240 kHz

## Result

Phase 5B passed. Both offline FM paths produced intelligible recovered audio. The higher-fidelity demo case sounded significantly clearer and produced the best numerical recovery result.

## Key Metrics

### Communications-Grade Case

- Correlation, conditioned vs. recovered: 0.9885
- Recovery error RMS: 0.01950
- Verdict: PASS

### Higher-Fidelity Demo Case

- Correlation, conditioned vs. recovered: 0.9995
- Recovery error RMS: 0.00420
- Verdict: PASS

## Interpretation

The ORION voice-processing path is functional in software. The narrower communications-grade case sounds more muffled because the speech bandwidth is intentionally limited to approximately telephone/radio voice bandwidth. The higher-fidelity case preserves more high-frequency speech detail and is better for demonstration, but it would occupy more bandwidth in an RF implementation.

## Evidence

- `data/audio/fm_scarlett_sv200_fm_offline_20260522_161722.png`
- `data/audio/fm_scarlett_sv200_fm_offline_20260522_161722.json`
- `data/audio/fm_scarlett_sv200_fm_offline_20260522_161722_recovered.wav`
- `data/audio/fm_scarlett_sv200_fm_hifi_20260522_161832.png`
- `data/audio/fm_scarlett_sv200_fm_hifi_20260522_161832.json`
- `data/audio/fm_scarlett_sv200_fm_hifi_20260522_161832_recovered.wav`

## Next Step

Proceed to Phase 5C planning: Pluto-to-Pluto voice over SDR. Before any RF voice transmission, define the legal/safety boundary, occupied bandwidth, center frequency, transmit gain, receive configuration, and abort criteria.
