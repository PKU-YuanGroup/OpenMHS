"""OpenMHS reference endpoints: protocol fixtures, not driver templates.

Four pure-stdlib, deterministic endpoints exercise the wire protocol, the
runtime safety rules and the conformance suite.  They are test fixtures with
hand-written bridges and manifests; a per-repository driver is written with
:mod:`mhs.driver` (``MHS/sdk/docs/driver-authoring.md``, tutorial
``MHS/sdk/examples/thermostat``) and never copies these modules.  They run in
compatibility mode: some bindings still drift from their catalogue classes
(field names, resource kinds; listed in ``MHS/sdk/docs/reference-endpoints.md``)
and are realigned after the pilot, while the MCP tool names stay unchanged.
Every binding serves the verb of its catalogue class (:func:`build_server`).

``conveyor``
    A fixed-step conveyor workcell with door interlock, latching e-stop,
    diverter routing, permits and exact deterministic replay.  The test profile
    (``--test-profile``) adds ``x-cap.mhs-test.*`` fault injection for negative
    conformance tests.

``lab``
    One endpoint with three simulated devices -- an analytic pipette, a plate
    reader and a sample mover -- for multi-device orchestration demos.

``arm``
    A 2-DOF planar arm with integer fixed-point kinematics and an optional
    seeded-noise mode for seeded-determinism testing.

``replay``
    A read-only endpoint serving a recorded evidence bundle.  All device modes
    are ``replay``: mutations are rejected with ``MHS.MODE.READ_ONLY``, reads and
    snapshots work, and recorded revisions are selected through resource reads
    with filter.revision. Public mhs.restore remains read-only-rejected.

Entry point::

    python3 -m mhs.reference <conveyor|lab|arm|replay> [--port 7400] [--stdio]

``serve()`` here is a thin adapter over ``mhs.server.MHSServer``; it never
re-implements the protocol.  The construction glue is isolated so that a core
API change is a one-file fix.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from typing import Any

from mhs.reference._common import EndpointSpec, catalogue_verb

__all__ = ["ENDPOINTS", "EndpointSpec", "build_endpoint", "build_server", "serve"]


ENDPOINTS = ("conveyor", "lab", "arm", "replay")


def build_endpoint(
    name: str,
    *,
    endpoint_id: str | None = None,
    test_profile: bool = False,
    bundle: str | None = None,
    noise: bool = False,
    seed: int = 0,
) -> EndpointSpec:
    """Build one endpoint specification by name."""

    if name == "conveyor":
        from mhs.reference import conveyor

        endpoint_id = endpoint_id or "mhs://localhost:7400"
        return conveyor.build(endpoint_id, test_profile=test_profile)
    if name == "lab":
        from mhs.reference import lab

        endpoint_id = endpoint_id or "mhs://localhost:7400"
        return lab.build(endpoint_id)
    if name == "arm":
        from mhs.reference import arm

        endpoint_id = endpoint_id or "mhs://localhost:7400"
        return arm.build(endpoint_id, noise=noise, seed=seed)
    if name == "replay":
        from mhs.reference import replay

        endpoint_id = endpoint_id or "mhs://localhost:7400"
        if not bundle:
            raise SystemExit("replay endpoint requires --bundle <recorded-bundle.json>")
        return replay.build(endpoint_id, bundle_path=bundle)
    raise SystemExit(f"unknown reference endpoint {name!r}; choose from {', '.join(ENDPOINTS)}")


# ---------------------------------------------------------------------------
# server construction / serving (the only place that touches mhs.server)
# ---------------------------------------------------------------------------


def build_server(spec: EndpointSpec, *, log_ready: bool = True) -> Any:
    """Materialise ``mhs.server`` objects for an :class:`EndpointSpec`.

    Each binding serves the verb of its catalogue class
    (:func:`mhs.reference._common.catalogue_verb`; an ``x-cap`` extension keeps
    the verb it declares, else ``invoke``), and the served manifest states it.
    The server runs in compatibility mode: the remaining drift of the
    fixtures is reported as ``MHSStrictWarning`` findings.
    """

    try:
        from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope
    except ImportError as exc:  # pragma: no cover - core not built yet
        raise SystemExit(
            "mhs.server is not available; the MHS core SDK (sdk-core) must be present "
            f"to run a reference endpoint ({exc})"
        ) from exc

    devices = []
    for manifest in spec.devices:
        bridge = spec.bridges[manifest["device_id"]]
        resources = [
            Resource(
                item["resource_id"],
                item.get("kind", "generic"),
                title=item.get("title"),
                state_schema=item.get("state_schema"),
                state=item.get("state"),
                revision=int(item.get("revision", 0)),
                sampling=item.get("sampling"),
                hash_exclusions=item.get("hash_exclusions"),
            )
            for item in manifest["resources"]
        ]
        capabilities = [
            Capability(
                item["capability_id"],
                item.get("resource"),
                title=item.get("title"),
                verb=catalogue_verb(item["capability_id"], item.get("verb")),
                input_schema=item.get("input_schema"),
                output_schema=item.get("output_schema"),
                semantics=item.get("semantics"),
                constraints=item.get("constraints"),
                limits=item.get("limits"),
                determinism=item.get("determinism"),
                exclusive=item.get("exclusive"),
                requires_permit=bool(item.get("requires_permit")),
                native=item.get("native"),
            )
            for item in manifest["capabilities"]
        ]
        for item in capabilities:
            item.publish_verb = True  # the manifest states the (catalogue) verb, as hello does
        safety = SafetyEnvelope(**manifest["safety"])
        devices.append(
            Device(
                manifest["device_id"],
                manifest.get("display_name"),
                mode=manifest["mode"],
                resources=resources,
                capabilities=capabilities,
                safety=safety,
                fidelity=manifest.get("fidelity"),
                profile=manifest.get("profile"),
                instance_id=manifest.get("instance_id"),
                models=manifest.get("models"),
                vendor=manifest.get("vendor"),
                model=manifest.get("model"),
                firmware=manifest.get("firmware"),
                serial=manifest.get("serial"),
                conformance=manifest.get("conformance"),
                provenance=manifest.get("provenance"),
                signatures=manifest.get("signatures"),
                bridge=bridge,
            )
        )
    return MHSServer(
        endpoint_id=spec.endpoint_id,
        devices=devices,
        features=list(spec.features),
        log_ready=log_ready,
    )


def _ready_event(spec: EndpointSpec, transport: str, *, url: str | None = None) -> dict[str, Any]:
    devices = []
    for manifest in spec.devices:
        devices.append(
            {
                "device_id": manifest["device_id"],
                "mode": manifest["mode"],
                "capabilities": [cap["capability_id"] for cap in manifest["capabilities"]],
            }
        )
    return {
        "mhs_ready": True,
        "transport": transport,
        "endpoint_id": spec.endpoint_id,
        "url": url,
        "devices": devices,
        "profile": spec.profile,
        "name": spec.name,
        "test_profile": any(cap["capability_id"].startswith("x-cap.mhs-test.") for d in spec.devices for cap in d["capabilities"]),
    }


def serve(
    spec: EndpointSpec,
    *,
    host: str = "127.0.0.1",
    port: int | None = 7400,
    stdio: bool = False,
) -> None:
    """Serve an endpoint over stdio or loopback HTTP until interrupted."""

    if stdio or port is None:
        sys.stderr.write(json.dumps(_ready_event(spec, "stdio")) + "\n")
        sys.stderr.flush()
        server = build_server(spec, log_ready=False)
        try:
            server.run_stdio()
        except KeyboardInterrupt:  # pragma: no cover - interactive path
            pass
        finally:
            spec.close()
        return

    server = build_server(spec, log_ready=False)
    url = f"http://{host}:{port}"
    start_http = getattr(server, "start_http", None)
    handle = None
    if callable(start_http):
        handle = start_http(host, port)
        actual_port = int(getattr(handle, "port", port) or port)
        url = getattr(handle, "url", f"http://{host}:{actual_port}")
        sys.stdout.write(json.dumps(_ready_event(spec, "http", url=url)) + "\n")
        sys.stdout.flush()
        try:
            while True:
                time.sleep(0.2)
        except KeyboardInterrupt:  # pragma: no cover - interactive path
            pass
        finally:
            shutdown = getattr(handle, "shutdown", None)
            if callable(shutdown):
                shutdown()
            spec.close()
        return

    # Fallback for a core without start_http: announce the expected URL, then block.
    sys.stdout.write(json.dumps(_ready_event(spec, "http", url=url)) + "\n")
    sys.stdout.flush()
    try:
        server.run_http(host, port)
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        spec.close()


def _endpoint_id_for(url: str, name: str) -> str:
    prefix = "http://"
    hostport = url[len(prefix) :] if url.startswith(prefix) else url
    return f"mhs://{hostport}"
