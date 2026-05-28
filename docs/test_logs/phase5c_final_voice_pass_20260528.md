# ORION Phase 5C Final Voice Pass — 2026-05-28

## Purpose

Record the final Phase 5C voice-FM pass after fixing radio identity resolution and switching to full-message cyclic TX playback.

## Final Result

* **Status:** PASS
* **Link:** `149` transmit → `e9e` receive
* **Mode:** over-air bench voice-FM recovery
* **TX method:** `cyclic-full`
* **Recovered audio:** four repeated voice-message loops
* **Final evidence artifact:**

  * `data/audio/rx_voice_fm_cyclicfull_hifi_g35_tx32_final_trim_v2_20260528_164530_limited_cleaned_active.wav`

## Key Configuration

* **TX identity:** `149`
* **RX identity:** `e9e`
* **TX gain:** `-32 dB`
* **RX gain:** `35 dB`
* **Center frequency:** `915 MHz`
* **IQ rate:** `1.000 Msps`
* **TX waveform:** hi-fi voice-FM IQ
* **TX duration:** `20 s`
* **RX capture duration:** `30 s`
* **Demod chosen offset:** approximately `+126.50 kHz`
* **Channel SNR estimate:** approximately `39.65 dB`

## What Was Proven

* `src/orion/pluto_identity.py` successfully resolved radios by stable serial identity.
* `09_tx_play_voice_fm_iq.py` selected `149` by serial suffix instead of unstable USB path.
* `08_rx_voice_fm_capture.py` selected `e9e` by serial suffix instead of unstable URI assumptions.
* `cyclic-full` TX successfully repeated the full IQ message in hardware.
* The recovered audio contained approximately four full voice-message loops.
* The previous USB-path failure mode was removed from the Phase 5C test flow.

## Important Failure Mode Fixed

Earlier tests used USB paths such as `usb:1.6.5` and `usb:1.7.5` as if they were stable device identities.

That assumption was false.

The USB path changed between sessions, and `usb:1.6.5` was observed resolving to `e9e` instead of `149`.

The corrected workflow now uses:

* `--tx-id 149`
* `--rx-id e9e`

instead of relying on session-specific USB paths.

## Evidence Quality

* Start of final trimmed artifact contains about `1.5 s` of static.
* Middle of artifact contains four recovered voice-message loops.
* End of artifact contains about `0.5 s` of static.
* Voice is recovered clearly enough to demonstrate repeated over-air message transmission.
* Audio is not claimed to be final communications-grade quality.

## Honest Engineering Conclusion

Phase 5C demonstrated repeated over-air hi-fi voice-FM recovery from `149` to `e9e`.

The successful result depended on stable serial identity resolution and full-message cyclic TX playback.

The result should be described as a close-range bench demonstration of repeated SDR voice recovery, not as an optimized long-range or ISS-ready voice link.

## Safe Report Wording

> Phase 5C demonstrated repeated over-air voice-FM recovery from `149` to `e9e`. The transmitter used full-message cyclic playback of a pre-generated hi-fi voice-FM IQ waveform, while the receiver captured IQ from the serial-resolved `e9e` unit for offline demodulation. The final trimmed artifact recovered approximately four repeated voice-message loops, with short static regions before and after the useful transmission window. This validates the Phase 5C bench voice-link workflow while leaving RF range, robustness, and audio-quality optimization as future work.

## Do Not Claim

* ISS-ready voice quality
* long-range voice-link readiness
* clean final audio
* fully optimized FM receiver
* robust operation across antenna spacings
* general performance beyond this bench setup

## Next Work

* Patch `03_rx_live_gui.py` to use `--rx-id e9e`.
* Patch `04_tx_tone_low_power.py` to use `--tx-id 149`.
* Optionally regenerate compressed hi-fi IQ after finalizing the cyclic-full path.
* Preserve only selected final evidence artifacts.
* Avoid committing large generated sweeps unless explicitly needed.
