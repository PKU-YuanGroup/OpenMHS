"""Shared helpers of the reference protocol fixtures (internal, not public API).

The reference endpoints are *protocol fixtures*, not driver templates: each is
a deterministic Python model, a manifest that validates against
``MHS/schema/device.schema.json`` and a hand-written bridge, used to exercise
the wire protocol, the runtime safety rules and the conformance suite.  A
per-repository driver is a :class:`mhs.driver.Driver` package (see
``MHS/sdk/docs/driver-authoring.md`` and ``MHS/sdk/examples/thermostat``),
never a copy of these modules.  This module holds the small pieces that the
four endpoints share.

Identity comes from :mod:`mhs._ids` (``ADAPTER_ID_PREFIX``, ``PROJECT_NAME``,
``WIRE_VERSION``).  A conformance claim is published only when the report that
backs it can be read: from the directories in ``MHS_CONFORMANCE_REPORTS``
(``os.pathsep``-separated; report files by name) or, in a source checkout,
from ``MHS/conformance/reports`` and ``MHS/sdk/docs/reports``.  An installed
package without either publishes no claim rather than a placeholder.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from mhs import _ids
from mhs.bridge.base import Bridge

MHS_VERSION = _ids.WIRE_VERSION

#: Fixed instance ids keep the reference simulators byte-for-byte reproducible.
#: A real endpoint generates a fresh ULID per physical unit at first boot; a
#: reference simulator deliberately does not, so conformance replays are stable.
INSTANCE_IDS = {
    "conveyor": "01J8ZQ3V6Y7M2N4P6R8S0T2V4W",
    "pipette": "01J8ZQ3V6Y7M2N4P6R8S0T2V50",
    "reader": "01J8ZQ3V6Y7M2N4P6R8S0T2V51",
    "mover": "01J8ZQ3V6Y7M2N4P6R8S0T2V52",
    "arm": "01J8ZQ3V6Y7M2N4P6R8S0T2V53",
    "replay": "01J8ZQ3V6Y7M2N4P6R8S0T2V54",
}

ZERO_DIGEST = "sha256:" + "0" * 64

#: Prefix of the reference fixtures' ``provenance.adapter_id``.
ADAPTER_ID_PREFIX = _ids.ADAPTER_ID_PREFIX + "reference."
#: The ``vendor`` of every reference fixture (no URL: the project has no host yet).
VENDOR = {"name": f"{_ids.PROJECT_NAME} reference fixture"}

#: Environment variable naming the directories that hold the published reports.
REPORTS_ENV = "MHS_CONFORMANCE_REPORTS"

#: Checkout-relative paths of the published conformance reports, by endpoint
#: name, best first.  Published reports back a claim with a real digest instead
#: of a placeholder (MHS-001 CON-035/039, MHS-010 GOV-083).
PUBLISHED_REPORTS: dict[str, tuple[str, ...]] = {
    "conveyor": ("MHS/conformance/reports/conveyor-cl4.json",),
    "lab": ("MHS/conformance/reports/lab-cl4.json", "MHS/conformance/reports/lab-cl2.json"),
    "arm": ("MHS/conformance/reports/arm-cl4.json", "MHS/conformance/reports/arm-cl3.json"),
    # A seeded-noise arm is a different fidelity instance and claims only the
    # report that was produced against that exact configuration (FID-004).
    "arm-seeded": ("MHS/sdk/docs/reports/conformance-arm-2dof-seeded.json",),
    "replay": ("MHS/sdk/docs/reports/conformance-replay-recorded.json",),
}


def checkout_root() -> Path | None:
    """The repository root when this module runs from a source checkout, else None.

    The layout is checked by name (``<root>/MHS/sdk/src/mhs/reference``), so an
    installed package never resolves to an unrelated directory.
    """
    here = Path(__file__).resolve().parent
    expected = ("reference", "mhs", "src", "sdk", "MHS")
    chain = [here, *here.parents]
    if len(chain) <= len(expected) or tuple(path.name for path in chain[: len(expected)]) != expected:
        return None
    return chain[len(expected)]


def report_candidates(name: str) -> list[Path]:
    """The files that may hold the published report of endpoint ``name``, in lookup order.

    ``MHS_CONFORMANCE_REPORTS`` directories come first (each report is looked
    up by file name), then the source checkout's paths.
    """
    relatives = PUBLISHED_REPORTS.get(name, ())
    out: list[Path] = []
    for directory in (os.environ.get(REPORTS_ENV) or "").split(os.pathsep):
        if directory.strip():
            out.extend(Path(directory).expanduser() / Path(relative).name for relative in relatives)
    root = checkout_root()
    if root is not None:
        out.extend(root / relative for relative in relatives)
    return out


def published_conformance(name: str, fallback_level: str | None = None) -> dict[str, Any] | None:
    """Return the conformance claim backed by a published report, or None.

    A claim without a recomputable digest must not be presented (GOV-083), so
    when no report is available the endpoint simply omits ``conformance``
    rather than advertising a placeholder.  ``fallback_level`` is used only
    when a readable report lacks ``level_achieved``.
    """
    for path in report_candidates(name):
        if not path.is_file():
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(report, Mapping):
            continue
        digest = report.get("report_digest")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            continue
        if set(digest.split(":", 1)[1].lower()) <= {"0"}:
            continue
        suite_version = report.get("suite_version")
        if not isinstance(suite_version, str) or not suite_version:
            continue
        environment = report.get("environment") or {}
        issuer = report.get("issuer") or {}
        claim: dict[str, Any] = {
            "profile": str(report.get("profile") or "MHS-Sim"),
            "level": str(report.get("level_achieved") or fallback_level or "CL0"),
            "suite_version": suite_version,
            "report_digest": digest,
            "issuer_kind": str(issuer.get("kind") or "self"),
        }
        if isinstance(environment, Mapping) and environment.get("date"):
            claim["issued_at"] = str(environment["date"])
        return claim
    return None


def catalogue_verb(capability_id: str, declared: Any = None) -> str:
    """The verb a reference binding serves: the catalogue class's, else the declared one, else ``invoke``.

    Extensions (``x-cap.*``) keep the verb they declare; the runtime never
    trusts an extension's ``read`` for the latch or arming anyway.
    """
    from mhs import catalog as _catalog

    if not _catalog.is_extension(capability_id):
        try:
            entry = _catalog.get(capability_id)
        except Exception:  # noqa: BLE001 - no catalogue: fall back to the declared verb
            entry = None
        verb = entry.get("verb") if isinstance(entry, Mapping) else None
        if verb in ("read", "write", "invoke"):
            return str(verb)
    return str(declared) if declared in ("read", "write", "invoke") else "invoke"


@dataclasses.dataclass
class EndpointSpec:
    """An endpoint ready to be handed to ``mhs.server.MHSServer``."""

    name: str
    endpoint_id: str
    profile: str
    devices: list[dict[str, Any]]
    bridges: dict[str, Bridge]
    features: list[str] = dataclasses.field(default_factory=list)
    notes: str = ""
    conformance_level: str = "CL4"

    def bridge_for(self, device_id: str) -> Bridge:
        return self.bridges[device_id]

    def close(self) -> None:
        for bridge in self.bridges.values():
            try:
                bridge.close()
            except Exception:  # noqa: BLE001 - teardown must not mask the reason
                pass


def capability(
    capability_id: str,
    resource: str,
    title: str,
    native: str,
    input_schema: Mapping[str, Any] | None,
    output_schema: Mapping[str, Any] | None,
    *,
    summary: str,
    tags: Iterable[str],
    units: Mapping[str, str] | None = None,
    effects: Iterable[str] = (),
    hazards: Iterable[str] = (),
    preconditions: Iterable[str] = (),
    postconditions: Iterable[str] = (),
    constraints: Mapping[str, Any] | None = None,
    determinism: str = "exact",
    exclusive: bool = True,
    requires_permit: bool = False,
    limits: Mapping[str, Any] | None = None,
    notes: str | None = None,
    verb: str | None = None,
) -> dict[str, Any]:
    """Build one manifest capability entry (closed schema: no extra keys).

    ``verb`` defaults to the catalogue class's verb (:func:`catalogue_verb`).
    """

    entry: dict[str, Any] = {
        "capability_id": capability_id,
        "resource": resource,
        "title": title,
        "verb": catalogue_verb(capability_id, verb),
        "native": native,
        "input_schema": copy.deepcopy(dict(input_schema or {"type": "object", "properties": {}})),
        "output_schema": copy.deepcopy(dict(output_schema or {"type": "object"})),
        "semantics": {
            "summary": summary,
            "tags": list(tags),
            "units": dict(units or {}),
            "effects": list(effects),
            "hazards": list(hazards),
            "preconditions": list(preconditions),
            "postconditions": list(postconditions),
            "determinism": determinism,
            "notes": notes or "",
        },
        "constraints": {
            "concurrency": "exclusive" if exclusive else "shared",
            "cancellable": bool((constraints or {}).get("cancellable", False)),
            "max_duration_ms": int((constraints or {}).get("max_duration_ms", 5000)),
        },
        "determinism": determinism,
        "exclusive": exclusive,
    }
    if requires_permit:
        entry["requires_permit"] = True
    if limits:
        entry["limits"] = copy.deepcopy(dict(limits))
    return entry


def resource(
    resource_id: str,
    kind: str,
    title: str,
    state_schema: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    hash_exclusions: Iterable[str] = (),
    sampling: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "resource_id": resource_id,
        "kind": kind,
        "title": title,
        "revision": 0,
        "sampling": dict(sampling or {"mode": "on_change"}),
        "hash_exclusions": list(hash_exclusions),
        "state_schema": copy.deepcopy(dict(state_schema)),
        "state": copy.deepcopy(dict(state)),
    }


def device(
    *,
    endpoint_id: str,
    slug: str,
    display_name: str,
    instance_id: str,
    mode: str,
    model: str,
    resources: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    safety: Mapping[str, Any],
    fidelity: Mapping[str, Any] | None,
    profile: Mapping[str, Any] | None = None,
    models: Iterable[str] = (),
    tags: Iterable[str] = (),
    operating_notes: Iterable[str] = (),
    conformance_level: str = "CL4",
    endpoint_name: str | None = None,
    provenance_sources: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a device manifest matching ``MHS/schema/device.schema.json``."""

    manifest: dict[str, Any] = {
        "mhs_version": MHS_VERSION,
        "device_id": f"{endpoint_id}/{slug}",
        "instance_id": instance_id,
        "display_name": display_name,
        "vendor": copy.deepcopy(VENDOR),
        "model": model,
        "mode": mode,
        "models": list(models),
        "resources": resources,
        "capabilities": capabilities,
        "safety": copy.deepcopy(dict(safety)),
        "provenance": {
            "adapter_id": ADAPTER_ID_PREFIX + slug.rsplit("/", 1)[-1],
            "generated_by": "mhs.reference (protocol fixture, not a driver template)",
            "evidence": list(provenance_sources),
        },
    }
    claim = published_conformance(endpoint_name, conformance_level) if endpoint_name else None
    if claim is not None:
        manifest["conformance"] = claim
    if profile:
        manifest["profile"] = copy.deepcopy(dict(profile))
    if fidelity is not None:
        manifest["fidelity"] = copy.deepcopy(dict(fidelity))
    return manifest


def exact_fidelity(engine: str, *, timestep_ms: float = 1, gaps: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "engine": engine,
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "Deterministic Python model; integer/fixed-point normative state, no wall-clock pacing.",
        },
        "timestep_ms": timestep_ms,
        "realtime_factor": 0,
        "reset": "full",
        "snapshot_restore": True,
        "gaps": list(gaps),
    }
