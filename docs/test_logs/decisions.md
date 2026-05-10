# ORION Engineering Decisions

## Initial Decisions

1. Project named **ORION**.
2. ORION will be framed as an ADALM-PLUTO SDR test kit for message transmission, signal characterization, and satellite-link readiness.
3. MVP emphasizes repeatable burst packet TX/RX, CRC validation, signal metrics, and live visualization.
4. Direct coax testing requires attenuation. Initial no-attenuator testing should use low-power over-air setup.
5. Voice transmission is future work unless the core system is complete.
6. GUI is in scope as a lightweight live visualization and demo layer.
7. iio-oscilloscope and GNU Radio may be used as diagnostic/support tools, but the final demo may use a custom ORION GUI.
8. Active working directory changed to E:\ORION.
9. Firmware update deferred. Both PLUTOs are currently detectable and functional; updating firmware would introduce unnecessary risk before receive-only and low-power tests.
10. A suspect USB cable was identified as the likely cause of earlier one-device detection behavior.
11. Phase 3B (GUI polish and documentation) was prioritized before Phase 4 TX implementation to stabilize and document the live visualization layer. A working, documented RX baseline reduces risk when TX is introduced and gives the project a clean demo-ready state at the receive-only boundary.
12. The live GUI (`03_rx_live_gui.py`) is treated as a demonstration and diagnostic layer, not a replacement for calibrated RF equipment. dBFS readings are relative to the ADC full scale and require a known reference signal for conversion to dBm. All spectrum observations are indicative, not metrological.
13. Phase 4 begins with a low-power over-air CW tone visibility test rather than a conducted (coax) link test. Conducted testing is deferred because no verified attenuators are available; connecting Pluto A and Pluto B directly via coax without attenuation risks driving the RX input above its safe limit (~+2.5 dBm) and damaging the hardware. Free-space path loss at 1–3 m on the benchtop provides passive attenuation sufficient for an initial tone test at low TX gain.
14. The Phase 4 tone test is intentionally minimal: a single CW tone with no modulation, no encoding, and no packet structure. The only objective is to confirm that a known spectral feature appears at the receiver and disappears when TX stops. Packet communication testing is deferred to Phase 5.
15. USB bus-path URIs (`usb:x.x.x`) are not stable device identifiers. Windows re-enumerates the USB hub on reconnect, reassigning paths. Authoritative identity is `hw_serial` (read-only from the device). Preferred runtime URIs are `ip:pluto.local` (Pluto A, serial ending `e9e`) and `ip:192.168.2.1` (Pluto B, serial ending `149`). All future-facing commands and documentation use IP URIs. USB paths observed in historical logs are preserved as-is.