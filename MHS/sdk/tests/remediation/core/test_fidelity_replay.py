"""Regression tests for FID-001..004 and SPEC-002/003."""

from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from mhs import canonical, connect
from mhs.errors import MHSError
from mhs.reference import build_endpoint, build_server
from mhs.reference.replay import build as build_replay, build_replay_bundle
from mhs.schema import SchemaStore

REPO = Path(__file__).resolve().parents[5]
STORE = SchemaStore()


def _hybrid_manifest(authority):
    from mhs.reference import build_endpoint

    spec = build_endpoint("conveyor", endpoint_id="mhs://fid.local:7400", test_profile=False)
    manifest = spec.devices[0]
    spec.close()
    manifest = copy.deepcopy(manifest)
    manifest["mode"] = "hybrid"
    if authority is not _MISSING:
        manifest["fidelity"]["authority"] = authority
    return manifest


class _Missing:
    pass


_MISSING = _Missing()


class HybridAuthorityTests(unittest.TestCase):
    """FID-001: authority is an object covering exactly the resources."""

    def test_hybrid_authority_object_validates(self):
        manifest = _hybrid_manifest({"workcell": "hardware"})
        self.assertEqual(STORE.validate(manifest, "device.schema.json"), [])

    def test_string_or_missing_authority_fails_schema(self):
        for authority in ("hardware", _MISSING):
            manifest = _hybrid_manifest(authority)
            errors = STORE.validate(manifest, "device.schema.json")
            self.assertTrue(errors, f"authority={authority!r} should fail validation")

    def test_server_rejects_authority_not_covering_resources(self):
        from mhs.server import Device, MHSServer, Resource

        device = Device(
            "mhs://fid.local:7400/arm",
            mode="hybrid",
            resources=[Resource("arm", "robot.arm", {"type": "object"})],
            capabilities=[],
            fidelity={"fidelity_level": "F0", "engine": "x",
                      "authority": {"wrong_resource": "hardware"}, "gaps": ["g"]},
        )
        with self.assertRaises(ValueError):
            MHSServer("mhs://fid.local:7400", [device], log_ready=False)


class ExperimentalBindingSchemaTests(unittest.TestCase):
    """SPEC-003: bindings of experimental classes are marked explicitly."""

    def test_x_mhs_experimental_is_a_boolean_field(self):
        spec = build_endpoint("conveyor", endpoint_id="mhs://spec.local:7400", test_profile=False)
        manifest = copy.deepcopy(spec.devices[0])
        spec.close()
        self.assertEqual(STORE.validate(manifest, "device.schema.json"), [])
        manifest["x-mhs-experimental"] = True
        self.assertEqual(STORE.validate(manifest, "device.schema.json"), [])
        manifest["x-mhs-experimental"] = "yes"
        self.assertTrue(STORE.validate(manifest, "device.schema.json"))


class CapabilityShapeTests(unittest.TestCase):
    """SPEC-002: one canonical flat capability class shape."""

    def test_all_62_classes_validate(self):
        catalogue = json.loads((REPO / "MHS/spec/capabilities.json").read_text())
        classes = catalogue.get("capabilities") or catalogue.get("classes") or catalogue
        if isinstance(classes, dict):
            classes = list(classes.values())
        self.assertEqual(len(classes), catalogue["capability_count"], "capability_count disagrees with the class list")
        for entry in classes:
            self.assertEqual(
                STORE.validate(entry, "capability.schema.json"), [],
                f"class {entry.get('capability_id')} does not validate",
            )

    def test_nested_semantics_is_not_part_of_the_contract(self):
        class_doc = {
            "capability_id": "cap.test.nested.v1",
            "title": "Nested", "verb": "invoke", "resource_kinds": ["world.sim"],
            "input_schema": {"type": "object"}, "output_schema": {"type": "object"},
            "summary": "A test class.",
            "tags": ["test", "nested", "invalid"],
            "semantics": {"summary": "old shape", "tags": ["a", "b", "c"]},
        }
        self.assertTrue(STORE.validate(class_doc, "capability.schema.json"))


class ReplayContractTests(unittest.TestCase):
    """FID-002/003: read-only seek, truthful revisions and recording integrity."""

    @classmethod
    def setUpClass(cls):
        cls.source_spec = build_endpoint(
            "conveyor", endpoint_id="mhs://replay-source.local:7400", test_profile=True
        )
        cls.source_server = build_server(cls.source_spec, log_ready=False)
        cls.source_handle = cls.source_server.start_http("127.0.0.1", 0)
        cls.source_client = connect(cls.source_handle.url)
        cls.bundle = build_replay_bundle(
            cls.source_client,
            commands=[{"capability_id": "cap.world.step.v1", "input": {"ticks": 5}}],
        )
        cls.tmp = tempfile.TemporaryDirectory()
        cls.bundle_path = Path(cls.tmp.name) / "bundle.json"
        cls.bundle_path.write_text(json.dumps(cls.bundle), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.source_client.close()
        cls.source_handle.shutdown()
        cls.source_spec.close()
        cls.tmp.cleanup()

    def _replay_client(self):
        spec = build_replay("mhs://replay.local:7400", bundle_path=self.bundle_path)
        server = build_server(spec, log_ready=False)
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        return spec, server, handle, client

    def test_seek_by_revision_and_read_only_restore(self):
        spec, server, handle, client = self._replay_client()
        try:
            hello = client.hello()
            self.assertIn("replay.seek", hello["features"])
            device = client.devices()[0]
            device_id = device["device_id"]
            resource_id = device["resources"][0]["resource_id"]
            session = client.open_session([device_id], capabilities=None,
                                          mode="replay", ttl_s=300)["session_id"]
            revisions = sorted({int(f["revision"]) for f in self.bundle["frames"]})
            for revision in revisions:
                frame = next(f for f in self.bundle["frames"] if int(f["revision"]) == revision)
                read = client.request("mhs.resource.read", {
                    "session_id": session, "device_id": device_id,
                    "resource_id": resource_id, "filter": {"revision": revision},
                    "deadline_ms": 5000,
                })
                self.assertEqual(read["revision"], revision)
                self.assertEqual(read["state"], frame["state"][resource_id])
                snapshot = client.snapshot(device_id)
                self.assertEqual(snapshot["revision"], revision)
                self.assertEqual(STORE.validate(snapshot, "snapshot.schema.json"), [])
                self.assertEqual(set(snapshot["state"]),
                                 {item["resource_id"] for item in device["resources"]})
                self.assertEqual(snapshot["state"][resource_id], frame["state"][resource_id])
                recording = client.request("mhs.resource.read", {
                    "session_id": session, "device_id": device_id,
                    "resource_id": "recording", "deadline_ms": 5000,
                })["state"]
                self.assertEqual(snapshot["state"]["recording"], recording)
                self.assertEqual(recording["current_revision"], revision)
                self.assertEqual(recording["head_digest"], self.bundle["head_digest"])
                self.assertEqual(recording["recorded_at"], self.bundle["recorded_at"])
                self.assertEqual(recording["receipt_count"], len(self.bundle["receipts"]))
                if self.bundle.get("source_endpoint") is None:
                    self.assertNotIn("source_endpoint", recording)
                self.assertEqual(snapshot["snapshot_digest"], canonical.digest(snapshot["state"]))
                exclusions = [f"/{item['resource_id']}{pointer}"
                              for item in device["resources"]
                              for pointer in item.get("hash_exclusions", [])]
                self.assertEqual(snapshot["state_hash"],
                                 canonical.state_hash(snapshot["state"], exclusions))
            with self.assertRaises(MHSError) as ctx:
                client.request("mhs.resource.read", {
                    "session_id": session, "device_id": device_id,
                    "resource_id": resource_id,
                    "filter": {"revision": max(revisions) + 99}, "deadline_ms": 5000,
                })
            self.assertEqual(ctx.exception.code, "MHS.RESOURCE.UNKNOWN")
            snapshot = client.snapshot(device_id)
            restored = client.restore(snapshot, device_id)
            self.assertEqual(restored["status"], "rejected")
            self.assertEqual(restored["error"]["mhs_code"], "MHS.MODE.READ_ONLY")
            exported = client.export_evidence()
            self.assertEqual(exported, self.bundle["source_evidence"])
            self.assertEqual(exported.get("head_digest"), self.bundle["source_evidence"]["head_digest"])
            self.assertTrue(client.verify_evidence(exported)["valid"])
        finally:
            client.close()
            handle.shutdown()
            spec.close()

    def test_snapshot_copy_does_not_mutate_recorded_frames_or_evidence(self):
        spec = build_replay("mhs://replay.local:7400", bundle_path=self.bundle_path)
        try:
            bridge = next(iter(spec.bridges.values()))
            frame_before = copy.deepcopy(bridge.current_frame)
            evidence_before = copy.deepcopy(bridge.source_bundle)
            snapshot = bridge.snapshot()
            snapshot["workcell"]["tick"] = -1
            snapshot["recording"]["receipts"][0]["status"] = "tampered"
            snapshot["recording"]["frames"].clear()
            snapshot["recording"]["receipts"].clear()
            self.assertEqual(bridge.current_frame, frame_before)
            self.assertEqual(bridge.source_bundle, evidence_before)
            fresh = bridge.snapshot()
            self.assertEqual(fresh["workcell"], frame_before["state"]["workcell"])
            self.assertEqual(fresh["recording"]["receipts"], self.bundle["receipts"])
            self.assertEqual(len(fresh["recording"]["frames"]), len(self.bundle["frames"]))
        finally:
            spec.close()

    def test_snapshot_recording_view_excludes_concurrent_seek(self):
        self._assert_cursor_exclusion("snapshot_recording_view")

    def test_snapshot_revision_excludes_concurrent_seek(self):
        self._assert_cursor_exclusion("snapshot_outer_revision")

    def test_selected_read_excludes_concurrent_seek(self):
        self._assert_cursor_exclusion("seek_read_revision")

    def _assert_cursor_exclusion(self, kind):
        spec, server, handle, first = self._replay_client()
        second = connect(handle.url)
        bridge = next(iter(spec.bridges.values()))
        frames = {frame["revision"]: frame for frame in self.bundle["frames"]}
        low, high = min(frames), max(frames)
        entered, release = threading.Event(), threading.Event()
        result = {}
        thread = None
        before = copy.deepcopy(bridge.source_bundle)
        try:
            device_id = first.devices()[0]["device_id"]
            sessions = [client.open_session([device_id], capabilities=None,
                                            mode="replay", ttl_s=300)["session_id"]
                        for client in (first, second)]

            def read(client, session, revision=None):
                params = {"session_id": session, "device_id": device_id,
                          "resource_id": "workcell", "deadline_ms": 5000}
                if revision is not None:
                    params["filter"] = {"revision": revision}
                return client.request("mhs.resource.read", params)

            read(first, sessions[0], low)

            def pause():
                entered.set()
                if not release.wait(5):
                    raise AssertionError("controlled replay barrier timed out")

            if kind == "snapshot_recording_view":
                original = bridge._recording_document

                def wrapped():
                    pause()
                    return original()

                bridge._recording_document = wrapped
            elif kind == "snapshot_outer_revision":
                original = bridge.snapshot

                def wrapped(*args, **kwargs):
                    state = original(*args, **kwargs)
                    pause()
                    return state

                bridge.snapshot = wrapped
            else:
                original = bridge.read
                first_read = [True]
                guard = threading.Lock()

                def wrapped(*args, **kwargs):
                    with guard:
                        should_pause = first_read[0]
                        first_read[0] = False
                    if should_pause:
                        pause()
                    return original(*args, **kwargs)

                bridge.read = wrapped

            def run_first():
                try:
                    result["value"] = (read(first, sessions[0], low)
                                       if kind == "seek_read_revision"
                                       else first.snapshot(device_id))
                except BaseException as exc:
                    result["error"] = exc

            thread = threading.Thread(target=run_first, daemon=True)
            thread.start()
            self.assertTrue(entered.wait(5), "first client did not reach the barrier")
            for action in (lambda: read(second, sessions[1], high),
                           lambda: read(second, sessions[1]),
                           lambda: second.snapshot(device_id)):
                with self.assertRaises(MHSError) as caught:
                    action()
                self.assertEqual(caught.exception.code, "MHS.DEVICE.BUSY")
                self.assertTrue(caught.exception.data["retryable"])
                self.assertEqual(bridge.current_revision, low)
            release.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertNotIn("error", result)
            value = result["value"]
            self.assertEqual(value["revision"], low)
            if kind == "seek_read_revision":
                self.assertEqual(value["state"], frames[low]["state"]["workcell"])
                self.assertEqual(value["state_hash"], frames[low]["state_hash"])
            else:
                self.assertEqual(value["state"]["workcell"], frames[low]["state"]["workcell"])
                self.assertEqual(value["state"]["recording"]["current_revision"], low)
            later = read(second, sessions[1], high)
            self.assertEqual(later["revision"], high)
            self.assertEqual(later["state"], frames[high]["state"]["workcell"])
            self.assertEqual(later["state_hash"], frames[high]["state_hash"])
            self.assertEqual(bridge.source_bundle, before)
        finally:
            release.set()
            if thread is not None:
                thread.join(5)
            first.close()
            second.close()
            handle.shutdown()
            spec.close()

    def test_reserved_resource_collision_is_rejected_without_overwriting_source(self):
        from mhs.bridge.replay import ReplayBridge

        frame = {"revision": 0, "state": {"recording": {"measurement": 42}}}
        before = copy.deepcopy(frame)
        with self.assertRaises(MHSError) as caught:
            ReplayBridge(frames=[frame])
        self.assertEqual(caught.exception.code, "MHS.PROTOCOL.UNSUPPORTED_FEATURE")
        self.assertEqual(frame, before)

    def test_multi_resource_recording_snapshot_keeps_all_source_resources(self):
        source = build_endpoint("lab", endpoint_id="mhs://multi-source.local:7400")
        source_server = build_server(source, log_ready=False)
        source_handle = source_server.start_http("127.0.0.1", 0)
        source_client = connect(source_handle.url)
        try:
            bundle = build_replay_bundle(source_client)
        finally:
            source_client.close()
            source_handle.shutdown()
            source.close()
        path = Path(self.tmp.name) / "multi-resource-bundle.json"
        path.write_text(json.dumps(bundle), encoding="utf-8")
        spec = build_replay("mhs://multi-replay.local:7400", bundle_path=path)
        server = build_server(spec, log_ready=False)
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        try:
            device = client.devices()[0]
            client.open_session([device["device_id"]], capabilities=None, mode="replay", ttl_s=300)
            snapshot = client.snapshot(device["device_id"])
            source_state = bundle["frames"][-1]["state"]
            self.assertEqual(set(source_state), {"pipette", "plate"})
            self.assertEqual(set(snapshot["state"]), {"pipette", "plate", "recording"})
            self.assertEqual({key: snapshot["state"][key] for key in source_state}, source_state)
            self.assertEqual(STORE.validate(snapshot, "snapshot.schema.json"), [])
            self.assertEqual(snapshot["state"]["recording"]["frames"][0]["state_hash"],
                             bundle["frames"][0]["state_hash"])
            self.assertEqual(client.export_evidence(), bundle["source_evidence"])
            self.assertTrue(client.verify_evidence()["valid"])
        finally:
            client.close()
            handle.shutdown()
            spec.close()

    def test_tampered_frame_is_rejected_at_load(self):
        tampered = copy.deepcopy(self.bundle)
        tampered["frames"][0]["state"]["workcell"]["tick"] = 777777
        path = Path(self.tmp.name) / "tampered.json"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaises(MHSError) as ctx:
            build_replay("mhs://replay.local:7400", bundle_path=path)
        self.assertIn(ctx.exception.code, (
            "MHS.EVIDENCE.CHAIN_BROKEN",
            "MHS.FIDELITY.REPLAY_DIVERGENCE",
        ))


class FidelityIdentityTests(unittest.TestCase):
    """FID-004: different fidelity configurations are distinct instances."""

    def test_arm_exact_and_noise_are_isolated(self):
        exact = build_endpoint("arm", endpoint_id="mhs://arm-exact.local:7400", noise=False)
        noise = build_endpoint("arm", endpoint_id="mhs://arm-noise.local:7400", noise=True)
        try:
            exact_manifest = exact.devices[0]
            noise_manifest = noise.devices[0]
            self.assertNotEqual(exact_manifest["instance_id"], noise_manifest["instance_id"])
            self.assertIn("conformance", exact_manifest)
            self.assertIn("conformance", noise_manifest)
            self.assertNotEqual(
                exact_manifest["conformance"]["report_digest"],
                noise_manifest["conformance"]["report_digest"],
                "each fidelity configuration must cite its own report",
            )
            exact_server = build_server(exact, log_ready=False)
            noise_server = build_server(noise, log_ready=False)
            exact_handle = exact_server.start_http("127.0.0.1", 0)
            noise_handle = noise_server.start_http("127.0.0.1", 0)
            exact_client = connect(exact_handle.url)
            noise_client = connect(noise_handle.url)
            try:
                noise_device = noise_client.devices()[0]["device_id"]
                noise_client.open_session([noise_device], capabilities=None,
                                          mode="simulated", ttl_s=300)
                noise_snapshot = noise_client.snapshot(noise_device)
                exact_device = exact_client.devices()[0]["device_id"]
                exact_client.open_session([exact_device], capabilities=None,
                                          mode="simulated", ttl_s=300)
                receipt = exact_client.restore(noise_snapshot, exact_device)
                self.assertEqual(receipt["status"], "rejected")
                self.assertIn(receipt["error"]["mhs_code"], (
                    "MHS.CONFLICT.SNAPSHOT_MISMATCH",
                ))
                own_snapshot = exact_client.snapshot(exact_device)
                own = exact_client.restore(own_snapshot, exact_device)
                self.assertEqual(own["status"], "completed")
            finally:
                exact_client.close()
                noise_client.close()
                exact_handle.shutdown()
                noise_handle.shutdown()
        finally:
            exact.close()
            noise.close()


if __name__ == "__main__":
    unittest.main()
