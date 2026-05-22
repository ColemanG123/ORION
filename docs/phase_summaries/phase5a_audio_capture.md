# ORION Phase 5A — Audio Capture Probe Summary

## Objective

Verify that the microphone/audio-interface path works before attempting any SDR voice transmission.

## Setup

- Microphone: Shure SV200
- Audio interface: Scarlett Solo USB
- Windows input device: Microphone (Scarlett Solo USB)
- Script: `scripts/05_audio_capture_probe.py`
- SDR/RF status: no SDR, no RF, no transmission

## Result

Phase 5A passed. The system successfully captured a 5-second microphone recording through the Scarlett Solo into Python and saved a WAV file, JSON metadata, and waveform/spectrum plot.

## Key Metrics

- Sample rate: 44,100 Hz
- Channels: 1
- Duration: 5.0 s
- Frames: 220,500
- Peak amplitude: 0.4966
- RMS amplitude: 0.0810
- Clipping fraction: 0.000000

## Interpretation

The audio input chain is usable for future offline voice waveform testing. The gain level is strong enough for modulation experiments without clipping. Minor plosive/static artifacts may be improved with a pop filter or foam windscreen, but the capture quality is sufficient for Phase 5B.

## Evidence

- `data/audio/audio_scarlett_sv200_test_20260522_160706.wav`
- `data/audio/audio_scarlett_sv200_test_20260522_160706.json`
- `data/audio/audio_scarlett_sv200_test_20260522_160706.png`

## Next Step

Proceed to Phase 5B: offline voice modulation/demodulation. This phase should use the saved WAV file as input and should not use SDR hardware or RF transmission.
