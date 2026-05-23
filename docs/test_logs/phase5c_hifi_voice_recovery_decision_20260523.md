# ORION Phase 5C Hi-Fi Voice Recovery Decision — 2026-05-23

## Purpose

This note records the Phase 5C decision to switch the primary quality path from comms-grade voice FM to hi-fi voice FM after successful repeated over-air recovery.

## Current Verified State

- `e9e` is the receive/default observer.
- `149` is the transmit/secondary unit.
- Serial suffix names are the authoritative device identities.
- Full-message chunked TX from `149` has been verified visually and by console output.
- A 20-second TX loop produced approximately four message wraps.
- The `+0.100 MHz` RF feature stayed visible on `e9e` for the full 20-second transmission.
- The recovered comms-grade message repeated four times in demodulated audio.
- The recovered hi-fi message was significantly clearer than the comms-grade version.

## Key Loop Verification

The long TX verification showed:

- full IQ message length: approximately `5.000 s`
- TX duration: approximately `20.000 s`
- expected message repetitions: approximately `4x`
- observed message repetitions in recovered audio: `4x`
- TX console reported message wraps: `4`

Conclusion:

`09_tx_play_voice_fm_iq.py` is correctly streaming the full IQ message, wrapping back to the beginning, and continuing until the requested TX duration expires.

## Hi-Fi Recovery Result

The hi-fi waveform recovered with noticeably better clarity than the comms-grade waveform.

Observed hi-fi audio defects:

- crackle on loud consonants/vowels,
- high-pitched ringing,
- subtle static,
- voice is much clearer overall than comms-grade.

Diagnostic results from the first hi-fi recovery showed:

- no final-WAV digital clipping,
- chosen received offset near `+126.75 kHz`,
- dominant high-frequency ringing candidates near `4043 Hz` and `4603 Hz`,
- final-audio clipping fractions near zero,
- crackle likely caused by RF/demod/gain/deviation behavior rather than final WAV clipping.

## Hi-Fi Receiver Sweep Decision

A focused hi-fi receiver sweep was run to test:

- deviation mismatch,
- channel bandwidth,
- light de-emphasis,
- high-frequency cleanup,
- notches near the ringing tones,
- limiter effects.

Best subjective profile:

`h12_deemp50_notch_both`

Reason:

- very clear voice,
- only one major crackle at the start,
- better overall quality than comms-grade.

Backup profile:

`h13_deemp75_notch_both`

Reason:

- less crackle overall,
- slightly more smoothed/muffled due to stronger de-emphasis.

Warmth comparison:

`h14_clean7000_notch_both`

Reason:

- sounded good,
- slightly less warmth in the voice.

Profiles that should not be treated as final:

- `h08_cut25_notch_both`
- `h09_cut30_notch_both`
- `h15_clean6000_notch_both`

Reason:

- worsened crackle,
- removed too much quality,
- or did not improve intelligibility.

## Final Phase 5C Quality Direction

Primary quality path:

`hi-fi voice FM`

Primary evidence profile:

`h12_deemp50_notch_both`

Fallback clean/crackle-minimized profile:

`h13_deemp75_notch_both`

Robust fallback profile:

`comms-grade p02_lp9_limited_clean`

## Engineering Interpretation

Comms-grade voice FM was the correct foothold for proving the RF voice link.

Hi-fi voice FM is now the better path for quality because it preserved more of the original microphone clarity and produced a more intelligible recovered voice, despite remaining crackle/ringing artifacts.

The current remaining defects are likely not final WAV clipping. They are more likely caused by:

- RF gain balance,
- 149 TX gain being too strong for the current geometry,
- e9e RX gain/saturation behavior,
- deviation/channel-filter mismatch,
- residual frequency/ringing artifacts.

## Next Experiment

Run a fresh hi-fi RF capture with slightly reduced TX strength to test whether crackle improves.

Recommended next test:

- waveform: existing hi-fi IQ file,
- `149` TX gain: `-35 dB`,
- `e9e` RX gain: `25 dB`,
- TX duration: `20 s`,
- RX duration: `30 s`,
- demod profile: h12-like settings.

If crackle improves while clarity remains good, the issue was likely TX/RF overdrive or receive-chain stress.

If crackle worsens or voice becomes too weak, return to `-32 dB` and test lower `e9e` RX gain instead.

## Locked h12-Like Demod Settings

Use this profile first for new hi-fi captures:

- expected offset: `127000 Hz`
- offset span: `20000 Hz`
- offset step: `250 Hz`
- analysis band: `25000 Hz`
- deviation: `15000 Hz`
- channel cutoff: `35000 Hz`
- demod rate: `200000 Hz`
- lowcut: `60 Hz`
- highcut: `8000 Hz`
- clean lowcut: `60 Hz`
- clean highcut: `8000 Hz`
- de-emphasis: `50 us`
- notch frequencies: `4043 Hz`, `4603 Hz`
- notch Q: `35`
- trim active start: `0.4 s`

## Safe Report Wording

> Phase 5C demonstrated repeated over-air hi-fi voice recovery from `149` to `e9e`. The recovered hi-fi audio was significantly clearer than the earlier comms-grade recovery, though it retained crackle on loud sounds, high-frequency ringing, and subtle static. Receiver-side sweep results selected a hi-fi de-emphasis/notch profile as the best current evidence artifact. Further quality improvement should focus on RF gain balance and fresh capture quality.

Avoid claiming:

- clean hi-fi voice recovery,
- final optimized audio,
- ISS-ready voice quality,
- fully solved RF link quality.
