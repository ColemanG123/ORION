# ORION Test Log

| Date/Time | Phase | Test | Setup | Result | Evidence File | Notes |
|---|---|---|---|---|---|---|
| 2026-05-10 12:44 | Phase 1 | ADALM-PLUTO detection | pyadi-iio + pylibiio + 00_list_plutos.py | PARTIAL PASS — at least one PLUTO reachable; unique-device confirmation still required | hardware_status.md | Connected: usb:, ip:pluto.local, usb:1.6.5 |
| 2026-05-10 12:XX | Phase 1B | Unique PLUTO identification | pyadi-iio + pylibiio + 00_list_plutos.py | PARTIAL PASS — one unique PLUTO confirmed; second physical PLUTO not detected | hardware_status.md | Working serial: 1044734c9605000308000b003535507e9e; expected second serial: 1044734c96050007e9ff160082b24f2149 |
| 2026-05-10 12:XX | Phase 1B | Unique PLUTO identification with both devices connected | Replaced suspect USB cable; both PLUTOs connected | PASS — two unique ADALM-PLUTOs confirmed | hardware_status.md | PLUTO A: v0.39 AD9364; PLUTO B: v0.38 AD9363A |
| 2026-05-10 13:34 | Phase 2B | RX repeatability summary | 02_rx_repeatability_summary.py (offline) | PASS | phase2_summary.md | 2 capture(s) processed, labels: pluto_a, pluto_b |
| 2026-05-10 13:34 | Phase 2 | RX spectrum probe | usb:1.8.5 @ 915.000MHz 1.000Msps slow_attack | PASS | spectrum_pluto_a_repeat_20260510_133427.png | label=pluto_a_repeat  peak=-47.7dBFS  floor=-87.2dBFS  peak_off=+0.059MHz |
| 2026-05-10 13:34 | Phase 2 | RX spectrum probe | usb:1.7.5 @ 915.000MHz 1.000Msps slow_attack | PASS | spectrum_pluto_b_repeat_20260510_133433.png | label=pluto_b_repeat  peak=-43.9dBFS  floor=-88.4dBFS  peak_off=+0.060MHz |
| 2026-05-10 13:34 | Phase 2B | RX repeatability summary | 02_rx_repeatability_summary.py (offline) | PASS | phase2_summary.md | 4 capture(s) processed, labels: pluto_a, pluto_a_repeat, pluto_b, pluto_b_repeat |
| 2026-05-10 13:38 | Phase 2B | RX repeatability summary | 02_rx_repeatability_summary.py (offline) | PASS | phase2_summary.md | 4 capture(s) processed, labels: pluto_a, pluto_b |
| 2026-05-10 13:45 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_a uri=usb:1.8.5 freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 13:45 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 84 frame(s) | — | label=pluto_a uri=usb:1.8.5 freq=915.000MHz frames=84 |
| 2026-05-10 13:46 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_b uri=usb:1.7.5 freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 13:46 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 52 frame(s) | — | label=pluto_b uri=usb:1.7.5 freq=915.000MHz frames=52 |
| 2026-05-10 | Phase 3B | GUI polish and documentation | 03_rx_live_gui.py + README.md + docs/gui_live_spectrum.md + decisions.md | COMPLETE | gui_live_spectrum.md | Window title, plot title, RX-ONLY badge added; README and GUI docs written |
| 2026-05-10 13:53 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_a uri=usb:1.8.5 freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 13:53 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 61 frame(s) | — | label=pluto_a uri=usb:1.8.5 freq=915.000MHz frames=61 |
| 2026-05-10 13:56 | Phase 1B | PLUTO unique-device ID | pyadi-iio + pylibiio + 00_list_plutos.py | PASS — ONE_UNIQUE_DEVICE_CONFIRMED | hardware_status.md | Connected URIs: usb:, ip:pluto.local, ip:192.168.2.1, usb:1.7.5 |
| 2026-05-10 | Phase 4-prep | TX tone safety plan and operator checklist | documentation only — no TX code written, no transmission performed | COMPLETE | phase4_low_power_tone_plan.md | Pluto B TX @ 915 MHz +100 kHz, Pluto A RX; coax deferred; conducted test deferred pending attenuators |
| 2026-05-10 14:00 | Phase 3 | RX live GUI | 03_rx_live_gui.py | FAIL — No device found | — | label=pluto_a_rx_observer uri=usb:1.8.5 |
| 2026-05-10 14:00 | Phase 1B | PLUTO unique-device ID | pyadi-iio + pylibiio + 00_list_plutos.py | PASS — TWO_UNIQUE_DEVICES_CONFIRMED | hardware_status.md | Connected URIs: ip:pluto.local, usb:1.6.5, ip:192.168.2.1, usb:1.7.5 |
| 2026-05-10 14:03 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_a_rx_observer uri=ip:pluto.local freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 14:03 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 7 frame(s) | — | label=pluto_a_rx_observer uri=ip:pluto.local freq=915.000MHz frames=7 |
| 2026-05-10 14:04 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_a_rx_baseline uri=ip:pluto.local freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 14:04 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 40 frame(s) | — | label=pluto_a_rx_baseline uri=ip:pluto.local freq=915.000MHz frames=40 |
| 2026-05-10 14:10 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_a_phase4_observer uri=ip:pluto.local freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 14:17 | Phase 4A | TX tone (low power over-air) | 04_tx_tone_low_power.py | STARTED | — | label=pluto_b_tx_tone uri=ip:192.168.2.1 freq=915.000MHz offset=+100kHz gain=-40dB amp=0.100 dur=10.0s |
| 2026-05-10 14:17 | Phase 4A | TX tone (low power over-air) | 04_tx_tone_low_power.py | STOPPED | — | label=pluto_b_tx_tone |
| 2026-05-10 14:18 | Phase 4A | TX tone (low power over-air) | 04_tx_tone_low_power.py | STARTED | — | label=pluto_b_tx_tone uri=ip:192.168.2.1 freq=915.000MHz offset=+100kHz gain=-40dB amp=0.100 dur=10.0s |
| 2026-05-10 14:18 | Phase 4A | TX tone (low power over-air) | 04_tx_tone_low_power.py | STOPPED | — | label=pluto_b_tx_tone |
| 2026-05-10 14:18 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 881 frame(s) | — | label=pluto_a_phase4_observer uri=ip:pluto.local freq=915.000MHz frames=881 |
| 2026-05-10 14:20 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_a_phase4_observer\ uri=ip:pluto.local freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 14:20 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 28 frame(s) | — | label=pluto_a_phase4_observer\ uri=ip:pluto.local freq=915.000MHz frames=28 |
| 2026-05-10 14:20 | Phase 3 | RX live GUI | 03_rx_live_gui.py | STARTED | — | label=pluto_a_phase4_observer\ uri=ip:pluto.local freq=915.000MHz rate=1.000Msps gain=slow_attack |
| 2026-05-10 14:21 | Phase 4A | TX tone (low power over-air) | 04_tx_tone_low_power.py | STARTED | — | label=pluto_b_tx_tone uri=ip:192.168.2.1 freq=915.000MHz offset=+100kHz gain=-40dB amp=0.100 dur=30.0s |
| 2026-05-10 14:21 | Phase 4A | TX tone (low power over-air) | 04_tx_tone_low_power.py | STOPPED | — | label=pluto_b_tx_tone |
| 2026-05-10 14:22 | Phase 3 | RX live GUI | 03_rx_live_gui.py | CLOSED after 152 frame(s) | — | label=pluto_a_phase4_observer\ uri=ip:pluto.local freq=915.000MHz frames=152 |
