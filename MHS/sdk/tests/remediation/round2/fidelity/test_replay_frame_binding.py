"""LEAD-FID-003: every replay frame must be bound to its source receipt.

The loader used to verify the source chain and each frame's internal hash but
never compared a frame with the receipt named by its command_id.  A recording
whose final tick was edited (and whose frame/outer digests were recomputed)
therefore loaded and served a state that contradicted the untouched source
receipt.  These tests keep the original positive recording working and add the
wrong command/device/revision/hash/missing/ambiguous cases.
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from mhs import canonical, connect
from mhs.reference import build_endpoint, build_server
from mhs.reference.replay import (
    build as build_replay,
    build_replay_bundle,
    load_bundle,
)

from . import support
from .support import (
    SHIPPED_BUNDLE,
    TempDir,
    expect_chain_invalid,
    load_shipped_bundle,
    rehash_bundle,
    resource_state_hash,
    write_json,
)

RESOURCE_ID = "workcell"


class ReplayPositiveControlTests(unittest.TestCase):
    """The legitimately recorded bundle keeps loading, replaying and verifying."""

    def test_shipped_recording_still_loads_replays_and_verifies(self):
        bundle = load_shipped_bundle()
        spec = build_replay("mhs://replay-binding.local:7400", bundle_path=SHIPPED_BUNDLE)
        server = build_server(spec, log_ready=False)
        try:
            device_id = spec.devices[0]["device_id"]
            session_id = support.hello_and_session(server, device_id, "replay")
            for frame in bundle["frames"]:
                read = support.rpc(
                    server,
                    "mhs.resource.read",
                    {
                        "session_id": session_id,
                        "device_id": device_id,
                        "resource_id": RESOURCE_ID,
                        "filter": {"revision": frame["revision"]},
                    },
                )
                self.assertEqual(read["revision"], frame["revision"])
                self.assertEqual(read["state"], frame["state"][RESOURCE_ID])
                self.assertEqual(read["state_hash"], frame["state_hash"])
            verification = support.rpc(
                server,
                "mhs.evidence.verify",
                {"session_id": session_id, "device_id": device_id},
            )
            self.assertTrue(verification["valid"], verification["errors"])
            self.assertEqual(verification["checked"], len(bundle["source_evidence"]["receipts"]))
            exported = support.rpc(
                server,
                "mhs.evidence.export",
                {"session_id": session_id, "device_id": device_id},
            )
            self.assertEqual(exported, bundle["source_evidence"])
            self.assertEqual(exported["head_digest"], bundle["source_evidence"]["head_digest"])
        finally:
            spec.close()

    def test_fresh_recording_binds_both_commands(self):
        spec = build_endpoint("conveyor", endpoint_id="mhs://fid-source.local:7400",
                              test_profile=True)
        server = build_server(spec, log_ready=False)
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        try:
            bundle = build_replay_bundle(
                client,
                commands=[
                    {"capability_id": "cap.world.step.v1", "input": {"ticks": 5}},
                    {"capability_id": "cap.world.step.v1", "input": {"ticks": 3}},
                ],
            )
            self.assertEqual([frame["revision"] for frame in bundle["frames"]], [0, 1, 2])
            with TempDir() as tmp:
                path = write_json(Path(tmp) / "fresh.json", bundle)
                loaded = load_bundle(path)
                self.assertEqual(loaded["bundle_digest"], bundle["bundle_digest"])
                replay_spec = build_replay("mhs://replay-fresh.local:7400", bundle_path=path)
                replay_server = build_server(replay_spec, log_ready=False)
                try:
                    device_id = replay_spec.devices[0]["device_id"]
                    session_id = support.hello_and_session(replay_server, device_id, "replay")
                    for frame in bundle["frames"]:
                        read = support.rpc(
                            replay_server,
                            "mhs.resource.read",
                            {
                                "session_id": session_id,
                                "device_id": device_id,
                                "resource_id": RESOURCE_ID,
                                "filter": {"revision": frame["revision"]},
                            },
                        )
                        self.assertEqual(read["state_hash"], frame["state_hash"])
                finally:
                    replay_spec.close()
        finally:
            client.close()
            handle.shutdown()
            spec.close()

    def test_genesis_only_recording_still_loads(self):
        spec = build_endpoint("conveyor", endpoint_id="mhs://fid-source.local:7400",
                              test_profile=True)
        server = build_server(spec, log_ready=False)
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        try:
            bundle = build_replay_bundle(client, commands=[])
            self.assertEqual(len(bundle["frames"]), 1)
            with TempDir() as tmp:
                path = write_json(Path(tmp) / "genesis-only.json", bundle)
                loaded = load_bundle(path)
                self.assertEqual(len(loaded["frames"]), 1)
        finally:
            client.close()
            handle.shutdown()
            spec.close()


class ReplayFrameBindingNegativeTests(unittest.TestCase):
    """A recording must not contradict the source receipts it claims."""

    def setUp(self):
        self._tmp = TempDir()
        self.tmp = self._tmp.__enter__()
        self.bundle = load_shipped_bundle()

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def _write(self, name: str, document: dict) -> Path:
        return write_json(self.tmp / name, document)

    def test_rehashed_frame_with_contradictory_source_receipt_is_rejected(self):
        """The exact review counterexample: frame and outer hash recomputed."""

        tampered = copy.deepcopy(self.bundle)
        frame = tampered["frames"][-1]
        frame["state"][RESOURCE_ID]["tick"] = 777777
        frame["state_hash"] = resource_state_hash(tampered, frame)
        tampered = rehash_bundle(tampered)
        # The source evidence is untouched and still verifies on its own.
        self.assertEqual(tampered["source_evidence"], self.bundle["source_evidence"])
        receipt = next(
            item for item in tampered["source_evidence"]["receipts"]
            if item.get("command_id") == frame["command_id"]
        )
        self.assertNotEqual(frame["state_hash"], receipt["state_hash_after"])
        path = self._write("rehashed.json", tampered)
        expect_chain_invalid(self, path, contains="state_hash contradicts its source receipt")

    def test_wrong_command_id_is_rejected(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["frames"][-1]["command_id"] = canonical.ulid()
        path = self._write("wrong-command.json", rehash_bundle(tampered))
        expect_chain_invalid(self, path, contains="no completed source receipt")

    def test_wrong_device_is_rejected(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["device"]["device_id"] = "mhs://localhost:7410/lab/other-workcell"
        path = self._write("wrong-device.json", rehash_bundle(tampered))
        expect_chain_invalid(self, path, contains="no source receipt for this device")

    def test_wrong_revision_is_rejected(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["frames"][-1]["revision"] = 2
        path = self._write("wrong-revision.json", rehash_bundle(tampered))
        expect_chain_invalid(self, path, contains="revision does not match its source receipt")

    def test_wrong_capability_is_rejected(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["frames"][-1]["capability_id"] = "cap.world.home.v1"
        path = self._write("wrong-capability.json", rehash_bundle(tampered))
        expect_chain_invalid(self, path, contains="capability does not match its source receipt")

    def test_initial_frame_must_not_claim_a_capability(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["frames"][0]["capability_id"] = "cap.world.snapshot.v1"
        path = self._write("initial-capability.json", rehash_bundle(tampered))
        expect_chain_invalid(self, path, contains="baseline observation")

    def test_initial_frame_revision_must_match_source_baseline(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["frames"][0]["revision"] = 4
        tampered["frames"][-1]["revision"] = 5
        path = self._write("initial-revision.json", rehash_bundle(tampered))
        expect_chain_invalid(self, path, contains="initial frame revision")

    def test_recorded_receipts_must_match_source_evidence(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["receipts"] = []
        path = self._write("receipt-copy.json", rehash_bundle(tampered))
        expect_chain_invalid(self, path, contains="recorded receipts disagree")

    def test_ambiguous_command_mapping_is_rejected(self):
        command_id = canonical.ulid()
        document = support.build_synthetic_bundle(
            self.tmp,
            device_id="mhs://fid.local:7400/recorded-workcell",
            state_docs=[{"tick": 0}, {"tick": 1}, {"tick": 2}],
            receipt_specs=[
                {"command_id": command_id, "state_revision_before": 0,
                 "state_revision_after": 1, "state_index": 1},
                # Same command id recorded twice: the frame cannot pick one.
                {"command_id": command_id, "state_revision_before": 0,
                 "state_revision_after": 1, "state_index": 2},
            ],
            frame_specs=[
                {"revision": 0, "state_index": 0},
                {"revision": 1, "state_index": 1, "command_id": command_id,
                 "capability_id": "cap.world.step.v1"},
            ],
        )
        path = self._write("ambiguous.json", document)
        expect_chain_invalid(self, path, contains="ambiguous")

    def test_duplicate_command_across_frames_is_rejected(self):
        first = canonical.ulid()
        second = canonical.ulid()
        document = support.build_synthetic_bundle(
            self.tmp,
            device_id="mhs://fid.local:7400/recorded-workcell",
            state_docs=[{"tick": 0}, {"tick": 1}, {"tick": 2}],
            receipt_specs=[
                {"command_id": first, "state_revision_before": 0,
                 "state_revision_after": 1, "state_index": 1},
                {"command_id": second, "state_revision_before": 1,
                 "state_revision_after": 2, "state_index": 2},
            ],
            frame_specs=[
                {"revision": 0, "state_index": 0},
                {"revision": 1, "state_index": 1, "command_id": first,
                 "capability_id": "cap.world.step.v1"},
                # Second frame reuses the first frame's command id.
                {"revision": 2, "state_index": 2, "command_id": first,
                 "capability_id": "cap.world.step.v1"},
            ],
        )
        path = self._write("duplicate-command.json", document)
        expect_chain_invalid(self, path, contains="more than one recorded frame")

    def test_control_cases_are_still_accepted(self):
        """Sanity: an unmodified copy with a recomputed digest is accepted."""

        path = self._write("control.json", rehash_bundle(self.bundle))
        loaded = load_bundle(path)
        self.assertEqual(loaded["bundle_digest"], self.bundle["bundle_digest"])


if __name__ == "__main__":
    unittest.main()
