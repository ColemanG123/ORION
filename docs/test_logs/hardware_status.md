# ORION Hardware Status

## Location

Innovation Lab / Toomey Hall, Missouri S&T

## Phase 1B Detection Run — 2026-05-23 18:19

### Python Package Availability

- `import adi`: **YES**
- `import iio`: **YES**

### URI Comparison Table

| URI | Connected | hw_serial | hw_model | dna/serial | USB path | IP addr | Fingerprint |
|-----|-----------|-----------|----------|------------|----------|---------|-------------|
| `usb:` | NO | — | — | — | — | — | — |
| `ip:pluto.local` | YES | 1044734c9605000308000b003535507e9e | Analog Devices PlutoSDR Rev.C (Z7010-AD9364) | — | — | pluto.local | `1044734c9605000308000b003535507e9e` |
| `ip:192.168.2.1` | NO | — | — | — | — | 192.168.2.1 | — |
| `ip:192.168.3.1` | YES | 1044734c9605000308000b003535507e9e | Analog Devices PlutoSDR Rev.C (Z7010-AD9364) | — | — | 192.168.3.1 | `1044734c9605000308000b003535507e9e` |
| `usb:1.6.5` | YES | 1044734c9605000308000b003535507e9e | Analog Devices PlutoSDR Rev.C (Z7010-AD9364) | — | 1.6.5 | — | `1044734c9605000308000b003535507e9e` |
| `usb:1.7.5` | YES | 1044734c96050007e9ff160082b24f2149 | Analog Devices PlutoSDR Rev.C (Z7010-AD9363A) | — | 1.7.5 | — | `1044734c96050007e9ff160082b24f2149` |

### Physical Device Groups

**Device 1** (fingerprint: `1044734c9605000308000b003535507e9e`)
- `ip:pluto.local`
- `ip:192.168.3.1`
- `usb:1.6.5`

**Device 2** (fingerprint: `1044734c96050007e9ff160082b24f2149`)
- `usb:1.7.5`

### Conclusion

**`TWO_UNIQUE_DEVICES_CONFIRMED`**

Distinct fingerprints found — TWO (or more) physical devices:
  Device 1: fingerprint '1044734c9605000308000b003535507e9e' → ['ip:pluto.local', 'ip:192.168.3.1', 'usb:1.6.5']
  Device 2: fingerprint '1044734c96050007e9ff160082b24f2149' → ['usb:1.7.5']

### Per-URI Detail

#### `usb:`

- **Connected**: No
- **Error**: `[Errno 0] No error`

#### `ip:pluto.local`

- **Connected**: Yes
- **Context description**: fe80::205:f7ff:fe68:5d67%ethernet_32775 Linux (none) 6.1.0-gf3da30df6004 #5 SMP PREEMPT Tue Oct 15 10:50:00 CEST 2024 armv7l
- **hw_serial** *(primary ID)*: `1044734c9605000308000b003535507e9e`
- **hw_model**: Analog Devices PlutoSDR Rev.C (Z7010-AD9364)
- **IP/hostname**: pluto.local
- **Context attributes**:
  - `ad9361-phy,model`: ad9364
  - `ad9361-phy,xo_correction`: 39999835
  - `fw_version`: v0.39
  - `hw_model`: Analog Devices PlutoSDR Rev.C (Z7010-AD9364)
  - `hw_model_variant`: 1
  - `hw_serial`: 1044734c9605000308000b003535507e9e
  - `ip,ip-addr`: fe80::205:f7ff:fe68:5d67%ethernet_32775
  - `local,kernel`: 6.1.0-gf3da30df6004
  - `uri`: ip:pluto.local
- **Context XML (first 600 chars)**:
  ```xml
  <?xml version="1.0" encoding="utf-8"?><!DOCTYPE context [<!ELEMENT context (device | context-attribute)*><!ELEMENT context-attribute EMPTY><!ELEMENT device (channel | attribute | debug-attribute | buffer-attribute)*><!ELEMENT channel (scan-element?, attribute*)><!ELEMENT attribute EMPTY><!ELEMENT scan-element EMPTY><!ELEMENT debug-attribute EMPTY><!ELEMENT buffer-attribute EMPTY><!ATTLIST context name CDATA #REQUIRED version-major CDATA #REQUIRED version-minor CDATA #REQUIRED version-git CDATA #REQUIRED description CDATA #IMPLIED><!ATTLIST context-attribute name CDATA #REQUIRED value CDATA #RE
  ```

#### `ip:192.168.2.1`

- **Connected**: No
- **Error**: `[Errno 0] No error`
- **IP/hostname**: 192.168.2.1

#### `ip:192.168.3.1`

- **Connected**: Yes
- **Context description**: 192.168.3.1 Linux (none) 6.1.0-gf3da30df6004 #5 SMP PREEMPT Tue Oct 15 10:50:00 CEST 2024 armv7l
- **hw_serial** *(primary ID)*: `1044734c9605000308000b003535507e9e`
- **hw_model**: Analog Devices PlutoSDR Rev.C (Z7010-AD9364)
- **IP/hostname**: 192.168.3.1
- **Context attributes**:
  - `ad9361-phy,model`: ad9364
  - `ad9361-phy,xo_correction`: 39999835
  - `fw_version`: v0.39
  - `hw_model`: Analog Devices PlutoSDR Rev.C (Z7010-AD9364)
  - `hw_model_variant`: 1
  - `hw_serial`: 1044734c9605000308000b003535507e9e
  - `ip,ip-addr`: 192.168.3.1
  - `local,kernel`: 6.1.0-gf3da30df6004
  - `uri`: ip:192.168.3.1
- **Context XML (first 600 chars)**:
  ```xml
  <?xml version="1.0" encoding="utf-8"?><!DOCTYPE context [<!ELEMENT context (device | context-attribute)*><!ELEMENT context-attribute EMPTY><!ELEMENT device (channel | attribute | debug-attribute | buffer-attribute)*><!ELEMENT channel (scan-element?, attribute*)><!ELEMENT attribute EMPTY><!ELEMENT scan-element EMPTY><!ELEMENT debug-attribute EMPTY><!ELEMENT buffer-attribute EMPTY><!ATTLIST context name CDATA #REQUIRED version-major CDATA #REQUIRED version-minor CDATA #REQUIRED version-git CDATA #REQUIRED description CDATA #IMPLIED><!ATTLIST context-attribute name CDATA #REQUIRED value CDATA #RE
  ```

#### `usb:1.6.5`

- **Connected**: Yes
- **Context description**: Linux (none) 6.1.0-gf3da30df6004 #5 SMP PREEMPT Tue Oct 15 10:50:00 CEST 2024 armv7l
- **hw_serial** *(primary ID)*: `1044734c9605000308000b003535507e9e`
- **hw_model**: Analog Devices PlutoSDR Rev.C (Z7010-AD9364)
- **USB path**: 1.6.5
- **Context attributes**:
  - `ad9361-phy,model`: ad9364
  - `ad9361-phy,xo_correction`: 39999835
  - `fw_version`: v0.39
  - `hw_model`: Analog Devices PlutoSDR Rev.C (Z7010-AD9364)
  - `hw_model_variant`: 1
  - `hw_serial`: 1044734c9605000308000b003535507e9e
  - `local,kernel`: 6.1.0-gf3da30df6004
  - `uri`: usb:1.6.5
  - `usb,idProduct`: b673
  - `usb,idVendor`: 0456
  - `usb,libusb`: 1.0.24.11584
  - `usb,product`: PlutoSDR (ADALM-PLUTO)
  - `usb,release`: 2.0
  - `usb,serial`: 1044734c9605000308000b003535507e9e
  - `usb,vendor`: Analog Devices Inc.
- **Context XML (first 600 chars)**:
  ```xml
  <?xml version="1.0" encoding="utf-8"?><!DOCTYPE context [<!ELEMENT context (device | context-attribute)*><!ELEMENT context-attribute EMPTY><!ELEMENT device (channel | attribute | debug-attribute | buffer-attribute)*><!ELEMENT channel (scan-element?, attribute*)><!ELEMENT attribute EMPTY><!ELEMENT scan-element EMPTY><!ELEMENT debug-attribute EMPTY><!ELEMENT buffer-attribute EMPTY><!ATTLIST context name CDATA #REQUIRED version-major CDATA #REQUIRED version-minor CDATA #REQUIRED version-git CDATA #REQUIRED description CDATA #IMPLIED><!ATTLIST context-attribute name CDATA #REQUIRED value CDATA #RE
  ```

#### `usb:1.7.5`

- **Connected**: Yes
- **Context description**: Linux (none) 5.15.0-175882-ge14e351533f9 #1 SMP PREEMPT Fri Nov 17 10:23:58 CET 2023 armv7l
- **hw_serial** *(primary ID)*: `1044734c96050007e9ff160082b24f2149`
- **hw_model**: Analog Devices PlutoSDR Rev.C (Z7010-AD9363A)
- **USB path**: 1.7.5
- **Context attributes**:
  - `ad9361-phy,model`: ad9363a
  - `ad9361-phy,xo_correction`: 39999904
  - `fw_version`: v0.38
  - `hw_model`: Analog Devices PlutoSDR Rev.C (Z7010-AD9363A)
  - `hw_model_variant`: 1
  - `hw_serial`: 1044734c96050007e9ff160082b24f2149
  - `local,kernel`: 5.15.0-175882-ge14e351533f9
  - `uri`: usb:1.7.5
  - `usb,idProduct`: b673
  - `usb,idVendor`: 0456
  - `usb,libusb`: 1.0.24.11584
  - `usb,product`: PlutoSDR (ADALM-PLUTO)
  - `usb,release`: 2.0
  - `usb,serial`: 1044734c96050007e9ff160082b24f2149
  - `usb,vendor`: Analog Devices Inc.
- **Context XML (first 600 chars)**:
  ```xml
  <?xml version="1.0" encoding="utf-8"?><!DOCTYPE context [<!ELEMENT context (device | context-attribute)*><!ELEMENT context-attribute EMPTY><!ELEMENT device (channel | attribute | debug-attribute | buffer-attribute)*><!ELEMENT channel (scan-element?, attribute*)><!ELEMENT attribute EMPTY><!ELEMENT scan-element EMPTY><!ELEMENT debug-attribute EMPTY><!ELEMENT buffer-attribute EMPTY><!ATTLIST context name CDATA #REQUIRED version-major CDATA #REQUIRED version-minor CDATA #REQUIRED version-git CDATA #REQUIRED description CDATA #IMPLIED><!ATTLIST context-attribute name CDATA #REQUIRED value CDATA #RE
  ```

## Current Setup

- Two ADALM-PLUTO SDRs physically present
- Both connected to powered ONN USB hub
- Hub connected to ASUS ProArt P16 laptop
- Small antennas available
- Two coax cables available
- No verified attenuators currently available

## Open Issues

- ~~Both PLUTOs detected and two unique devices confirmed~~ ✓ Resolved — Phase 1B PASS
- ~~Firmware recovery~~ ✓ Not required — both PLUTOs functional
- USB bus-path URIs change on re-enumeration — use `ip:pluto.local` / `ip:192.168.2.1` for all routine operation
- No verified attenuators available — conducted coax testing deferred
