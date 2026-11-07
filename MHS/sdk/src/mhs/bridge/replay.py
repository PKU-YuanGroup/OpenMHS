"""Read-only replay bridge (MHS-000 sections 7.1 and 9.3).

``ReplayBridge`` serves a recorded endpoint state history.  Every mutation is
refused with ``MHS.MODE.READ_ONLY``. Reads and snapshots work; the public server
selects revisions with ``mhs.resource.read filter.revision``. The internal
:meth:`restore` method can select a recorded frame, but public ``mhs.restore``
is rejected as read-only.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping, Sequence

from mhs.bridge.base import Bridge, make_mhs_error, unsupported
from mhs.bridge.base import main as _bridge_main

__all__ = ["ReplayBridge", "main"]

RECORDING_RESOURCE = "recording"


class ReplayBridge(Bridge):
    """Serve a recorded state history read-only."""

    bridge_kind = "replay"

    def __init__(
        self,
        *,
        device_id: str | None = None,
        frames: Sequence[Mapping[str, Any]] = (),
        receipts: Sequence[Mapping[str, Any]] = (),
        head_digest: str | None = None,
        source_endpoint: str | None = None,
        bundle_digest: str | None = None,
        recorded_at: str | None = None,
        source_bundle: Mapping[str, Any] | None = None,
        primary_resource: str | None = None,
        capabilities: Iterable[Mapping[str, Any]] = (),
    ):
        super().__init__(device_id=device_id)
        self._frames: list[dict[str, Any]] = []
        for raw in frames:
            frame = copy.deepcopy({str(key): value for key, value in dict(raw).items()})
            if "state" not in frame or not isinstance(frame["state"], Mapping):
                raise make_mhs_error(
                    "MHS.EVIDENCE.CHAIN_INVALID",
                    "recorded frame is missing its state document",
                    {"retryable": False},
                )
            if RECORDING_RESOURCE in frame["state"]:
                raise make_mhs_error(
                    "MHS.PROTOCOL.UNSUPPORTED_FEATURE",
                    "source resource 'recording' conflicts with the replay evidence resource",
                    {"retryable": False, "details": {"resource_id": RECORDING_RESOURCE}},
                )
            self._frames.append(frame)
        if not self._frames:
            raise make_mhs_error(
                "MHS.EVIDENCE.NOT_FOUND",
                "replay bundle contains no recorded frames",
                {"retryable": False},
            )
        self._frames.sort(key=lambda item: int(item.get("revision", 0)))
        self._by_revision = {int(frame.get("revision", 0)): frame for frame in self._frames}
        self._receipts = [copy.deepcopy(dict(item)) for item in receipts]
        self._head_digest = head_digest
        self._source_endpoint = source_endpoint
        self._bundle_digest = bundle_digest
        self._recorded_at = recorded_at
        #: The immutable source evidence bundle this recording replays
        #: (FID-028: replay evidence is a copy of the recording's chain).
        self.source_bundle = copy.deepcopy(dict(source_bundle)) if isinstance(source_bundle, Mapping) else None
        self._capabilities = [copy.deepcopy(dict(item)) for item in capabilities]
        self._primary_resource = primary_resource or _first_resource(self._frames[0]["state"])
        self.position = len(self._frames) - 1

    # -- adapter surface ---------------------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._capabilities)

    def resources(self) -> list[dict[str, Any]]:
        return [
            {"resource_id": self._primary_resource, "kind": "world.sim"},
            {"resource_id": RECORDING_RESOURCE, "kind": "evidence.replay"},
        ]

    @property
    def current_frame(self) -> dict[str, Any]:
        return self._frames[self.position]

    @property
    def current_revision(self) -> int:
        return int(self.current_frame.get("revision", 0))

    @property
    def revisions(self) -> list[int]:
        return [int(frame.get("revision", 0)) for frame in self._frames]

    # -- read-only state ---------------------------------------------------
    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        if resource_id == RECORDING_RESOURCE:
            recording = self._recording_document()
            if fields:
                return {name: recording.get(name) for name in fields if name in recording}
            return recording
        if resource_id not in self.current_frame["state"]:
            raise unsupported(resource_id, kind="resource")
        state = copy.deepcopy(dict(self.current_frame["state"][resource_id]))
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        self.ensure_open()
        # The replay endpoint declares its evidence view as a resource too.
        # Include that view without altering the recorded source frame or its
        # receipt-bound hash: the endpoint snapshot has a different scope.
        state = copy.deepcopy(dict(self.current_frame["state"]))
        state[RECORDING_RESOURCE] = self._recording_document()
        return state

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self.ensure_open()
        target = _select_frame(snapshot, self._frames, self._by_revision)
        self.position = self._frames.index(target)
        return copy.deepcopy(dict(target["state"]))

    def frame_at(self, revision: int) -> dict[str, Any]:
        """Return the recorded frame for ``revision`` or raise a coded error."""
        frame = self._by_revision.get(int(revision))
        if frame is None:
            raise make_mhs_error(
                "MHS.RESOURCE.UNKNOWN",
                f"revision {revision} is not present in the recorded bundle",
                {"retryable": False, "details": {"recorded_revisions": self.revisions}},
            )
        return copy.deepcopy(dict(frame))

    def seek(self, revision: int) -> dict[str, Any]:
        """Select a recorded revision by number (used by the replay endpoint)."""

        self.ensure_open()
        frame = self._by_revision.get(int(revision))
        if frame is None:
            raise make_mhs_error(
                "MHS.CONFLICT.SNAPSHOT",
                f"revision {revision} is not present in the recorded bundle",
                {"retryable": False, "details": {"recorded_revisions": self.revisions}},
            )
        self.position = self._frames.index(frame)
        return {"revision": revision, "state_hash": frame.get("state_hash")}

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        raise make_mhs_error(
            "MHS.MODE.READ_ONLY",
            "replay endpoints are read-only; reads, snapshots and revision selection are available",
            {
                "retryable": False,
                "details": {"capability_id": capability_id, "mode": "replay"},
                "remediation": "Use mhs.resource.read with filter.revision or mhs.snapshot on a replay endpoint.",
            },
        )

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        raise make_mhs_error(
            "MHS.MODE.READ_ONLY",
            "replay endpoints are read-only",
            {"retryable": False, "details": {"resource_id": resource_id, "mode": "replay"}},
        )

    def safety_status(self) -> dict[str, Any]:
        return {
            "risk_class": "R0",
            "estop": {"engaged": False, "latching": False},
            "interlocks": [],
            "permits": [],
            "safe_state": {"description": "replay has no actuators", "achieved": True},
        }

    def describe(self) -> dict[str, Any]:
        described = super().describe()
        described.update(
            {
                "recorded_revisions": self.revisions,
                "position": self.position,
                "source_endpoint": self._source_endpoint,
                "receipt_count": len(self._receipts),
                "head_digest": self._head_digest,
            }
        )
        return described

    # -- internals ---------------------------------------------------------
    def _recording_document(self) -> dict[str, Any]:
        document = {
            "kind": "mhs.reference.replay-recording",
            "read_only": True,
            "source_endpoint": self._source_endpoint,
            "head_digest": self._head_digest,
            "bundle_digest": self._bundle_digest,
            "recorded_at": self._recorded_at,
            "receipt_count": len(self._receipts),
            "current_revision": self.current_revision,
            "revisions": self.revisions,
            "frames": [
                {
                    "revision": int(frame.get("revision", 0)),
                    "state_hash": frame.get("state_hash"),
                    "command_id": frame.get("command_id"),
                }
                for frame in self._frames
            ],
            "receipts": copy.deepcopy(self._receipts),
        }
        # Optional string metadata is absent when unknown, not a fabricated
        # string or a null value outside the served resource schema.
        return {key: value for key, value in document.items() if value is not None}


def _first_resource(state: Any) -> str:
    if isinstance(state, Mapping) and state:
        return str(next(iter(state)))
    return "state"


def _select_frame(
    snapshot: Any,
    frames: Sequence[Mapping[str, Any]],
    by_revision: Mapping[int, Mapping[str, Any]],
) -> Mapping[str, Any]:
    if isinstance(snapshot, Mapping):
        revision = snapshot.get("revision")
        if isinstance(revision, int) and revision in by_revision:
            return by_revision[revision]
        state_hash = snapshot.get("state_hash")
        if isinstance(state_hash, str):
            for frame in frames:
                if frame.get("state_hash") == state_hash:
                    return frame
        state = snapshot.get("state")
        if isinstance(state, Mapping):
            if "state" in state and isinstance(state["state"], Mapping):
                state = state["state"]
            for frame in frames:
                if frame.get("state") == state:
                    return frame
            # Accept an unrecorded state document: replay it as-is by appending a frame.
            frames_list = frames  # read-only view; caller owns mutation
            raise make_mhs_error(
                "MHS.CONFLICT.SNAPSHOT",
                "snapshot state is not present in the recorded bundle",
                {"retryable": False},
            )
        if isinstance(state, Mapping) and revision is None:
            return by_revision[next(iter(by_revision))]
    raise make_mhs_error(
        "MHS.CONFLICT.SNAPSHOT",
        "restore on a replay endpoint needs a recorded revision, state_hash or state",
        {"retryable": False, "details": {"recorded_revisions": sorted(by_revision)}},
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
