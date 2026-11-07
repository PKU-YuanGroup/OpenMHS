"""Build the runtime objects, the manifest and the reference file of a Driver.

* :func:`build_manifest` -- the device manifest of a driver class or
  instance, for its declared view (``backend=None``: a hardware driver as
  hardware) or for a backend (``"fake"`` or ``"sim"``: mode ``simulated``, the
  fake fidelity contract, ``models: [<hardware id>]``, a device id of its own;
  any name outside :data:`BACKENDS` raises ``ValueError``).
* :func:`build_device` -- the :class:`mhs.server.Device` serving one driver
  instance, resolved in strict mode (a finding raises
  :class:`~mhs.driver.spec.DriverDefinitionError`).
* :func:`build_server` -- a strict :class:`mhs.server.MHSServer` for one or
  more driver instances.
* :func:`build_reference` -- ``reference.json`` content, rendered by
  :func:`mhs.reference_file.render` (write it with
  :func:`mhs.reference_file.dump` and :func:`mhs.reference_file.render_markdown`).

Mapping (plan 3.8): the parameters become one resource whose
``state_schema`` marks read-only parameters ``readOnly`` and carries their
``x-mhs-unit``; writable parameters bind ``cap.device.configure.v1`` (served by
``mhs.resource.write``) with their limits keyed by parameter path; reads are
served by ``mhs.resource.read``; every action is one binding named
``x-mhs-name`` after its method, with the class schema (narrowed to the
method's parameters) or an inline extension schema and its
``x-mhs-schema-digest``; the risk class is the highest of the declared risk,
the per-action/per-parameter risks and the class floors; ``safety.estop.native``
names the ``@estop`` method (``null``: a software-only latch).  A composed
driver (``extra_resources``) publishes its further typed resources after the
main one, each with an empty read-only state, and every binding on the
resource it declares (``Action(resource=...)``); the device, its e-stop latch
and its bridge stay one.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .. import canonical
from .. import reference_file as _reference_file
from ..protocol import MHS_VERSION
from ..server import Capability, Device, MHSServer, Resource, SafetyEnvelope
from .._server.strict import MHSStrictError
from . import model as _model
from .model import BACKENDS, FAKE_BACKENDS
from .spec import DriverDefinitionError

__all__ = [
    "BACKENDS",
    "DEFAULT_ENDPOINT_ID",
    "DriverCapability",
    "DriverDevice",
    "FAKE_FIDELITY",
    "build_device",
    "build_manifest",
    "build_reference",
    "build_server",
    "check_backend",
    "close_server",
    "device_from_manifest",
    "hardware_device_id",
    "remap_overlay",
    "served_device_id",
    "served_mode",
]

#: Host part of the device id of a driver that declares a short ``device_id``.
DEFAULT_HOST = "mhs://localhost"
#: Endpoint id of a server built by :func:`build_server` / :func:`mhs.adapter.load`.
DEFAULT_ENDPOINT_ID = "mhs://localhost"
#: ``provenance.generated_by`` of every manifest built here.
GENERATED_BY = "mhs.driver"

#: Fidelity contract of a hardware driver served on a fake backend (the transport is replaced).
FAKE_FIDELITY: dict[str, Any] = {
    "engine": "fake",
    "fidelity_level": "F0",
    "determinism": {"kind": "seeded", "seed_control": "none"},
    "timestep_ms": 0,
    "realtime_factor": 0,
    "reset": "full",
    "snapshot_restore": False,
    "gaps": ["transport replaced by fake backend"],
}


# ---------------------------------------------------------------------------
# runtime objects with the 0.9 manifest members the dataclasses do not model
# ---------------------------------------------------------------------------


@dataclass
class DriverCapability(Capability):
    """A :class:`mhs.server.Capability` that also publishes extension members (``x-mhs-name``, digests)."""

    extra: dict[str, Any] = field(default_factory=dict)

    def manifest(self, *, concurrency: str | None = None) -> dict[str, Any]:
        out = super().manifest(concurrency=concurrency)
        for key, value in self.extra.items():
            out.setdefault(key, copy.deepcopy(value))
        return out


@dataclass
class DriverDevice(Device):
    """A :class:`mhs.server.Device` that also publishes ``watchdog_ms`` (a device-side watchdog the
    driver cites with a Fact; the runtime does not implement it)."""

    watchdog_ms: int | None = None

    def manifest(self, **options: Any) -> dict[str, Any]:
        out = super().manifest(**options)
        if self.watchdog_ms:
            out["watchdog_ms"] = int(self.watchdog_ms)
        return out


# ---------------------------------------------------------------------------
# identity and views
# ---------------------------------------------------------------------------


def hardware_device_id(model: _model.DriverModel) -> str:
    """The device id of the driver's declared device (``mhs://localhost/<device_id>`` for a short name)."""
    declared = model.device_id
    return declared if declared.startswith("mhs://") else f"{DEFAULT_HOST}/{declared}"


def check_backend(backend: Any) -> None:
    """Raise ``ValueError`` unless ``backend`` is ``None`` (the declared view) or one of :data:`BACKENDS`."""
    if backend is not None and backend not in BACKENDS:
        raise ValueError(f"backend {backend!r} is not one of {list(BACKENDS)} (only 'hardware' drives the device; "
                         "'fake' and 'sim' are served as mode simulated)")


def is_fake_view(model: _model.DriverModel, backend: str | None) -> bool:
    """True when a hardware driver is served on its ``fake`` or ``sim`` backend (any other name raises)."""
    check_backend(backend)
    return model.mode == "hardware" and backend in FAKE_BACKENDS


def served_device_id(model: _model.DriverModel, backend: str | None) -> str:
    """The id served for ``backend``: the hardware id, or ``<hardware id>/<backend>`` for a fake view."""
    base = hardware_device_id(model)
    return f"{base}/{backend}" if is_fake_view(model, backend) else base


def served_mode(model: _model.DriverModel, backend: str | None) -> str:
    """``hardware`` only for a hardware driver on its hardware backend; every other view is ``simulated``."""
    check_backend(backend)
    return "hardware" if model.mode == "hardware" and backend in (None, "hardware") else "simulated"


def fake_fidelity(backend: str) -> dict[str, Any]:
    out = copy.deepcopy(FAKE_FIDELITY)
    if backend != "fake":
        out["engine"] = f"{backend} backend"
        out["gaps"] = [f"transport replaced by the {backend} backend"]
    return out


def _model_of(driver: Any) -> tuple[_model.DriverModel, Any]:
    """``(model, instance or None)`` of a Driver class or instance."""
    from .base import Driver

    if isinstance(driver, Driver):
        return driver._model, driver
    if isinstance(driver, type) and issubclass(driver, Driver):
        if getattr(driver, "_needs_instance", False):
            raise DriverDefinitionError(f"{driver.__qualname__} builds its contract from its backend; pass an instance "
                                        "(e.g. Cls(backend='fake'))", driver=driver.__qualname__)
        return driver.driver_model(), None
    raise TypeError(f"expected a Driver subclass or instance, got {driver!r}")


def _fidelity(model: _model.DriverModel, instance: Any, backend: str | None) -> dict[str, Any] | None:
    if instance is not None:
        hook = getattr(instance, "fidelity_for", None)
        if callable(hook):
            return hook(backend)
    if model.mode == "simulated":
        return copy.deepcopy(model.fidelity) if model.fidelity else None
    if is_fake_view(model, backend):
        return fake_fidelity(str(backend))
    return None


def _display_name(model: _model.DriverModel, fake: bool, backend: str | None) -> str:
    name = model.display_name or " ".join(item for item in (model.vendor, model.model) if item) or model.driver
    if fake:
        name = f"{name} ({backend} backend)"
    return name[:200]


def build_manifest(driver: Any, *, backend: str | None = None, upstream: Mapping[str, str] | None = None,
                   instance_id: str | None = None) -> dict[str, Any]:
    """The device manifest of ``driver`` (a class or an instance) for ``backend``.

    ``backend=None`` is the declared view (an instance defaults to its own
    backend).  ``upstream`` (``{repo, commit}``, e.g. from ``driver.lock.json``)
    becomes ``provenance.source_repo``/``source_commit``.
    """
    model, instance = _model_of(driver)
    if backend is None and instance is not None and not isinstance(driver, type):
        backend = instance.backend
    if instance is not None:
        projection_check = getattr(instance, "_validate_backend_projection", None)
        if callable(projection_check):
            projection_check(backend)
    fake = is_fake_view(model, backend)
    out: dict[str, Any] = {
        "mhs_version": MHS_VERSION,
        "device_id": served_device_id(model, backend),
        "instance_id": instance_id or canonical.ulid(),
        "display_name": _display_name(model, fake, backend),
        "mode": served_mode(model, backend),
        "resources": model.resources_manifest(),
        "capabilities": [binding.manifest(model.resource_of(binding)) for binding in model.bindings],
        "safety": model.safety_manifest(),
    }
    models = list(model.models)
    if fake:
        models = [hardware_device_id(model)] + [item for item in models if item != hardware_device_id(model)]
    if models:
        out["models"] = models
    if model.vendor:
        out["vendor"] = {"name": model.vendor}
    if model.model:
        out["model"] = model.model
    if model.tags:
        out["profile"] = {"tags": list(model.tags)}
    if model.operating_notes:
        out.setdefault("profile", {})["operating_notes"] = list(model.operating_notes)
    fidelity = _fidelity(model, instance, backend)
    if fidelity is not None:
        out["fidelity"] = fidelity
    provenance: dict[str, Any] = {"generated_by": GENERATED_BY}
    source = dict(upstream or model.upstream or {})
    if source.get("repo"):
        provenance["source_repo"] = str(source["repo"])
    if source.get("commit"):
        provenance["source_commit"] = str(source["commit"])
    out["provenance"] = provenance
    if model.watchdog_ms:
        out["watchdog_ms"] = model.watchdog_ms
    return out


# ---------------------------------------------------------------------------
# Device / server
# ---------------------------------------------------------------------------


def device_from_manifest(manifest: Mapping[str, Any], bridge: Any, *, strict: bool = True) -> DriverDevice:
    """A :class:`DriverDevice` for a device manifest (``device.schema.json``) served by ``bridge``.

    Strict resolution findings raise :class:`DriverDefinitionError` (its
    ``findings`` are the :class:`mhs._server.strict.Finding` objects).
    """
    resources = [Resource(item["resource_id"], item["kind"], title=item.get("title"),
                          state_schema=copy.deepcopy(item.get("state_schema")), state=copy.deepcopy(item.get("state")),
                          revision=int(item.get("revision", 0) or 0), sampling=copy.deepcopy(item.get("sampling")),
                          hash_exclusions=copy.deepcopy(item.get("hash_exclusions")))
                 for item in manifest["resources"]]
    capabilities = []
    for item in manifest["capabilities"]:
        extra = {key: copy.deepcopy(value) for key, value in item.items() if key.startswith("x-")}
        capabilities.append(DriverCapability(
            item["capability_id"], item["resource"], title=item.get("title"), verb=item.get("verb"),
            input_schema=copy.deepcopy(item.get("input_schema")), output_schema=copy.deepcopy(item.get("output_schema")),
            semantics=copy.deepcopy(item.get("semantics")), constraints=copy.deepcopy(item.get("constraints")),
            limits=copy.deepcopy(item.get("limits")), determinism=item.get("determinism"),
            exclusive=bool(item.get("exclusive")), requires_permit=bool(item.get("requires_permit")),
            native=item.get("native"), extra=extra))
    safety = manifest["safety"]
    envelope = SafetyEnvelope(
        risk_class=safety["risk_class"], envelope=copy.deepcopy(safety.get("envelope") or {}),
        interlocks=copy.deepcopy(safety.get("interlocks") or []),
        requires_permit=list(safety.get("requires_permit") or []), estop=copy.deepcopy(safety["estop"]),
        safe_state=copy.deepcopy(safety["safe_state"]), max_cumulative=copy.deepcopy(safety.get("max_cumulative") or {}))
    try:
        return DriverDevice(
            manifest["device_id"], manifest.get("display_name"), mode=manifest["mode"], resources=resources,
            capabilities=capabilities, safety=envelope, fidelity=copy.deepcopy(manifest.get("fidelity")),
            profile=copy.deepcopy(manifest.get("profile")), instance_id=manifest.get("instance_id"),
            models=list(manifest["models"]) if manifest.get("models") else None,
            vendor=copy.deepcopy(manifest.get("vendor")), model=manifest.get("model"),
            firmware=manifest.get("firmware"), serial=manifest.get("serial"),
            provenance=copy.deepcopy(manifest.get("provenance")), bridge=bridge, strict=True if strict else None,
            watchdog_ms=manifest.get("watchdog_ms"))
    except MHSStrictError as exc:
        raise DriverDefinitionError([item.text() for item in exc.findings], driver=str(manifest["device_id"]),
                                    findings=exc.findings) from exc


_device = device_from_manifest


def strict_findings(driver: Any, *, backend: str | None = None) -> list[Any]:
    """Every strict-mode finding of ``driver``'s device for ``backend`` (empty when it would be served)."""
    from .._server import strict as _strict

    manifest = build_manifest(driver, backend=backend)
    try:
        device = _device(manifest, None)
    except DriverDefinitionError as exc:
        return list(exc.findings)
    return list(_strict.resolve_device(device).findings)


def build_device(driver: Any, *, upstream: Mapping[str, str] | None = None) -> DriverDevice:
    """The strict :class:`mhs.server.Device` serving the driver instance ``driver`` on its backend."""
    from .base import Driver

    if not isinstance(driver, Driver):
        raise TypeError(f"build_device needs a Driver instance, got {driver!r}")
    manifest = build_manifest(driver, backend=driver.backend, upstream=upstream)
    return _device(manifest, driver)


def remap_overlay(overlay: Any, aliases: Mapping[str, str]) -> Any:
    """``site_limits`` with each ``{hardware id: served id}`` entry moved to the served id (a fake narrows like its hardware).

    An entry the overlay already has for the served id is kept as written (the hardware entry is then left alone).
    ``overlay`` may be a document or a path; ``None`` stays ``None``.
    """
    if overlay is None or not aliases:
        return overlay
    if isinstance(overlay, (str, os.PathLike)):
        try:
            document = json.loads(Path(overlay).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return overlay  # the server reports the unreadable file
    elif isinstance(overlay, Mapping):
        document = copy.deepcopy(dict(overlay))
    else:
        return overlay
    devices = document.get("devices")
    if not isinstance(devices, dict):
        return document
    for source, target in aliases.items():
        if source != target and source in devices and target not in devices:
            # The served device takes the hardware entry; the hardware id is not served here.
            devices[target] = devices.pop(source)
    return document


def build_server(drivers: Any, *, endpoint_id: str = DEFAULT_ENDPOINT_ID, site_limits: Any = None,
                 state_dir: Any = None, upstream: Mapping[str, str] | None = None, allow_hardware: bool = False,
                 **server_options: Any) -> MHSServer:
    """A strict :class:`mhs.server.MHSServer` serving one driver instance (or a list of them).

    ``site_limits`` is the operator overlay; entries for a hardware device id
    also narrow its fake view.  A driver on its hardware backend needs
    ``allow_hardware=True`` and a ``state_dir`` (:func:`mhs.adapter.load` also
    checks the review state of the package).  ``server_options`` go to
    ``MHSServer`` (``auth_tokens``, ``armed``, ``approval_verifier``, ...);
    ``strict`` cannot be changed.
    """
    if "strict" in server_options:
        raise TypeError("drivers are always served in strict mode; strict cannot be passed")
    items = list(drivers) if isinstance(drivers, (list, tuple)) else [drivers]
    hardware = [item for item in items if getattr(item, "is_hardware", False)]
    if hardware and not allow_hardware:
        raise PermissionError(f"{type(hardware[0]).__name__} runs its hardware backend: pass allow_hardware=True")
    if hardware and state_dir is None:
        raise PermissionError(f"{type(hardware[0]).__name__} runs its hardware backend: a state_dir is required "
                              "(the e-stop latch and the command journal must survive a restart)")
    devices = [build_device(item, upstream=upstream) for item in items]
    aliases = {hardware_device_id(item._model): device.device_id for item, device in zip(items, devices)}
    return MHSServer(endpoint_id, devices, strict=True, site_limits=remap_overlay(site_limits, aliases),
                     state_dir=state_dir, **server_options)


def close_server(server: Any) -> None:
    """Close the server (evidence, ``state_dir``) and every driver it serves."""
    try:
        server.close()
    finally:
        for device in list(getattr(server, "devices", {}).values()):
            bridge = getattr(device, "bridge", None)
            close = getattr(bridge, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001 - closing never fails
                    pass


# ---------------------------------------------------------------------------
# reference file
# ---------------------------------------------------------------------------


def build_reference(driver: Any, *, backend: str | None = None, overlay: Any = None,
                    provenance: Mapping[str, Any] | None = None,
                    upstream: Mapping[str, str] | None = None) -> dict[str, Any]:
    """The reference file of ``driver`` (declared view unless ``backend`` is given).

    Facts, tags, ``safety.estop.native`` and the action names come from the
    driver; ``Limit.operator_required`` reasons and x-cap examples are added
    to what :func:`mhs.reference_file.render` produces; ``provenance`` may add
    ``authored_by``/``reviewed_by`` (from ``driver.lock.json``).
    """
    model, _instance = _model_of(driver)
    manifest = build_manifest(driver, backend=backend, upstream=upstream, instance_id="0" * 26)
    manifest.pop("instance_id", None)
    reference = _reference_file.render(
        manifest, overlay=overlay, facts=list(model.facts), provenance=provenance,
        upstream=dict(upstream) if upstream else (dict(model.upstream) if model.upstream else None),
        estop_native=model.estop.native if model.estop is not None else None)
    _add_driver_details(reference, model)
    problems = _reference_file.validate(reference)
    if problems:  # pragma: no cover - the additions follow reference.schema.json
        raise _reference_file.ReferenceFileError("reference file invalid after driver details: " + "; ".join(problems[:5]))
    return reference


def _add_driver_details(reference: dict[str, Any], model: _model.DriverModel) -> None:
    if model.operator_bridges:
        # E3: the bridges the operator must run (RosDriver.operator_bridges); the package never starts them.
        reference.setdefault("safety", {})["operator_bridges"] = [dict(item) for item in model.operator_bridges]
    reasons = model.operator_reasons
    by_name = {}
    for binding in model.bindings:
        by_name[binding.name] = binding
    for entry in (reference.get("safety") or {}).get("operator_required") or []:
        if entry.get("reason"):
            continue
        if "path" in entry:
            binding = by_name.get(str(entry.get("name")))
            reason = reasons.get((binding.capability_id, str(entry["path"]))) if binding is not None else None
        else:
            reason = reasons.get((_model.CONFIGURE, str(entry.get("name"))))
        if reason:
            entry["reason"] = reason[:500]
    for entry in reference.get("actions") or []:
        binding = by_name.get(str(entry.get("name")))
        if binding is not None and binding.examples and "examples" not in entry:
            entry["examples"] = copy.deepcopy(binding.examples)
