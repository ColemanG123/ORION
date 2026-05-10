# CRC and Packet Framing

## Definitions

**Packet framing**: structuring a digital message into a standardized format
with a header (sync word, source/destination address, length), payload (data),
and trailer (error-detection code). Enables the receiver to identify message
boundaries and verify data integrity.

**CRC (Cyclic Redundancy Check)**: a mathematical checksum appended to a packet.
The receiver recomputes the CRC over the received data and compares it to the
transmitted value. A mismatch indicates a bit error in the received packet.
Common variants: CRC-16 (2-byte check), CRC-32 (4-byte check).

## ORION Packet Concept

Packet TX/RX with CRC validation is planned for **Phase 5** (not yet
implemented). The intended design:

1. Transmitter constructs a fixed-length packet: sync word + payload + CRC-32
2. Transmitter modulates the packet onto a carrier (modulation scheme TBD)
3. Receiver demodulates and extracts the packet bytes
4. Receiver checks CRC — PASS or FAIL per packet
5. System reports Packet Error Rate (PER) over a test run

No modulation, framing, or CRC code exists in the current ORION codebase.
Phase 4A tested only a raw CW tone with no data payload.

## Test Notes

- Phase 4A confirmed that Pluto B can transmit and Pluto A can observe an
  over-air signal at low power. This is the prerequisite for packet testing.
- Modulation scheme (BPSK, GMSK, etc.) will be selected during Phase 5 design.
- `examples/config_example.yaml` previously listed BPSK and CRC32 as fields —
  those have been removed as they were forward-looking placeholders.
