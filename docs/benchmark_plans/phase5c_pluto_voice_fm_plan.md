# ORION Phase 5C — Pluto-to-Pluto Voice FM Plan

## Objective

Demonstrate a short low-power Pluto-to-Pluto voice FM transmission using the Phase 5A microphone recording and Phase 5B offline FM waveform pipeline.

## Boundary

This phase is limited to a local bench Pluto-to-Pluto test.

- No handheld radio transmission
- No GMRS transmission
- No ISS-oriented transmission
- No external antenna
- No amplifier
- No ground-station rack equipment
- No coax connection unless verified attenuation is available
- Short duration only
- Abort immediately if behavior is unexpected

## Proposed Setup

- Transmitter: PLUTO B, serial ending `149`
- Receiver: PLUTO A, serial ending `e9e`
- Center frequency: 915.000 MHz
- Voice FM offset: baseband-centered, no intentional carrier offset unless needed
- TX gain: start at or below the previous safe low-power tone-test level
- TX audio source: Phase 5A Scarlett/SV200 WAV
- Modulation source: Phase 5B FM waveform generation logic
- RX evidence: saved IQ capture, metadata, spectrum plot, recovered WAV if demodulation succeeds

## Test Ladder

### Phase 5C-0 — RF Readiness Check

Confirm both PLUTOs are visible and correctly identified.

### Phase 5C-1 — Generate Pluto-Ready Voice FM IQ

Generate a finite complex64 IQ file from the Phase 5A WAV. No SDR, no RF.

### Phase 5C-2 — Receive-Only Baseline

Run PLUTO A receive-only capture at 915 MHz before transmission.

### Phase 5C-3 — Low-Power Voice FM Transmit

Transmit the finite FM IQ buffer from PLUTO B for a short duration only.

### Phase 5C-4 — Receive and Offline Demodulate

Capture IQ on PLUTO A, demodulate the received FM, and save recovered WAV.

## Success Criteria

- PLUTO A and PLUTO B are identified by serial number.
- Voice FM IQ generation completes offline.
- TX script has a dry-run mode and explicit RF confirmation flag.
- RX capture produces saved IQ and metadata.
- Recovered audio is intelligible.
- All artifacts are saved and logged.

## Abort Criteria

Abort immediately if:

- Wrong PLUTO identity is detected
- Transmit URI is ambiguous
- TX gain is not explicitly low
- RX plot shows unexpected saturation
- Script fails to stop TX cleanly
- Operator is uncertain about RF state

## Interpretation

A successful Phase 5C would demonstrate a local bench voice-FM SDR path. It would not constitute an ISS communication test, handheld-radio compatibility test, calibrated link-budget result, or legal authorization for broader RF operation.
