"""Shared helpers for round-2 fidelity/evidence regression tests.

These helpers deliberately rebuild the *documented* rules (state hashing,
bundle digesting) instead of importing private helpers from the implementation,
so the tests act as an independent oracle rather than mirroring the code under
test.
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from mhs import canonical
from mhs.errors import MHSError

#: /repo/MHS/sdk/tests/remediation/round2/fidelity/support.py -> /repo
REPO = Path(__file__).resolve().parents[6]
SHIPPED_BUNDLE = REPO / "MHS/sdk/docs/reports/replay-bundle-conveyor.json"
SNAPSHOT_SCHEMA = "snapshot.schema.json"
BUNDLE_KIND = "mhs.reference.replay-bundle"


class RpcError(RuntimeError):
    """A JSON-RPC error returned by the in-process server."""

    def __init__(self, error: Mapping[str, Any]):
        self.error = dict(error)
        super().__init__(f"{self.error.get('code')}: {self.error.get('message')}")


def rpc(server: Any, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Call one JSON-RPC method on an in-process ``MHSServer``.

    This is the same dispatch entry point used by ``server.handle``; it returns
    the ``result`` object or raises :class:`RpcError` with the structured error.
    """

    payload = dict(params or {})
    payload.setdefault("deadline_ms", 5000)
    response = server.handle(
        {"jsonrpc": "2.0", "id": canonical.ulid(), "method": method, "params": payload}
    )
    if hasattr(response, "to_dict"):  # pragma: no cover - older response objects
        response = response.to_dict()
    if not isinstance(response, Mapping):
        raise AssertionError(f"{method} returned no JSON-RPC response")
    if "error" in response:
        raise RpcError(response["error"])
    return dict(response.get("result") or {})


def hello_and_session(server: Any, device_id: str, mode: str) -> str:
    """Send ``hello`` and open a session; return the session id."""

    rpc(server, "mhs.hello", {"protocol_versions": ["1.0"]})
    opened = rpc(
        server,
        "mhs.session.open",
        {"device_ids": [device_id], "mode": mode},
    )
    return str(opened["session_id"])


def read_state(server: Any, session_id: str, device_id: str, resource_id: str) -> dict[str, Any]:
    return rpc(
        server,
        "mhs.resource.read",
        {"session_id": session_id, "device_id": device_id, "resource_id": resource_id},
    )


def snapshot(server: Any, session_id: str, device_id: str) -> dict[str, Any]:
    return rpc(server, "mhs.snapshot", {"session_id": session_id, "device_id": device_id})


def restore(server: Any, session_id: str, device_id: str, snapshot_doc: Mapping[str, Any],
            **extra: Any) -> dict[str, Any]:
    params = {"session_id": session_id, "device_id": device_id, "snapshot": dict(snapshot_doc)}
    params.update(extra)
    return rpc(server, "mhs.restore", params)


def resource_state_hash(bundle: Mapping[str, Any], frame: Mapping[str, Any]) -> str:
    """Recompute a recorded frame hash per the documented single-resource rule."""

    primary = bundle.get("primary_resource")
    if not primary:
        primary = next(iter(frame["state"]))
    exclusions = []
    for resource in (bundle.get("device") or {}).get("resources") or []:
        if resource.get("resource_id") == primary:
            exclusions = list(resource.get("hash_exclusions") or [])
    return canonical.state_hash(frame["state"][primary], exclusions)


def rehash_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute the outer bundle digest after a deliberate mutation."""

    document = copy.deepcopy(dict(bundle))
    document["bundle_digest"] = canonical.digest(
        {key: value for key, value in document.items() if key != "bundle_digest"}
    )
    return document


def write_json(path: Path, document: Mapping[str, Any]) -> Path:
    path.write_text(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def load_shipped_bundle() -> dict[str, Any]:
    return json.loads(SHIPPED_BUNDLE.read_text(encoding="utf-8"))


class TempDir:
    """Context manager for a temp directory in the system default temp dir.

    Tests never write inside the repository (in particular not into the
    private ``remediation-round2/`` audit directory).
    """

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mhs-fidelity-")

    @property
    def path(self) -> Path:
        return Path(self._tmp.name)

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *exc: object) -> None:
        self._tmp.cleanup()


def expect_chain_invalid(testcase: Any, path: Path, *, contains: str | None = None) -> MHSError:
    """Load a bundle and assert it is rejected before endpoint construction."""

    from mhs.reference.replay import build as build_replay

    with testcase.assertRaises(MHSError) as ctx:
        build_replay("mhs://replay-test.local:7400", bundle_path=path)
    error = ctx.exception
    testcase.assertEqual(
        error.code,
        "MHS.EVIDENCE.CHAIN_BROKEN",
        f"unexpected rejection code {error.code}: {error}",
    )
    if contains:
        testcase.assertIn(contains, str(error), f"rejection message was {error}")
    return error


def build_synthetic_bundle(
    tmp_path: Path,
    *,
    device_id: str,
    state_docs: Iterable[Mapping[str, Any]],
    frame_specs: Iterable[Mapping[str, Any]],
    receipt_specs: Iterable[Mapping[str, Any]],
    endpoint_id: str = "mhs://fid.local:7400",
) -> dict[str, Any]:
    """Build a chain-valid recording bundle from explicit frames and receipts.

    ``state_docs`` are primary-resource state documents.  ``frame_specs`` name a
    ``revision``, a ``state_index`` and optionally ``command_id``/``capability_id``
    (omitted means the initial baseline frame).  ``receipt_specs`` name
    ``command_id``, ``state_revision_before``/``state_revision_after``, the
    ``state_index`` whose hash becomes ``state_hash_after``, and optionally
    ``capability_id``/``status``.  Receipts are appended to a real
    :class:`EvidenceLog`, so the source chain verifies.
    """

    from mhs.evidence import EvidenceLog

    resource_id = "workcell"
    states = [copy.deepcopy(dict(state)) for state in state_docs]
    hashes = [canonical.state_hash(state, []) for state in states]
    receipts = [dict(spec) for spec in receipt_specs]
    frames = [dict(spec) for spec in frame_specs]

    log = EvidenceLog(endpoint_id, path=tmp_path / "synthetic-source.jsonl", fsync=False)
    for spec in receipts:
        state_index = int(spec["state_index"])
        record = {
            "receipt_id": canonical.ulid(),
            "command_id": spec["command_id"],
            "session_id": "mhs_s_0123456789abcdefghijklmn",
            "endpoint_id": endpoint_id,
            "device_id": device_id,
            "capability_id": spec.get("capability_id", "cap.world.step.v1"),
            "resource_ids": [resource_id],
            "input_digest": canonical.digest({"ticks": state_index}),
            "status": spec.get("status", "completed"),
            "mode": "simulated",
            "accepted_at": canonical.now_rfc3339(),
            "state_revision_before": int(spec["state_revision_before"]),
            "state_revision_after": int(spec["state_revision_after"]),
            "state_hash_after": hashes[state_index],
        }
        log.append_receipt(record)
    source = log.export()
    log.close()

    recorded_frames = []
    for spec in frames:
        state_index = int(spec["state_index"])
        recorded_frames.append(
            {
                "revision": int(spec["revision"]),
                "state": {resource_id: states[state_index]},
                "state_hash": hashes[state_index],
                "command_id": spec.get("command_id"),
                "capability_id": spec.get("capability_id"),
            }
        )
    device_manifest = {
        "device_id": device_id,
        "capabilities": [],
        "resources": [{"resource_id": resource_id, "kind": "world.sim",
                       "hash_exclusions": []}],
    }
    bundle = {
        "kind": BUNDLE_KIND,
        "bundle_version": "1.0",
        "recorded_at": canonical.now_rfc3339(),
        "source_endpoint": endpoint_id,
        "device": device_manifest,
        "primary_resource": resource_id,
        "frames": recorded_frames,
        "receipts": source["receipts"],
        "head_digest": source["head_digest"],
        "source_evidence": source,
    }
    return rehash_bundle(bundle)
