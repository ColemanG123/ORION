#!/usr/bin/env python3
"""
src/orion/pluto_identity.py — stable ADALM-PLUTO identity resolver for ORION.

Purpose
-------
Resolve ORION radio identities by serial suffix, not unstable USB paths.

Canonical identities:
  e9e = receive/default observer
  149 = transmit/secondary

Why
---
USB paths such as usb:1.6.5 and usb:1.7.5 can change between sessions.
Serial suffixes are the stable device identities.
"""

from __future__ import annotations

from dataclasses import dataclass


E9E_SERIAL_SUFFIX = "e9e"
E149_SERIAL_SUFFIX = "149"

CANONICAL_SERIAL_SUFFIXES = {
    "e9e": E9E_SERIAL_SUFFIX,
    "rx": E9E_SERIAL_SUFFIX,
    "observer": E9E_SERIAL_SUFFIX,
    "149": E149_SERIAL_SUFFIX,
    "tx": E149_SERIAL_SUFFIX,
    "secondary": E149_SERIAL_SUFFIX,
}

PREFERRED_STATIC_URIS = [
    "ip:192.168.3.1",
    "ip:pluto.local",
    "ip:192.168.2.1",
]


@dataclass(frozen=True)
class PlutoMatch:
    identity: str
    serial_suffix: str
    uri: str
    full_serial: str
    hw_model: str


def canonical_suffix(identity_or_suffix: str) -> str:
    key = identity_or_suffix.strip().lower()
    if key in CANONICAL_SERIAL_SUFFIXES:
        return CANONICAL_SERIAL_SUFFIXES[key]

    if len(key) >= 3:
        return key[-3:]

    raise ValueError(f"Cannot resolve Pluto identity/suffix: {identity_or_suffix!r}")


def discover_iio_uris() -> list[str]:
    """
    Return candidate IIO URIs from stable guesses plus iio.scan_contexts().
    """
    import iio

    uris: list[str] = []

    def add(uri: str) -> None:
        if uri and uri not in uris:
            uris.append(uri)

    for uri in PREFERRED_STATIC_URIS:
        add(uri)

    try:
        scanned = iio.scan_contexts()
        for uri in scanned:
            add(uri)
    except Exception:
        pass

    return uris


def read_context_identity(uri: str) -> tuple[str, str]:
    """
    Return (hw_serial, hw_model) for a candidate URI.
    """
    import iio

    ctx = iio.Context(uri)
    serial = ctx.attrs.get("hw_serial", "")
    model = ctx.attrs.get("hw_model", "")
    return serial, model


def resolve_pluto_uri(identity_or_suffix: str, verbose: bool = True) -> PlutoMatch:
    """
    Resolve e9e/149/rx/tx/serial-suffix into the currently valid IIO URI.

    Example:
      resolve_pluto_uri("e9e").uri
      resolve_pluto_uri("149").uri
      resolve_pluto_uri("tx").uri
    """
    suffix = canonical_suffix(identity_or_suffix)
    candidates = discover_iio_uris()

    seen: list[tuple[str, str, str, str]] = []

    if verbose:
        print(f"[pluto_identity] resolving '{identity_or_suffix}' as suffix ...{suffix}")
        print(f"[pluto_identity] probing {len(candidates)} URI(s): {candidates}")

    for uri in candidates:
        try:
            serial, model = read_context_identity(uri)
            seen.append((uri, serial, serial[-3:] if serial else "", model))

            if serial.lower().endswith(suffix.lower()):
                if verbose:
                    print(f"[pluto_identity] resolved ...{suffix} -> {uri}")
                    print(f"[pluto_identity] serial={serial}")
                return PlutoMatch(
                    identity=identity_or_suffix,
                    serial_suffix=suffix,
                    uri=uri,
                    full_serial=serial,
                    hw_model=model,
                )
        except Exception as exc:
            seen.append((uri, f"ERROR: {exc}", "", ""))

    detail = "\n".join(
        f"  {uri:<18} suffix={suf or '???':<3} serial={serial} model={model}"
        for uri, serial, suf, model in seen
    )

    raise RuntimeError(
        f"Could not resolve Pluto identity '{identity_or_suffix}' "
        f"(suffix ...{suffix}).\nCandidates seen:\n{detail}"
    )


def print_identity_table() -> None:
    """
    Diagnostic table for current session.
    """
    print("URI -> hw_serial")
    print("-" * 72)

    for uri in discover_iio_uris():
        try:
            serial, model = read_context_identity(uri)
            suffix = serial[-3:] if serial else "???"
            print(f"{uri:<18} suffix={suffix:<3} serial={serial} model={model}")
        except Exception as exc:
            print(f"{uri:<18} ERROR: {exc}")


if __name__ == "__main__":
    print_identity_table()
    print()
    print("Resolved:")
    for ident in ("e9e", "149"):
        match = resolve_pluto_uri(ident, verbose=False)
        print(f"  {ident:<3} -> {match.uri:<18} serial={match.full_serial}")