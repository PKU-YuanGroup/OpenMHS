"""Read-only replay endpoint over a recorded evidence bundle (an OpenMHS reference endpoint).

This module is a protocol fixture, not a driver template: it serves a
recording to exercise replay mode (FID-003/FID-028) and the conformance
suite.  The recorded device's bindings are served with the verbs of their
catalogue classes and keep their recorded ids, so MCP tool names are those of
the recording.

A *recording bundle* is a small, self-describing JSON document::

    {
      "kind": "mhs.reference.replay-bundle",
      "bundle_version": "1.0",
      "recorded_at": "2026-10-20T00:00:00Z",
      "source_endpoint": "mhs://localhost:7400",
      "device": { ...original device manifest... },
      "frames": [
        {"revision": 0, "state": {"workcell": {...}}, "state_hash": "sha256:...",
         "command_id": null, "capability_id": null},
        ...
      ],
      "receipts": [ ...evidence receipts... ],
      "head_digest": "sha256:..."
    }

The replay endpoint reconstructs a ``mode="replay"`` device from it.  Mutating
commands and public ``mhs.restore`` are rejected with ``MHS.MODE.READ_ONLY``.
Reads and snapshots work; ``mhs.resource.read filter.revision`` selects a
recorded revision's state. ``build_replay_bundle`` records such a bundle from
a live reference endpoint via the standard client API.

Provenance (FID-003/FID-028)
----------------------------

``load_bundle`` verifies the source evidence chain *and* cross-binds every
non-genesis frame to exactly one completed receipt of the same device on
command id, capability (plus ``input_digest`` when recorded), revision and
state hash, as well as the consecutive revision chain.  The first frame is the
recorded baseline: it is an observation, not an execution, so it carries no
``command_id``/``capability_id`` and no receipt; its revision must equal the
first source receipt's ``state_revision_before``.  A recording whose frames
contradict its own receipts is rejected before an endpoint is constructed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from mhs.bridge.replay import RECORDING_RESOURCE, ReplayBridge
from mhs.reference._common import INSTANCE_IDS, EndpointSpec, device, resource

__all__ = [
    "BUNDLE_KIND",
    "build",
    "build_replay_bundle",
    "load_bundle",
    "write_bundle",
]

BUNDLE_KIND = "mhs.reference.replay-bundle"
BUNDLE_VERSION = "1.0"

REPLAY_SLUG = "replay/recorded-device"


def load_bundle(path: str | Path) -> dict[str, Any]:
    """Load and structurally validate a recording bundle."""

    from mhs.errors import MHSError

    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise MHSError(
            "MHS.EVIDENCE.NOT_FOUND", f"cannot read replay bundle {path!r}: {exc}", {"retryable": False}
        ) from exc
    except json.JSONDecodeError as exc:
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID", f"replay bundle {path!r} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(document, Mapping):
        raise MHSError("MHS.EVIDENCE.CHAIN_INVALID", "replay bundle must be a JSON object")
    if document.get("kind") != BUNDLE_KIND:
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID",
            f"replay bundle kind must be {BUNDLE_KIND!r}; got {document.get('kind')!r}",
            {
                "retryable": False,
                "remediation": "Record a replay bundle with mhs.reference.replay.build_replay_bundle().",
            },
        )
    if not isinstance(document.get("device"), Mapping):
        raise MHSError("MHS.EVIDENCE.CHAIN_INVALID", "replay bundle needs a recorded device manifest")
    frames = document.get("frames")
    if not isinstance(frames, list) or not frames:
        raise MHSError("MHS.EVIDENCE.CHAIN_INVALID", "replay bundle needs at least one recorded frame")
    _validate_bundle_integrity(document)
    return dict(document)


def _validate_bundle_integrity(document: Mapping[str, Any]) -> None:
    """Recompute the bundle digest, source chain and every recorded state hash.

    A replay claim is only meaningful if the served frames are bound to the
    recording's evidence chain (FID-003/FID-028).  Corruption is rejected here,
    before any endpoint is constructed.
    """

    from mhs import canonical
    from mhs.errors import MHSError
    from mhs.evidence import verify_bundle

    declared_digest = document.get("bundle_digest")
    if not isinstance(declared_digest, str):
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID",
            "replay bundle has no bundle_digest; recapture it with build_replay_bundle()",
            {"retryable": False},
        )
    unsigned = {key: value for key, value in document.items() if key != "bundle_digest"}
    recomputed = canonical.digest(unsigned)
    if recomputed != declared_digest:
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID",
            "replay bundle digest does not recompute (recording was modified)",
            {"retryable": False,
             "details": {"declared": declared_digest, "recomputed": recomputed}},
        )

    source = document.get("source_evidence")
    if not isinstance(source, Mapping):
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID",
            "replay bundle has no source_evidence bundle; the replay chain cannot be verified",
            {"retryable": False},
        )
    report = verify_bundle(dict(source))
    if not report.valid:
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID",
            "source evidence bundle does not verify",
            {"retryable": False,
             "details": {"errors": list(report.errors)[:8]}},
        )
    if source.get("head_digest") and source.get("head_digest") != document.get("head_digest"):
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID",
            "source evidence head does not match the recorded head_digest",
            {"retryable": False},
        )

    device = document.get("device") or {}
    resources = list(device.get("resources") or [])
    primary = document.get("primary_resource") or (
        str(resources[0].get("resource_id")) if resources else None
    )
    exclusions_by_resource = {
        str(item.get("resource_id")): list(item.get("hash_exclusions") or [])
        for item in resources
        if isinstance(item, Mapping)
    }
    seen_revisions: set[int] = set()
    for index, frame in enumerate(document.get("frames") or []):
        if not isinstance(frame, Mapping) or not isinstance(frame.get("state"), Mapping):
            raise MHSError(
                "MHS.EVIDENCE.CHAIN_INVALID",
                f"recorded frame {index} has no state document",
                {"retryable": False, "details": {"frame": index}},
            )
        revision = int(frame.get("revision", index))
        if revision in seen_revisions:
            raise MHSError(
                "MHS.EVIDENCE.CHAIN_INVALID",
                f"recorded revision {revision} appears twice",
                {"retryable": False, "details": {"frame": index}},
            )
        seen_revisions.add(revision)
        state = frame["state"]
        if primary and len(resources) <= 1 and primary in state:
            expected = canonical.state_hash(
                state[primary], exclusions_by_resource.get(primary, [])
            )
        else:
            pointers = [
                f"/{resource_id}{pointer}"
                for resource_id, exclusions in exclusions_by_resource.items()
                for pointer in exclusions
                if isinstance(pointer, str) and pointer.startswith("/")
            ]
            expected = canonical.state_hash(state, pointers)
        if frame.get("state_hash") != expected:
            raise MHSError(
                "MHS.EVIDENCE.CHAIN_INVALID",
                f"recorded state hash for revision {revision} does not recompute",
                {"retryable": False,
                 "details": {"revision": revision, "declared": frame.get("state_hash"),
                             "recomputed": expected}},
            )

    _bind_frames_to_source(
        document,
        source,
        primary=primary,
        resources=resources,
        exclusions_by_resource=exclusions_by_resource,
    )


def _bind_frames_to_source(
    document: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    primary: str | None,
    resources: list[Any],
    exclusions_by_resource: Mapping[str, list[Any]],
) -> None:
    """Cross-bind every recorded frame to the source receipt that produced it.

    FID-003/FID-028: a valid source chain is not enough.  Each non-genesis frame
    must agree with exactly one completed receipt of the *same* device on
    command id, capability (and ``input_digest`` when the recording carries it),
    ``state_revision_after`` and ``state_hash_after``; the receipts must chain
    the frames consecutively (``state_revision_before`` equals the previous
    frame's revision).

    The initial frame is not an execution result and therefore has no receipt.
    Its provenance is defined separately and explicitly: it MUST be the first
    frame, MUST NOT name a command_id or capability, and its revision MUST equal
    the first source receipt's ``state_revision_before`` (the recorded baseline).
    A frame that claims to be an execution without such a receipt is rejected.
    """

    from mhs import canonical
    from mhs.errors import MHSError

    def reject(message: str, **details: Any) -> None:
        raise MHSError(
            "MHS.EVIDENCE.CHAIN_INVALID",
            message,
            {"retryable": False, "details": details or None},
        )

    frames = sorted(
        (frame for frame in (document.get("frames") or []) if isinstance(frame, Mapping)),
        key=lambda frame: int(frame.get("revision", 0)),
    )
    manifest = document.get("device") or {}
    device_id = manifest.get("device_id") if isinstance(manifest, Mapping) else None
    if not isinstance(device_id, str) or not device_id:
        reject(
            "replay bundle device manifest declares no device_id; "
            "frames cannot be bound to source receipts"
        )

    receipts = [item for item in (source.get("receipts") or []) if isinstance(item, Mapping)]
    completed_by_command: dict[str, list[Mapping[str, Any]]] = {}
    for receipt in receipts:
        if receipt.get("status") != "completed":
            # Rejected/unknown attempts are evidence, but they did not produce a
            # recorded state and must never satisfy a frame's provenance.
            continue
        command_id = receipt.get("command_id")
        if isinstance(command_id, str) and command_id:
            completed_by_command.setdefault(command_id, []).append(receipt)

    # The top-level receipt list is a copy of the source chain.  If it disagrees,
    # the recording presents two contradictory histories.
    recorded_receipts = document.get("receipts")
    if isinstance(recorded_receipts, list) and canonical.digest(
        {"receipts": list(recorded_receipts)}
    ) != canonical.digest({"receipts": receipts}):
        reject("recorded receipts disagree with the verified source evidence chain")

    seen_commands: dict[str, int] = {}
    previous_revision: int | None = None
    for index, frame in enumerate(frames):
        revision = int(frame.get("revision", index))
        command_id = frame.get("command_id")
        capability_id = frame.get("capability_id")

        if command_id is None:
            if index != 0:
                reject(
                    "only the first recorded frame may omit command_id; "
                    "every later frame is an execution result and needs a source receipt",
                    frame=index,
                    revision=revision,
                )
            if capability_id is not None:
                reject(
                    "the initial recorded frame is a baseline observation, not an execution, "
                    "and must not name a capability",
                    frame=index,
                    revision=revision,
                )
            if receipts:
                baseline = receipts[0].get("state_revision_before")
                if baseline != revision:
                    reject(
                        "initial frame revision does not match the source chain baseline",
                        frame=index,
                        revision=revision,
                        first_receipt_state_revision_before=baseline,
                    )
            previous_revision = revision
            continue

        if not isinstance(command_id, str) or not command_id:
            reject(
                "recorded frame command_id must be a non-empty string",
                frame=index,
                revision=revision,
            )
        if not isinstance(capability_id, str) or not capability_id:
            reject(
                "recorded frame must name the capability that produced it",
                frame=index,
                revision=revision,
            )
        if command_id in seen_commands:
            reject(
                "command_id appears in more than one recorded frame; the frame/receipt mapping is ambiguous",
                frame=index,
                revision=revision,
                command_id=command_id,
                earlier_frame=seen_commands[command_id],
            )
        seen_commands[command_id] = index

        candidates = completed_by_command.get(command_id) or []
        if not candidates:
            reject(
                "recorded frame has no completed source receipt for its command_id",
                frame=index,
                revision=revision,
                command_id=command_id,
            )
        matching = [receipt for receipt in candidates if receipt.get("device_id") == device_id]
        if not matching:
            reject(
                "recorded frame has no source receipt for this device",
                frame=index,
                revision=revision,
                command_id=command_id,
                frame_device=device_id,
            )
        if len(matching) > 1:
            reject(
                "command_id maps to more than one completed source receipt; "
                "the frame/receipt mapping is ambiguous",
                frame=index,
                revision=revision,
                command_id=command_id,
                matching_receipts=len(matching),
            )
        receipt = matching[0]

        if receipt.get("capability_id") != capability_id:
            reject(
                "recorded frame capability does not match its source receipt",
                frame=index,
                revision=revision,
                command_id=command_id,
                frame_capability=capability_id,
                receipt_capability=receipt.get("capability_id"),
            )
        frame_input_digest = frame.get("input_digest")
        if isinstance(frame_input_digest, str) and receipt.get("input_digest") != frame_input_digest:
            reject(
                "recorded frame input_digest does not match its source receipt",
                frame=index,
                revision=revision,
                command_id=command_id,
            )

        if receipt.get("state_revision_after") != revision:
            reject(
                "recorded frame revision does not match its source receipt state_revision_after",
                frame=index,
                revision=revision,
                command_id=command_id,
                receipt_state_revision_after=receipt.get("state_revision_after"),
            )
        if previous_revision is not None and receipt.get("state_revision_before") != previous_revision:
            reject(
                "recorded frames are not consecutive with the source receipt chain",
                frame=index,
                revision=revision,
                command_id=command_id,
                previous_frame_revision=previous_revision,
                receipt_state_revision_before=receipt.get("state_revision_before"),
            )

        declared_hash = frame.get("state_hash")
        receipt_hash = receipt.get("state_hash_after")
        if len(resources) <= 1 and isinstance(primary, str):
            bound_hash = declared_hash
        else:
            # A multi-resource frame hash covers the whole device while a receipt
            # carries the primary resource's hash, so bind the recorded sub-state.
            resource_state = None
            state = frame.get("state")
            if isinstance(state, Mapping) and isinstance(primary, str):
                resource_state = state.get(primary)
            if not isinstance(resource_state, Mapping):
                reject(
                    "recorded frame does not contain the primary resource state needed to bind its receipt",
                    frame=index,
                    revision=revision,
                    primary_resource=primary,
                )
            bound_hash = canonical.state_hash(
                resource_state, exclusions_by_resource.get(str(primary), [])
            )
        if not isinstance(receipt_hash, str) or receipt_hash != bound_hash:
            reject(
                "recorded frame state_hash contradicts its source receipt state_hash_after",
                frame=index,
                revision=revision,
                command_id=command_id,
                frame_state_hash=declared_hash,
                receipt_state_hash_after=receipt_hash,
                bound_state_hash=bound_hash,
            )
        previous_revision = revision


def write_bundle(path: str | Path, bundle: Mapping[str, Any]) -> str:
    """Persist a bundle atomically and return its file path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)
    return str(target)


def build_replay_bundle(
    client: Any,
    *,
    device_id: str | None = None,
    commands: Iterable[Mapping[str, Any]] = (),
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Record a replay bundle by driving a live endpoint through the client API.

    ``commands`` is an ordered list of ``{"capability_id": ..., "input": {...}}``
    mappings; a snapshot is taken after every command (and before the first), so
    each recorded revision has its exact state document.
    """

    from mhs import canonical

    devices = client.devices()
    if not devices:
        raise RuntimeError("endpoint exposes no devices")
    manifest = devices[0] if device_id is None else next(
        (item for item in devices if item.get("device_id") == device_id), devices[0]
    )
    device_id = manifest["device_id"]
    resources = manifest.get("resources") or []
    primary = str(resources[0]["resource_id"]) if resources else "state"

    frames: list[dict[str, Any]] = []

    def record(command_id: Any = None, capability_id: Any = None) -> None:
        snapshot = client.snapshot(device_id=device_id)
        state = None
        if isinstance(snapshot, Mapping):
            state = snapshot.get("state")
            if not isinstance(state, Mapping):
                state = snapshot.get("snapshot")
        if not isinstance(state, Mapping):
            state = {}
        frames.append(
            {
                "revision": int(snapshot.get("revision", len(frames))),
                "state": copy.deepcopy(dict(state)),
                "state_hash": snapshot.get("state_hash"),
                "command_id": command_id,
                "capability_id": capability_id,
            }
        )

    session = client.open_session(device_ids=[device_id], capabilities=None, mode=None, ttl_s=600)
    session_id = session["session_id"] if isinstance(session, Mapping) else session
    record()
    try:
        for command in commands:
            receipt = client.invoke(
                command["capability_id"],
                input=command.get("input"),
                device_id=device_id,
                session_id=session_id,
            )
            record(receipt.get("command_id"), command["capability_id"])
    finally:
        closer = getattr(client, "close_session", None)
        if callable(closer):
            try:
                closer(session_id)
            except Exception:  # noqa: BLE001 - keep the recording even if close fails
                pass
    evidence = client.export_evidence()
    receipts = list(evidence.get("receipts") or []) if isinstance(evidence, Mapping) else []
    bundle: dict[str, Any] = {
        "kind": BUNDLE_KIND,
        "bundle_version": BUNDLE_VERSION,
        "recorded_at": canonical.now_rfc3339(),
        "source_endpoint": evidence.get("endpoint_id") if isinstance(evidence, Mapping) else None,
        "device": copy.deepcopy(dict(manifest)),
        "primary_resource": primary,
        "frames": frames,
        "receipts": receipts,
        "head_digest": evidence.get("head_digest") if isinstance(evidence, Mapping) else None,
        # FID-003/FID-028: keep the complete source evidence chain (including
        # genesis).  The replay endpoint serves and verifies this chain; it is
        # never re-signed as a new execution.
        "source_evidence": copy.deepcopy(dict(evidence)) if isinstance(evidence, Mapping) else None,
    }
    if not isinstance(bundle.get("source_evidence"), Mapping):
        raise RuntimeError("source endpoint produced no evidence bundle to record")
    bundle["bundle_digest"] = canonical.digest(bundle)
    if path is not None:
        write_bundle(path, bundle)
    return bundle


def _recording_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["kind", "read_only", "revisions"],
        "properties": {
            "kind": {"type": "string"},
            "read_only": {"type": "boolean"},
            "source_endpoint": {"type": "string"},
            "recorded_at": {"type": "string"},
            "head_digest": {"type": "string"},
            "bundle_digest": {"type": "string"},
            "revisions": {"type": "array", "items": {"type": "integer"}},
            "receipt_count": {"type": "integer", "minimum": 0},
            "frames": {"type": "array", "items": {"type": "object"}},
        },
    }


def _replay_manifest(endpoint_id: str, bundle: Mapping[str, Any], bridge: ReplayBridge) -> dict[str, Any]:
    original = dict(bundle["device"])
    source_slug = str(original.get("device_id", "recorded-device")).rsplit("/", 2)
    suffix = "/".join(source_slug[-2:]) if len(source_slug) >= 2 else "recorded-device"
    resources = []
    for item in original.get("resources") or []:
        entry = copy.deepcopy(dict(item))
        # Every resource follows the selected frame, including non-primary
        # resources. A static state would override ReplayBridge.read().
        entry.pop("state", None)
        entry["revision"] = bridge.current_revision
        resources.append(entry)
    recording = resource(
        RECORDING_RESOURCE,
        "evidence.replay",
        "Recorded evidence bundle",
        _recording_schema(),
        {},
        sampling={"mode": "on_change"},
    )
    recording.pop("state")
    resources.append(recording)
    capabilities = copy.deepcopy(list(original.get("capabilities") or []))
    safety = copy.deepcopy(dict(original.get("safety") or {}))
    safety["interlocks"] = []
    safety["estop"] = {"kind": "software", "latching": False, "latency_ms": 0, "reset": "mhs.safety.reset"}
    safety["safe_state"] = {
        "description": "Replay endpoints have no actuators; there is no safe-state transition to perform",
        "achieved_by": [],
    }
    fidelity = copy.deepcopy(dict(original.get("fidelity") or {}))
    fidelity["reset"] = "none"
    fidelity["snapshot_restore"] = True
    gaps = list(fidelity.get("gaps") or [])
    gaps.append("Replay is read-only: state can be selected by recorded revision but never mutated")
    fidelity["gaps"] = gaps
    manifest = device(
        endpoint_id=endpoint_id,
        slug=REPLAY_SLUG,
        display_name=str(original.get("display_name", "Recorded device")) + " (replay)",
        instance_id=INSTANCE_IDS["replay"],
        mode="replay",
        model=str(original.get("model", "recorded")) + "-replay",
        resources=resources,
        capabilities=capabilities,
        safety=safety,
        fidelity=fidelity,
        profile={
            "title": "Replayed " + str(original.get("model", "device")),
            "summary": "Read-only replay of a recorded MHS session: reads, snapshots and revision selection are available; commands and mhs.restore are refused with MHS.MODE.READ_ONLY.",
            "tags": ["replay", "recorded evidence", "read-only", "deterministic"],
            "operating_notes": [
                "Every mhs.command returns MHS.MODE.READ_ONLY; this endpoint cannot actuate anything.",
                "mhs.resource.read with filter.revision selects that revision's recorded state.",
                "The 'recording' resource exposes the recorded receipt list and head digest.",
            ],
        },
        conformance_level="CL4",
        endpoint_name="replay",
        provenance_sources=["MHS/sdk/src/mhs/reference/replay.py"],
    )
    manifest["models"] = [str(original.get("device_id"))]
    return manifest


def build(endpoint_id: str, *, bundle_path: str | Path) -> EndpointSpec:
    """Build the read-only replay endpoint from a recording bundle file."""

    bundle = load_bundle(bundle_path)
    frames = list(bundle["frames"])
    primary = bundle.get("primary_resource")
    if not primary:
        first_state = frames[0].get("state") or {}
        primary = next(iter(first_state), "state") if isinstance(first_state, Mapping) else "state"
    bridge = ReplayBridge(
        frames=frames,
        receipts=list(bundle.get("receipts") or []),
        head_digest=bundle.get("head_digest"),
        source_endpoint=bundle.get("source_endpoint"),
        bundle_digest=bundle.get("bundle_digest"),
        recorded_at=bundle.get("recorded_at"),
        source_bundle=bundle.get("source_evidence"),
        primary_resource=primary,
        capabilities=list((bundle.get("device") or {}).get("capabilities") or []),
    )
    manifest = _replay_manifest(endpoint_id, bundle, bridge)
    return EndpointSpec(
        name="replay",
        endpoint_id=endpoint_id,
        profile="MHS-Sim",
        devices=[manifest],
        bridges={manifest["device_id"]: bridge},
        features=[
            "MHS.SAFETY.NOT_CERTIFIED",
            "replay",
            "read-only",
            "state-replay-by-revision",
            "mcp-projection-v1",
        ],
        notes="Read-only replay of a recorded evidence bundle; commands return MHS.MODE.READ_ONLY.",
        conformance_level="CL4",
    )
