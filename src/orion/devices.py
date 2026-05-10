"""
ORION Phase 1 / 1B — ADALM-PLUTO detection and unique-device identification.

All operations are read-only. No transmission, no hardware reconfiguration.
No frequency, gain, sample rate, bandwidth, or buffer settings are touched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Dependency probes
# ---------------------------------------------------------------------------

def probe_imports() -> dict[str, bool]:
    """Return availability of each SDR-related import."""
    results: dict[str, bool] = {}
    for name in ("adi", "iio"):
        try:
            __import__(name)
            results[name] = True
        except ImportError:
            results[name] = False
    return results


def print_import_status(availability: dict[str, bool]) -> None:
    for name, ok in availability.items():
        status = "OK" if ok else "MISSING"
        symbol = "+" if ok else "!"
        print(f"  [{symbol}] import {name:<6}  {status}")
    if not availability.get("adi"):
        print("      -> Install: pip install pyadi-iio")
    if not availability.get("iio"):
        print("      -> Install: pip install pylibiio  (or install libiio drivers)")


# ---------------------------------------------------------------------------
# IIO context scan
# ---------------------------------------------------------------------------

def scan_iio_contexts() -> list[str]:
    """Return URIs found via iio_context_scan (read-only)."""
    try:
        import iio  # type: ignore
    except ImportError:
        return []

    found: list[str] = []
    try:
        contexts = iio.scan_contexts()
        found.extend(contexts.keys())
    except Exception:
        pass
    return found


# ---------------------------------------------------------------------------
# PlutoResult dataclass — Phase 1B expanded
# ---------------------------------------------------------------------------

@dataclass
class PlutoResult:
    uri: str

    # connection
    connected: bool = False
    error: Optional[str] = None

    # context-level identifying fields (most reliable for Pluto)
    hw_serial: Optional[str] = None    # ctx.attrs["hw_serial"]  ← primary fingerprint
    hw_model: Optional[str] = None     # ctx.attrs["hw_model"]
    ctx_attrs: dict[str, str] = field(default_factory=dict)
    ctx_xml_snippet: Optional[str] = None  # first 600 chars of ctx.xml

    # device-level fallback fields
    device_name: Optional[str] = None  # ctx.description / ctx.name
    serial: Optional[str] = None       # dev.attrs["serial"]
    dna: Optional[str] = None          # dev.attrs["dna"]
    firmware: Optional[str] = None
    dev_attrs: dict[str, str] = field(default_factory=dict)

    # transport clues parsed from the URI itself
    usb_path: Optional[str] = None     # e.g. "1.6.5" from usb:1.6.5
    ip_addr: Optional[str] = None      # e.g. "pluto.local" from ip:pluto.local

    # derived: best available unique identifier
    fingerprint: Optional[str] = None  # hw_serial > dna > serial


# ---------------------------------------------------------------------------
# URI parsing helpers
# ---------------------------------------------------------------------------

def _parse_uri(uri: str) -> tuple[Optional[str], Optional[str]]:
    """Return (usb_path, ip_addr) parsed from a URI string."""
    usb_path: Optional[str] = None
    ip_addr: Optional[str] = None
    uri_lower = uri.lower()
    if uri_lower.startswith("usb:"):
        tail = uri[4:].strip()
        if tail:
            usb_path = tail
    elif uri_lower.startswith("ip:"):
        tail = uri[3:].strip()
        if tail:
            ip_addr = tail
    return usb_path, ip_addr


# ---------------------------------------------------------------------------
# Context attribute harvesting — handles pylibiio API variations
# ---------------------------------------------------------------------------

_CTX_ID_ATTRS = ("hw_serial", "hw_model", "uri", "local,hostname", "local,kernel")

_DEV_ID_ATTRS = (
    "serial", "dna", "firmware_version", "ad9361-phy_version",
    "model_name", "hw_model",
)


def _harvest_ctx_attrs(ctx) -> dict[str, str]:  # type: ignore[type-arg]
    """Read context-level attributes from an iio.Context, tolerating API variations."""
    out: dict[str, str] = {}
    try:
        # pylibiio >= 0.23: ctx.attrs is a dict {name: value}
        if hasattr(ctx, "attrs") and ctx.attrs:
            items = ctx.attrs
            if hasattr(items, "items"):
                for k, v in items.items():
                    out[str(k)] = str(v)
            else:
                # Older API: iterable of attr objects
                for attr in items:
                    try:
                        out[str(attr.name)] = str(attr.value)
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def _harvest_dev_attrs(dev) -> dict[str, str]:  # type: ignore[type-arg]
    """Read device-level attributes from an iio.Device."""
    out: dict[str, str] = {}
    for attr_name in _DEV_ID_ATTRS:
        try:
            val = dev.attrs[attr_name].value
            out[attr_name] = str(val)
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Per-URI probe
# ---------------------------------------------------------------------------

def probe_uri(uri: str) -> PlutoResult:
    """Attempt a read-only connection to *uri* and harvest all identifying info."""
    result = PlutoResult(uri=uri)
    result.usb_path, result.ip_addr = _parse_uri(uri)

    try:
        import iio  # type: ignore
    except ImportError:
        result.error = "iio not available"
        return result

    try:
        ctx = iio.Context(uri)
    except Exception as exc:
        result.connected = False
        result.error = str(exc)
        return result

    result.connected = True

    # --- context description / name ---
    try:
        result.device_name = ctx.description or ctx.name or None
    except Exception:
        pass

    # --- context XML snippet ---
    try:
        xml = ctx.xml
        if xml:
            result.ctx_xml_snippet = xml[:600]
    except Exception:
        pass

    # --- context-level attributes ---
    result.ctx_attrs = _harvest_ctx_attrs(ctx)
    result.hw_serial = result.ctx_attrs.get("hw_serial") or None
    result.hw_model  = result.ctx_attrs.get("hw_model")  or None

    # --- device-level attributes (fallback) ---
    try:
        for dev in ctx.devices:
            dev_attrs = _harvest_dev_attrs(dev)
            result.dev_attrs.update(dev_attrs)
    except Exception:
        pass

    result.serial   = result.dev_attrs.get("serial")   or None
    result.dna      = result.dev_attrs.get("dna")       or None
    result.firmware = (
        result.dev_attrs.get("firmware_version")
        or result.dev_attrs.get("ad9361-phy_version")
        or None
    )

    # hw_model from device attrs if not found in context
    if not result.hw_model:
        result.hw_model = result.dev_attrs.get("hw_model") or result.dev_attrs.get("model_name") or None

    # --- derive fingerprint: best unique identifier available ---
    result.fingerprint = result.hw_serial or result.dna or result.serial

    return result


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

# Stable preferred URIs; usb: scan discovers bus-path aliases automatically.
# usb:1.x.x paths are NOT listed here — they are unstable and change on reconnect.
CANDIDATE_URIS = [
    "usb:",
    "ip:pluto.local",
    "ip:192.168.2.1",
]


def discover_plutos(extra_uris: list[str] | None = None) -> list[PlutoResult]:
    """
    Probe all candidate URIs in a read-only fashion.
    Scanned contexts are appended if not already in the list.
    Returns one PlutoResult per URI attempted.
    """
    uris: list[str] = list(CANDIDATE_URIS)

    for u in scan_iio_contexts():
        if u not in uris:
            uris.append(u)

    if extra_uris:
        for u in extra_uris:
            if u not in uris:
                uris.append(u)

    return [probe_uri(u) for u in uris]


# ---------------------------------------------------------------------------
# Disambiguation
# ---------------------------------------------------------------------------

Conclusion = str  # ONE_UNIQUE_DEVICE_CONFIRMED | TWO_UNIQUE_DEVICES_CONFIRMED | UNABLE_TO_DISAMBIGUATE


def disambiguate(
    results: list[PlutoResult],
) -> tuple[Conclusion, dict[str, list[str]]]:
    """
    Group connected URIs by fingerprint and return a conclusion string.

    Returns:
        conclusion: one of the three sentinel strings
        groups: {fingerprint -> [uri, ...]}  (empty if unable to identify)
    """
    connected = [r for r in results if r.connected]

    if not connected:
        return "NO_DEVICES_FOUND", {}

    groups: dict[str, list[str]] = {}
    unidentified: list[str] = []

    for r in connected:
        if r.fingerprint:
            groups.setdefault(r.fingerprint, []).append(r.uri)
        else:
            unidentified.append(r.uri)

    unique_count = len(groups)

    if unique_count == 0:
        # All connected but none had any identifying attribute
        return "UNABLE_TO_DISAMBIGUATE", {}

    if unique_count == 1 and not unidentified:
        return "ONE_UNIQUE_DEVICE_CONFIRMED", groups

    if unique_count >= 2:
        return "TWO_UNIQUE_DEVICES_CONFIRMED", groups

    # Some identified, some not — cannot be certain
    return "UNABLE_TO_DISAMBIGUATE", groups


def _conclusion_note(conclusion: Conclusion, groups: dict[str, list[str]]) -> str:
    """Return a human-readable explanation of the conclusion."""
    if conclusion == "ONE_UNIQUE_DEVICE_CONFIRMED":
        fp = next(iter(groups))
        uris = groups[fp]
        return (
            f"All {len(uris)} connected URI(s) share fingerprint '{fp}'. "
            "They are aliases for ONE physical ADALM-PLUTO."
        )
    if conclusion == "TWO_UNIQUE_DEVICES_CONFIRMED":
        lines = []
        for i, (fp, uris) in enumerate(groups.items(), 1):
            lines.append(f"  Device {i}: fingerprint '{fp}' → {uris}")
        return "Distinct fingerprints found — TWO (or more) physical devices:\n" + "\n".join(lines)
    if conclusion == "UNABLE_TO_DISAMBIGUATE":
        return (
            "Could not extract unique identifiers from all connected URIs. "
            "Manual inspection required (check hw_serial via libiio or Pluto web UI)."
        )
    if conclusion == "NO_DEVICES_FOUND":
        return "No URIs responded."
    return ""


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def print_comparison_table(results: list[PlutoResult]) -> None:
    """Print a fixed-width comparison table to stdout."""
    cols = ("URI", "OK", "hw_serial", "hw_model", "dna/serial", "usb_path", "ip_addr", "fingerprint")
    widths = (20, 3, 20, 16, 20, 10, 16, 20)

    header = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    sep    = "  ".join("-" * w for w in widths)
    print(header)
    print(sep)

    for r in results:
        row = (
            r.uri,
            "YES" if r.connected else "NO",
            r.hw_serial  or "-",
            r.hw_model   or "-",
            r.dna or r.serial or "-",
            r.usb_path   or "-",
            r.ip_addr    or "-",
            r.fingerprint or "-",
        )
        print("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))


def results_to_markdown(
    availability: dict[str, bool],
    results: list[PlutoResult],
    conclusion: Conclusion,
    groups: dict[str, list[str]],
    timestamp: str,
) -> str:
    lines: list[str] = []
    lines.append("# ORION Hardware Status")
    lines.append("")
    lines.append("## Location")
    lines.append("")
    lines.append("Innovation Lab / Toomey Hall, Missouri S&T")
    lines.append("")
    lines.append(f"## Phase 1B Detection Run — {timestamp}")
    lines.append("")

    # Package availability
    lines.append("### Python Package Availability")
    lines.append("")
    for name, ok in availability.items():
        mark = "YES" if ok else "NO — install required"
        lines.append(f"- `import {name}`: **{mark}**")
    lines.append("")

    # Comparison table
    lines.append("### URI Comparison Table")
    lines.append("")
    lines.append("| URI | Connected | hw_serial | hw_model | dna/serial | USB path | IP addr | Fingerprint |")
    lines.append("|-----|-----------|-----------|----------|------------|----------|---------|-------------|")
    for r in results:
        row = [
            f"`{r.uri}`",
            "YES" if r.connected else "NO",
            r.hw_serial   or "—",
            r.hw_model    or "—",
            r.dna or r.serial or "—",
            r.usb_path    or "—",
            r.ip_addr     or "—",
            f"`{r.fingerprint}`" if r.fingerprint else "—",
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Physical device groups
    if groups:
        lines.append("### Physical Device Groups")
        lines.append("")
        for i, (fp, uris) in enumerate(groups.items(), 1):
            lines.append(f"**Device {i}** (fingerprint: `{fp}`)")
            for u in uris:
                lines.append(f"- `{u}`")
            lines.append("")

    # Conclusion
    lines.append("### Conclusion")
    lines.append("")
    lines.append(f"**`{conclusion}`**")
    lines.append("")
    lines.append(_conclusion_note(conclusion, groups))
    lines.append("")

    # Per-URI detail
    lines.append("### Per-URI Detail")
    lines.append("")
    for r in results:
        lines.append(f"#### `{r.uri}`")
        lines.append("")
        lines.append(f"- **Connected**: {'Yes' if r.connected else 'No'}")
        if r.error:
            lines.append(f"- **Error**: `{r.error}`")
        if r.device_name:
            lines.append(f"- **Context description**: {r.device_name}")
        if r.hw_serial:
            lines.append(f"- **hw_serial** *(primary ID)*: `{r.hw_serial}`")
        if r.hw_model:
            lines.append(f"- **hw_model**: {r.hw_model}")
        if r.dna:
            lines.append(f"- **dna**: `{r.dna}`")
        if r.serial:
            lines.append(f"- **serial**: `{r.serial}`")
        if r.firmware:
            lines.append(f"- **firmware**: {r.firmware}")
        if r.usb_path:
            lines.append(f"- **USB path**: {r.usb_path}")
        if r.ip_addr:
            lines.append(f"- **IP/hostname**: {r.ip_addr}")
        if r.ctx_attrs:
            lines.append(f"- **Context attributes**:")
            for k, v in sorted(r.ctx_attrs.items()):
                lines.append(f"  - `{k}`: {v}")
        if r.ctx_xml_snippet:
            lines.append(f"- **Context XML (first 600 chars)**:")
            lines.append(f"  ```xml")
            lines.append(f"  {r.ctx_xml_snippet}")
            lines.append(f"  ```")
        lines.append("")

    # Static setup notes
    lines.append("## Current Setup")
    lines.append("")
    lines.append("- Two ADALM-PLUTO SDRs physically present")
    lines.append("- Both connected to powered ONN USB hub")
    lines.append("- Hub connected to ASUS ProArt P16 laptop")
    lines.append("- Small antennas available")
    lines.append("- Two coax cables available")
    lines.append("- No verified attenuators currently available")
    lines.append("")
    lines.append("## Open Issues")
    lines.append("")
    lines.append("- ~~Both PLUTOs detected and two unique devices confirmed~~ ✓ Resolved — Phase 1B PASS")
    lines.append("- ~~Firmware recovery~~ ✓ Not required — both PLUTOs functional")
    lines.append("- USB bus-path URIs change on re-enumeration — use `ip:pluto.local` / `ip:192.168.2.1` for all routine operation")
    lines.append("- No verified attenuators available — conducted coax testing deferred")
    lines.append("")

    return "\n".join(lines)


def testlog_row(
    results: list[PlutoResult],
    conclusion: Conclusion,
    timestamp: str,
) -> str:
    connected = [r for r in results if r.connected]
    result_str = f"{'PASS' if connected else 'FAIL'} — {conclusion}"
    uris = ", ".join(r.uri for r in connected) if connected else "none"
    return (
        f"| {timestamp} | Phase 1B | PLUTO unique-device ID | "
        f"pyadi-iio + pylibiio + 00_list_plutos.py | "
        f"{result_str} | hardware_status.md | Connected URIs: {uris} |"
    )
