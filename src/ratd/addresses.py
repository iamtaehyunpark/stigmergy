"""A1 — Address grammar. One formal syntax, enforced identically in
validator, runtime, and prompts; never silently relaxed (the PATH_RE
lesson: .tar.gz drift correlated with worker refusals, E1 d01_r3).

BNF:
  address   ::= namespace "/" key
  namespace ::= base ("." index)*
  base      ::= "root" | "_system" | "_doctor"     (underscore bases are
                                                    runtime/system-only)
  index     ::= [1-9][0-9]*
  key       ::= [a-z][a-z0-9_]*                    (length <= 64)

Numeric families (A5 incremental assembly): a key matching <stem>_<n>
belongs to the family <stem>. A family is declarable as one pin-set with
the literal form  <stem>_{1..n}  (n known at declaration, capped).
"""
from __future__ import annotations

import re

KEY_MAX = 64
FAMILY_MAX = 40  # declaration cap: <stem>_{1..n} with n <= 40

NAMESPACE_RE = re.compile(r"^(root|_system|_doctor)(\.[1-9][0-9]*)*$")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
FAMILY_DECL_RE = re.compile(r"^([a-z][a-z0-9_]*)_\{1\.\.([1-9][0-9]*)\}$")
FAMILY_KEY_RE = re.compile(r"^([a-z][a-z0-9_]*)_([1-9][0-9]*)$")
# For scanning free text (capsules) for address mentions:
ADDRESS_SCAN_RE = re.compile(r"(?:root|_system|_doctor)(?:\.\d+)*/[a-z][a-z0-9_]*")


def split_address(address: str) -> tuple[str, str] | None:
    if not isinstance(address, str) or address.count("/") != 1:
        return None
    namespace, key = address.split("/")
    return namespace, key


def address_error(address: str, *, system: bool = False) -> str | None:
    """None if the address conforms; otherwise a repair-feedback note.

    system=True permits the reserved underscore bases (runtime/doctor).
    Family declarations (stem_{1..n}) are valid as *declared* paths.
    """
    parts = split_address(address)
    if parts is None:
        return f"address {address!r} must be exactly namespace/key"
    namespace, key = parts
    if not NAMESPACE_RE.match(namespace):
        return f"namespace {namespace!r} must be root(.index)* (indexes start at 1, no leading zeros)"
    if namespace.split(".")[0].startswith("_") and not system:
        return f"namespace {namespace!r} is reserved (underscore namespaces are runtime-writable only)"
    fam = FAMILY_DECL_RE.match(key)
    if fam:
        if len(fam.group(1)) + 1 + len(str(fam.group(2))) > KEY_MAX:
            return f"family key {key!r} expands past the {KEY_MAX}-char key cap"
        if int(fam.group(2)) > FAMILY_MAX:
            return f"family key {key!r} declares more than {FAMILY_MAX} members"
        return None
    if not KEY_RE.match(key):
        return f"key {key!r} must be [a-z][a-z0-9_]* — no dots, no extensions, no uppercase"
    if len(key) > KEY_MAX:
        return f"key {key!r} exceeds {KEY_MAX} chars"
    return None


def valid_address(address: str, *, system: bool = False) -> bool:
    return address_error(address, system=system) is None


def expand_family(address: str) -> list[str]:
    """'ns/stem_{1..3}' -> ['ns/stem_1', 'ns/stem_2', 'ns/stem_3'];
    a plain address expands to itself."""
    parts = split_address(address)
    if parts is None:
        return [address]
    namespace, key = parts
    fam = FAMILY_DECL_RE.match(key)
    if not fam:
        return [address]
    stem, n = fam.group(1), int(fam.group(2))
    return [f"{namespace}/{stem}_{i}" for i in range(1, n + 1)]


def is_family_declaration(address: str) -> bool:
    parts = split_address(address)
    return parts is not None and FAMILY_DECL_RE.match(parts[1]) is not None


def family_stem(key: str) -> str | None:
    match = FAMILY_KEY_RE.match(key)
    return match.group(1) if match else None


def is_system_namespace(namespace_or_address: str) -> bool:
    return namespace_or_address.split("/")[0].split(".")[0].startswith("_")


def ancestor_namespaces(agent_id: str) -> list[str]:
    parts = agent_id.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]


def scan_addresses(text: str) -> set[str]:
    return set(ADDRESS_SCAN_RE.findall(text or ""))
