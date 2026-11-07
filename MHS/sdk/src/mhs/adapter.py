"""Load a driver package (or an ``mhs-adapter.json``) into a strict OpenMHS endpoint.

::

    from mhs.adapter import load

    server = load("MHS/drivers/labs/owner__repo")              # fake backend, mode "simulated"
    server = load(path, backend="hardware", allow_hardware=True, state_dir="/var/lib/mhs/bath")

:func:`load` always returns an :class:`mhs.server.MHSServer` in strict mode
(plan 3.6): the catalogue verbs and schemas, output validation,
``MHS.SAFETY.LIMITS_UNSET``, operator-only hardware reset and arming all
apply.  The backend rules (plan 3.9) are checked before any backend object is
created:

* ``backend`` is ``"hardware"``, ``"fake"`` or ``"sim"`` (any other name is
  refused, ``reason="backend_unknown"``); only ``hardware`` drives the device;
* ``backend="hardware"`` needs ``allow_hardware=True`` and a ``state_dir``
  (the e-stop latch and the idempotency journal must survive a restart);
* a hardware driver at R2 or above needs ``driver.lock.json``, and a
  model-authored one (``authored_by.kind == "model"``) a human
  ``reviewed_by`` signature, before a hardware backend may start;
* ``fake`` and ``sim`` serve the device as ``mode: simulated`` with the fake
  fidelity contract and ``models: [<hardware id>]``;
* the device contract of a decorated or declarative driver is resolved in
  strict mode before its backend is opened, so a driver strict mode refuses
  (e.g. SAFE-045) never connects.  Simulator families (Gymnasium, MuJoCo)
  derive their contract from the opened backend and are checked after it
  opens; ``site_limits`` are checked when the server starts.

An ``mhs-adapter.json`` (the declarative interchange format,
``adapter.schema.json``) is served with the bridge family each of its
``bridges[]`` names (python-object, serial, scpi/scpi-visa, gymnasium, mujoco)
or, with ``kind: "driver"`` and ``config.path``, by the driver package it
points to (a driver directory, never another ``mhs-adapter.json``).  A
manifest that declares a hardware or hybrid device has no fake: it needs the
hardware rules above; one whose devices are all simulated has no hardware
backend.  A serial or SCPI bridge drives a physical transport (a port, host
or VISA resource), so its device must be declared ``hardware`` or ``hybrid``
(an ``mhs-adapter.json`` has no fake transport; serve a driver directory with
a ``fake`` backend instead).  Every device is resolved in strict mode before
any bridge or native object is created.

Refusals raise :class:`LoadError` (``reason`` says which rule);
definition problems raise :class:`mhs.driver.DriverDefinitionError`.
Close the endpoint and its drivers with :func:`mhs.driver.close_server`.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .driver.base import Driver
from .driver.build import (
    BACKENDS,
    DEFAULT_ENDPOINT_ID,
    build_server,
    close_server,
    device_from_manifest,
    strict_findings,
)
from .driver.loader import driver_class, read_lock, review_problem
from .driver.spec import DriverDefinitionError
from .server import MHSServer

__all__ = ["ADAPTER_FILE", "LoadError", "close_server", "load", "load_driver"]

ADAPTER_FILE = "mhs-adapter.json"
_UNSET: Any = object()
_HARDWARE_MODES = ("hardware", "hybrid")
#: mhs-adapter.json bridge kinds that open a physical transport (port, host, VISA resource) from their config.
_TRANSPORT_BRIDGES = ("serial", "scpi", "scpi-visa")


class LoadError(ValueError):
    """A backend rule refused the load; ``reason`` is one of the ``REASONS``."""

    REASONS = ("not_found", "backend_unknown", "hardware_not_allowed", "state_dir_required", "review_required",
               "no_hardware_backend", "no_fake_backend", "adapter_invalid", "bridge_unsupported",
               "simulation_deployment_invalid")

    def __init__(self, message: str, *, reason: str):
        self.reason = reason
        super().__init__(message)


def _known_backend(backend: Any) -> None:
    if not isinstance(backend, str) or backend not in BACKENDS:
        raise LoadError(f"backend {backend!r} is not one of {list(BACKENDS)}: only 'hardware' drives the device, "
                        "'fake' and 'sim' are served as mode simulated", reason="backend_unknown")


def _check_backend(*, name: str, mode: str, risk: str, backend: str, allow_hardware: bool, state_dir: Any,
                   lock: Mapping[str, Any] | None, lock_problems: list[str], require_human: bool = False,
                   companion_stop: bool = False) -> None:
    _known_backend(backend)
    if backend != "hardware":
        return
    if mode not in _HARDWARE_MODES:
        raise LoadError(f"{name} is a {mode} driver; it has no hardware backend", reason="no_hardware_backend")
    if not allow_hardware:
        raise LoadError(f"{name}: a hardware backend needs allow_hardware=True (an operator decision; the "
                        "acceptance gate never passes it)", reason="hardware_not_allowed")
    if state_dir is None:
        raise LoadError(f"{name}: a hardware backend needs state_dir, so the e-stop latch and the command journal "
                        "survive a restart", reason="state_dir_required")
    problem = review_problem(lock, lock_problems, risk=risk, require_human=require_human,
                             companion_stop=companion_stop)
    if problem is not None:
        raise LoadError(f"{name}: {problem}", reason="review_required")


def _resolve(path: str | os.PathLike[str]) -> tuple[str, Path]:
    target = Path(path).expanduser()
    if target.is_file() and target.suffix == ".json":
        return "adapter", target.resolve()
    if target.is_dir():
        if (target / "driver.py").is_file():
            return "driver", target.resolve()
        if (target / ADAPTER_FILE).is_file():
            return "adapter", (target / ADAPTER_FILE).resolve()
    raise LoadError(f"{path} is neither a driver directory (driver.py) nor an {ADAPTER_FILE}", reason="not_found")


def _upstream(lock: Mapping[str, Any] | None) -> dict[str, str] | None:
    upstream = lock.get("upstream") if isinstance(lock, Mapping) else None
    if isinstance(upstream, Mapping) and upstream.get("repo_url") and upstream.get("commit"):
        return {"repo": str(upstream["repo_url"]), "commit": str(upstream["commit"])}
    return None


def load_driver(path: str | os.PathLike[str], backend: str = "fake", *, allow_hardware: bool = False,
                state_dir: Any = None, options: Mapping[str, Any] | None = None, native: Any = _UNSET,
                native_wrapper: Any = None, simulation_deployment: Mapping[str, Any] | None = None) -> Driver:
    """The opened :class:`~mhs.driver.Driver` instance of a driver directory (same backend rules as :func:`load`).

    ``options`` are the keyword arguments of the backend factory (a port, a
    host); ``native`` passes the backend object directly (a recorder in a
    test), skipping the factory; ``native_wrapper`` wraps the object the
    factory creates before ``setup()`` runs (the gate's
    :class:`mhs.testing.Recorder`). ``simulation_deployment`` is an explicit
    live-simulator endpoint and fidelity contract for a simulated
    :class:`mhs.driver.RosDriver`, used only with ``backend="sim"``. It is
    separate from factory options and is never inferred from a package.
    """
    _known_backend(backend)
    kind, directory = _resolve(path)
    if kind != "driver":
        raise LoadError(f"{path} is not a driver directory", reason="not_found")
    cls = driver_class(directory)
    from .driver.families import RosDriver
    from .driver.tag_driver import TagDriver  # tag-bridge helper (2026-11-04): human hardware review at every risk
    if simulation_deployment is not None and not issubclass(cls, RosDriver):
        raise LoadError("simulation_deployment is supported only by RosDriver", reason="simulation_deployment_invalid")
    from .driver.hardware_stop import declares_companion_stop

    lock, lock_problems = read_lock(directory)
    if getattr(cls, "_needs_instance", False):
        mode, risk = str(getattr(cls, "mode", "simulated")), str(getattr(cls, "risk", "R0"))
    else:
        model = cls.driver_model()
        mode, risk = model.mode, model.risk
    _check_backend(name=cls.__qualname__, mode=mode, risk=risk, backend=backend, allow_hardware=allow_hardware,
                   state_dir=state_dir, lock=lock, lock_problems=lock_problems,
                   require_human=issubclass(cls, (RosDriver, TagDriver)),
                   companion_stop=declares_companion_stop(cls))
    if not getattr(cls, "_needs_instance", False):
        # Resolve the device contract before the backend opens: a refused driver never connects (or runs setup()).
        refused = [item for item in strict_findings(cls, backend=backend) if getattr(item, "refuse", True)]
        if refused:
            raise DriverDefinitionError([item.text() for item in refused], driver=cls.__qualname__, findings=refused)
    kwargs: dict[str, Any] = {"backend": backend, "base_dir": directory, "options": dict(options or {})}
    if native is not _UNSET:
        kwargs["native"] = native
    if native_wrapper is not None:
        kwargs["native_wrapper"] = native_wrapper
    if simulation_deployment is not None:
        kwargs["simulation_deployment"] = simulation_deployment
    driver = cls(**kwargs)
    try:
        driver.open()
    except BaseException:
        driver.close()
        raise
    return driver


def load(path: str | os.PathLike[str], backend: str = "fake", site_limits: Any = None,
         allow_hardware: bool = False, state_dir: Any = None, *, endpoint_id: str = DEFAULT_ENDPOINT_ID,
         options: Mapping[str, Any] | None = None, native: Any = _UNSET,
         simulation_deployment: Mapping[str, Any] | None = None, **server_options: Any) -> MHSServer:
    """A strict :class:`~mhs.server.MHSServer` serving the driver directory or ``mhs-adapter.json`` at ``path``.

    ``site_limits`` is the operator overlay (``site-limits.json`` document or
    path); its entries for the hardware device id also narrow the fake view.
    ``simulation_deployment`` is forwarded only to a ROS driver, including
    one referenced by an adapter's single ``driver`` bridge.
    ``server_options`` go to :class:`~mhs.server.MHSServer` (``auth_tokens``,
    ``armed``, ``approval_verifier``, ``fsync`` ...); ``strict`` is always
    ``True`` and cannot be passed.
    """
    if "strict" in server_options:
        raise TypeError("mhs.adapter.load always serves in strict mode; strict cannot be passed")
    _known_backend(backend)
    kind, target = _resolve(path)
    if kind == "adapter":
        return _load_adapter(target, backend=backend, site_limits=site_limits, allow_hardware=allow_hardware,
                             state_dir=state_dir, endpoint_id=endpoint_id, options=options, native=native,
                             server_options=server_options, simulation_deployment=simulation_deployment)
    driver = load_driver(target, backend, allow_hardware=allow_hardware, state_dir=state_dir, options=options,
                         native=native, simulation_deployment=simulation_deployment)
    lock, _problems = read_lock(target)
    try:
        return build_server(driver, endpoint_id=endpoint_id, site_limits=site_limits, state_dir=state_dir,
                            upstream=_upstream(lock), allow_hardware=allow_hardware, **server_options)
    except BaseException:
        driver.close()
        raise


# ---------------------------------------------------------------------------
# mhs-adapter.json
# ---------------------------------------------------------------------------


def _load_adapter(path: Path, *, backend: str, site_limits: Any, allow_hardware: bool, state_dir: Any,
                  endpoint_id: str, options: Mapping[str, Any] | None, native: Any,
                  server_options: Mapping[str, Any], simulation_deployment: Mapping[str, Any] | None = None) -> MHSServer:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LoadError(f"{path} cannot be read: {exc}", reason="adapter_invalid") from exc
    from .schema import default_store

    problems = default_store().validate(document, "adapter.schema.json") if isinstance(document, dict) else ["not an object"]
    if problems:
        raise LoadError(f"{path} is not a valid {ADAPTER_FILE}: " + "; ".join(problems[:5]), reason="adapter_invalid")
    base_dir = path.parent
    bridges = list(document.get("bridges") or [])
    devices = list(document["devices"])
    drivers = [item for item in bridges if item.get("kind") == "driver"]
    if drivers:
        if len(bridges) != 1:
            raise LoadError(f"{path}: a 'driver' bridge must be the only bridge", reason="adapter_invalid")
        config = drivers[0].get("config") or {}
        relative = config.get("path", ".")
        if not isinstance(relative, str):
            raise LoadError(f"{path}: bridges[0].config.path must be a directory path", reason="adapter_invalid")
        target = base_dir / relative
        if not (target.is_dir() and (target / "driver.py").is_file()):
            # Only a driver directory: a path back to an mhs-adapter.json would load itself again.
            raise LoadError(f"{path}: bridges[0].config.path ({relative!r}) must name a driver directory "
                            "(driver.py)", reason="adapter_invalid")
        return load(target, backend, site_limits, allow_hardware, state_dir, endpoint_id=endpoint_id,
                    options=options, native=native, simulation_deployment=simulation_deployment, **server_options)
    if simulation_deployment is not None:
        raise LoadError("simulation_deployment requires an adapter's single RosDriver bridge",
                        reason="simulation_deployment_invalid")
    if len(bridges) != len(devices):
        raise LoadError(f"{path}: give one bridge per device ({len(devices)} devices, {len(bridges)} bridges)",
                        reason="adapter_invalid")
    for manifest, entry in zip(devices, bridges):
        if entry.get("kind") in _TRANSPORT_BRIDGES and manifest.get("mode") not in _HARDWARE_MODES:
            # A simulated label on a real port or instrument is never served (fake and sim never reach hardware).
            raise LoadError(f"{path}: device {manifest.get('device_id')} is declared {manifest.get('mode')!r}, but "
                            f"its {entry.get('kind')} bridge drives a physical transport (port, host or VISA "
                            f"resource) and an {ADAPTER_FILE} has no fake transport; declare the device hardware "
                            "(served under the hardware rules) or serve a driver directory with a fake backend",
                            reason="no_fake_backend")
    lock, lock_problems = read_lock(base_dir)
    risk_order = ("R0", "R1", "R2", "R3")
    hardware = [item for item in devices if item.get("mode") in _HARDWARE_MODES]
    if hardware:
        if backend != "hardware":
            raise LoadError(f"{path} declares {'a hardware' if len(hardware) == 1 else 'hardware'} device "
                            f"({hardware[0]['device_id']}); an {ADAPTER_FILE} has no fake backend -- serve the driver "
                            "directory for a fake", reason="no_fake_backend")
        risk = max((str((item.get("safety") or {}).get("risk_class") or "R0") for item in hardware),
                   key=lambda value: risk_order.index(value) if value in risk_order else 0)
        _check_backend(name=str(document.get("adapter_id")), mode="hardware", risk=risk, backend=backend,
                       allow_hardware=allow_hardware, state_dir=state_dir, lock=lock, lock_problems=lock_problems)
    elif backend == "hardware":
        raise LoadError(f"{path} declares only simulated devices; it has no hardware backend",
                        reason="no_hardware_backend")
    served_manifests = []
    for manifest in devices:
        served = copy.deepcopy(manifest)
        served.pop("instance_id", None)  # every start gets a fresh instance id (adapter.schema.json)
        # Strict refusals (risk floor, SAFE-045 ...) come before any bridge or native object exists.
        device_from_manifest(served, None)
        served_manifests.append(served)
    made: list[Any] = []
    served_devices = []
    try:
        for served, entry in zip(served_manifests, bridges):
            bridge = _make_bridge(entry, served, base_dir)
            made.append(bridge)
            served_devices.append(device_from_manifest(served, bridge))
        return MHSServer(endpoint_id, served_devices, strict=True, site_limits=site_limits, state_dir=state_dir,
                         **server_options)
    except BaseException:
        for bridge in made:
            try:
                bridge.close()
            except Exception:  # noqa: BLE001 - closing never fails
                pass
        raise


def _make_bridge(entry: Mapping[str, Any], manifest: Mapping[str, Any], base_dir: Path) -> Any:
    kind = str(entry.get("kind"))
    config = copy.deepcopy(dict(entry.get("config") or {}))
    device_id = str(manifest["device_id"])
    if kind == "python-object":
        from .bridge.python import PythonObjectBridge

        schemas = {str(item["capability_id"]): {"output_schema": copy.deepcopy(item["output_schema"])}
                   for item in manifest.get("capabilities") or [] if isinstance(item.get("output_schema"), Mapping)}
        return PythonObjectBridge(config, device_id=device_id, strict=True, base_dir=base_dir,
                                  capability_schemas=schemas)
    if kind == "serial":
        from .bridge.serial import SerialBridge

        return SerialBridge(config, device_id=device_id)
    if kind in ("scpi", "scpi-visa"):
        from .bridge.scpi import ScpiBridge

        config.setdefault("strict", True)
        return ScpiBridge(config, device_id=device_id)
    if kind == "gymnasium":
        from .bridge.gymnasium import GymnasiumBridge

        allowed = {"env_id", "env_spec", "seed", "render_mode", "max_steps", "autoreset", "max_ticks"}
        unknown = sorted(set(config) - allowed)
        if unknown:
            raise LoadError(f"gymnasium bridge config keys {unknown} are not supported (allowed: {sorted(allowed)})",
                            reason="adapter_invalid")
        return GymnasiumBridge(device_id=device_id, **config)
    if kind == "mujoco":
        from .bridge.mujoco import MujocoBridge

        allowed = {"model_path", "model_xml", "seed", "max_ticks"}
        unknown = sorted(set(config) - allowed)
        if unknown:
            raise LoadError(f"mujoco bridge config keys {unknown} are not supported (allowed: {sorted(allowed)})",
                            reason="adapter_invalid")
        if config.get("model_path"):
            config["model_path"] = str(base_dir / str(config["model_path"]))
        return MujocoBridge(device_id=device_id, **config)
    raise LoadError(f"bridge kind {kind!r} cannot be served from an {ADAPTER_FILE} (python-object, serial, scpi, "
                    "scpi-visa, gymnasium, mujoco or driver)", reason="bridge_unsupported")
