"""Determinism and safety-semantics tests for the reference device models.

The ``Fixture*`` classes pin the WP-06 06c contract of the reference
endpoints: they are protocol fixtures that serve catalogue verbs with
unchanged MCP tool names, take their identity from :mod:`mhs._ids`, read
published reports from ``MHS_CONFORMANCE_REPORTS`` or the checkout, signal
cancellation with :class:`mhs.signals.Cancelled`, and keep exactly the
documented catalogue drift (``MHS/sdk/docs/reference-endpoints.md``).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
import warnings
from pathlib import Path
from unittest import mock

from tests.endpoints import support  # noqa: F401 - puts the SDK on sys.path

from mhs import _ids
from mhs import catalog
from mhs._server import strict as _strict
from mhs.bridge.base import BridgeContext
from mhs.conformance.inprocess import client_for
from mhs.mcp import MCPProjection
from mhs.reference import _common, build_endpoint, build_server
from mhs.reference.arm import Arm2DOF, ArmBridge
from mhs.reference.conveyor import ConveyorBridge, ConveyorSim
from mhs.reference.lab import LabBench, PipetteBridge, PlateReaderBridge, SampleMoverBridge
from mhs.signals import Cancelled

REFERENCE_DIR = Path(_common.__file__).resolve().parent
DOCS = Path(__file__).resolve().parents[2] / "docs"
BUNDLE = DOCS / "reports" / "replay-bundle-conveyor.json"


def error_code(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


class ConveyorModelTests(unittest.TestCase):
    def test_step_is_integer_deterministic_and_snapshotable(self) -> None:
        sim = ConveyorSim()
        sim.start(50)
        sim.feed(1)
        sim.step(100)
        first = sim.state_doc()
        self.assertEqual(first["parts"][0]["position_um"], 5_000)
        clone = ConveyorSim()
        clone.restore(sim.snapshot())
        self.assertEqual(clone.state_doc(), first)
        sim.step(100)
        clone.step(100)
        self.assertEqual(clone.state_doc(), sim.state_doc())

    def test_door_latch_blocks_motion_and_reset_clears_it(self) -> None:
        sim = ConveyorSim()
        sim.start(80)
        sim.feed(1)
        sim.set_door("open")
        state = sim.state_doc()
        self.assertEqual(state["drive"], "stopped")
        self.assertTrue(state["latched"])
        with self.assertRaises(Exception):
            sim.start(50)
        sim.set_door("closed")
        sim.reset_interlocks()
        self.assertFalse(sim.state_doc()["latched"])
        sim.start(50)
        self.assertEqual(sim.state_doc()["drive"], "running")

    def test_estop_latches_and_holds_motion(self) -> None:
        sim = ConveyorSim()
        sim.start(50)
        sim.feed(1)
        sim.estop("test")
        position = sim.state_doc()["parts"][0]["position_um"]
        sim.step(50)
        self.assertEqual(sim.state_doc()["parts"][0]["position_um"], position)
        self.assertTrue(sim.state_doc()["latched"])
        sim.reset_interlocks()
        self.assertFalse(sim.state_doc()["latched"])

    def test_diverter_routes_parts_deterministically(self) -> None:
        sim = ConveyorSim()
        sim.start(200)
        sim.feed(1)
        sim.set_gate("divert")
        sim.step(5_000)
        parts = sim.state_doc()["parts"]
        self.assertTrue(parts)
        self.assertIn(parts[0]["route"], ("diverted", "stopped"))

    def test_feed_requires_clear_infeed(self) -> None:
        sim = ConveyorSim()
        sim.feed(1)
        with self.assertRaises(Exception) as caught:
            sim.feed(1)
        self.assertEqual(error_code(caught.exception), "MHS.DEVICE.PRECONDITION_UNMET")

    def test_fault_injection_is_visible_in_state(self) -> None:
        sim = ConveyorSim()
        sim.set_fault("sensor_fault", True)
        self.assertEqual(sim.state_doc()["sensors"]["infeed"], "unknown")
        sim.set_fault("sensor_fault", False)
        sim.start(50)
        sim.feed(1)
        sim.set_fault("jam", True)
        sim.step(100)
        self.assertEqual(sim.state_doc()["parts"][0]["position_um"], 0)


class LabModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bench = LabBench()
        self.pipette = PipetteBridge(self.bench)
        self.reader = PlateReaderBridge(self.bench)
        self.mover = SampleMoverBridge(self.bench)

    def tearDown(self) -> None:
        for bridge in (self.pipette, self.reader, self.mover):
            bridge.close()

    def test_transfer_moves_integer_volume_and_consumes_a_tip(self) -> None:
        result = self.pipette.transfer("A1", "B1", 25)
        self.assertEqual(result["volume_ul"], 25)
        self.assertEqual(self.bench.wells["A1"]["volume_ul"], 125)
        self.assertEqual(self.bench.wells["B1"]["volume_ul"], 25)
        self.assertTrue(result["tip_consumed"])
        self.assertEqual(result["tips_remaining"], 6)
        self.assertEqual(self.pipette.tip_state()["tip_volume_ul"], 0)

    def test_aspirate_requires_sufficient_source_volume(self) -> None:
        with self.assertRaises(Exception) as caught:
            self.pipette.aspirate("B2", 10)
        self.assertEqual(error_code(caught.exception), "MHS.DEVICE.PRECONDITION_UNMET")

    def test_plate_must_be_at_the_instrument(self) -> None:
        with self.assertRaises(Exception):
            self.reader.spectrum("plate-001", [600])
        self.mover.move("plate-001", "reader")
        readings = self.reader.spectrum("plate-001", [600], ["A1", "B1"])["readings"]
        self.assertEqual(len(readings), 2)
        self.assertGreater(readings[0]["absorbance_mAU"], readings[1]["absorbance_mAU"])
        with self.assertRaises(Exception):
            self.pipette.transfer("A1", "B1", 5)

    def test_reader_is_a_pure_function_of_state(self) -> None:
        self.mover.move("plate-001", "reader")
        first = self.reader.spectrum("plate-001", [450, 600], ["A1"])
        bench = LabBench()
        bench.location = "reader"
        reader2 = PlateReaderBridge(bench)
        try:
            second = reader2.spectrum("plate-001", [450, 600], ["A1"])
            self.assertEqual(first["readings"], second["readings"])
        finally:
            reader2.close()

    def test_snapshot_restore_roundtrip(self) -> None:
        self.pipette.transfer("A1", "B1", 20)
        snapshot = self.pipette.snapshot()
        self.pipette.transfer("A2", "B2", 20)
        self.pipette.restore(snapshot)
        self.assertEqual(self.bench.wells["A2"]["volume_ul"], 150)
        self.assertEqual(self.bench.wells["B2"]["volume_ul"], 0)


class ArmModelTests(unittest.TestCase):
    def test_forward_and_inverse_kinematics_agree(self) -> None:
        arm = Arm2DOF()
        x, y = arm.forward(30_000, -45_000)
        q1, q2 = arm.inverse(x, y, elbow="down")
        self.assertLessEqual(abs(q1 - 30_000), 1_500)
        self.assertLessEqual(abs(q2 + 45_000), 1_500)

    def test_joint_limits_are_enforced(self) -> None:
        arm = Arm2DOF()
        with self.assertRaises(Exception) as caught:
            arm.joint_position([200.0, 0.0])
        self.assertEqual(error_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_unreachable_cartesian_target_is_refused(self) -> None:
        arm = Arm2DOF()
        with self.assertRaises(Exception):
            arm.cartesian_pose(2000, 0)

    def test_snapshot_restore_is_exact(self) -> None:
        arm = Arm2DOF()
        arm.joint_position([10.0, 20.0])
        snapshot = arm.snapshot()
        arm.joint_position([-40.0, 60.0])
        arm.restore(snapshot)
        self.assertEqual(arm.state_doc()["joint_mdeg"], [10_000, 20_000])

    def test_seeded_noise_is_reproducible(self) -> None:
        targets = ([15.0, -25.0], [-5.0, 45.0])
        first = Arm2DOF(noise=True)
        first.seed_rng(42)
        first_poses = []
        for target in targets:
            first.joint_position(target)
            first_poses.append(first.state_doc()["pose_um"])
        second = Arm2DOF(noise=True)
        second.seed_rng(42)
        second_poses = []
        for target in targets:
            second.joint_position(target)
            second_poses.append(second.state_doc()["pose_um"])
        self.assertEqual(first_poses, second_poses)
        self.assertTrue(all(isinstance(value, int) for pose in first_poses for value in pose))
        # same seed from scratch reproduces the same first perturbed pose
        third = Arm2DOF(noise=True)
        third.seed_rng(42)
        third.joint_position(targets[0])
        self.assertEqual(third.state_doc()["pose_um"], first_poses[0])


def _server(name: str, **options):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the documented compatibility-mode drift warnings
        spec = build_endpoint(name, endpoint_id=f"mhs://localhost/{name}", **options)
        return spec, build_server(spec, log_ready=False)


#: MCP tool names of the reference endpoints (unchanged by the 06c verb and drift fixes).
TOOL_NAMES = {
    "conveyor": [
        "mhs__lab_conveyor_workcell__actuation_valve", "mhs__lab_conveyor_workcell__mhs_reference_feed",
        "mhs__lab_conveyor_workcell__mhs_reference_start", "mhs__lab_conveyor_workcell__motion_stop",
        "mhs__lab_conveyor_workcell__world_restore", "mhs__lab_conveyor_workcell__world_snapshot",
        "mhs__lab_conveyor_workcell__world_state", "mhs__lab_conveyor_workcell__world_step",
    ],
    "lab": [
        "mhs__lab_liquid_handler__fluid_aspirate", "mhs__lab_liquid_handler__fluid_dispense",
        "mhs__lab_liquid_handler__fluid_level", "mhs__lab_liquid_handler__fluid_transfer",
        "mhs__lab_liquid_handler__motion_stop", "mhs__lab_plate_reader__measure_spectrum",
        "mhs__lab_sample_mover__motion_stop", "mhs__lab_sample_mover__sample_move",
    ],
    "arm": [
        "mhs__robot_arm_2dof__motion_cartesian_pos_529c54", "mhs__robot_arm_2dof__motion_home",
        "mhs__robot_arm_2dof__motion_joint_positio_288cd9", "mhs__robot_arm_2dof__motion_stop",
        "mhs__robot_arm_2dof__world_restore", "mhs__robot_arm_2dof__world_seed",
        "mhs__robot_arm_2dof__world_snapshot", "mhs__robot_arm_2dof__world_state",
    ],
}

#: The catalogue drift the fixtures keep until the post-pilot class realignment
#: (field names and resource kinds; documented in docs/reference-endpoints.md).
REMAINING_DRIFT = {
    "conveyor": {
        ("schema-drift", "cap.actuation.valve.v1"), ("kind-mismatch", "cap.actuation.valve.v1"),
        ("kind-mismatch", "cap.motion.stop.v1"),
    },
    "lab": {
        ("schema-drift", "cap.fluid.aspirate.v1"), ("schema-drift", "cap.fluid.dispense.v1"),
        ("schema-drift", "cap.fluid.transfer.v1"), ("schema-drift", "cap.fluid.level.v1"),
        ("schema-drift", "cap.measure.spectrum.v1"), ("schema-drift", "cap.sample.move.v1"),
        ("kind-mismatch", "cap.motion.stop.v1"),
    },
    "arm": {
        ("schema-drift", "cap.motion.joint_position.v1"), ("schema-drift", "cap.motion.cartesian_pose.v1"),
        ("kind-mismatch", "cap.world.state.v1"), ("kind-mismatch", "cap.world.snapshot.v1"),
        ("kind-mismatch", "cap.world.restore.v1"), ("kind-mismatch", "cap.world.seed.v1"),
    },
}


class FixtureVerbTests(unittest.TestCase):
    """Reference endpoints serve catalogue verbs; MCP tool names are unchanged."""

    def test_hello_and_manifests_report_catalogue_verbs(self) -> None:
        for name, options in (("conveyor", {}), ("lab", {}), ("arm", {}), ("replay", {"bundle": str(BUNDLE)})):
            with self.subTest(endpoint=name):
                spec, server = _server(name, **options)
                try:
                    client = client_for(server)
                    hello = client.hello()
                    manifests = {item["device_id"]: item for item in client.devices()}
                    for device in hello["devices"]:
                        published = {item["capability_id"]: item.get("verb")
                                     for item in manifests[device["device_id"]]["capabilities"]}
                        for capability in device["capabilities"]:
                            cid = capability["capability_id"]
                            expected = catalog.get(cid)["verb"] if not catalog.is_extension(cid) else "invoke"
                            self.assertEqual(capability["verb"], expected, cid)
                            self.assertEqual(published[cid], expected, cid)
                finally:
                    spec.close()

    def test_world_state_is_a_read_and_leaves_the_revision(self) -> None:
        spec, server = _server("conveyor")
        try:
            client = client_for(server)
            hello = client.hello()
            verbs = {item["capability_id"]: item["verb"] for item in hello["devices"][0]["capabilities"]}
            self.assertEqual(verbs["cap.world.state.v1"], "read")
            self.assertEqual(verbs["cap.actuation.valve.v1"], "write")
            self.assertEqual(verbs["cap.world.step.v1"], "invoke")
            device_id = hello["devices"][0]["device_id"]
            session = client.open_session(device_ids=[device_id], ttl_s=60)["session_id"]
            receipt = client.invoke("cap.world.state.v1", {}, device_id=device_id, session_id=session)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["state_revision_before"], receipt["state_revision_after"])
        finally:
            spec.close()

    def test_mcp_tool_names_are_unchanged(self) -> None:
        for name, expected in TOOL_NAMES.items():
            with self.subTest(endpoint=name):
                spec, server = _server(name)
                try:
                    projection = MCPProjection(client_for(server))
                    with contextlib.redirect_stderr(io.StringIO()):
                        projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                            "protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "reference-tests", "version": _ids.SDK_VERSION}}})
                        listed = projection.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                                                            "params": {}})
                    tools = sorted(tool["name"] for tool in listed["result"]["tools"] if "x-mhs" in tool)
                    self.assertEqual(tools, expected)
                finally:
                    spec.close()


class FixtureIdentityTests(unittest.TestCase):
    """Identity comes from mhs._ids; no legacy domain anywhere in mhs/reference."""

    def test_sources_never_name_the_legacy_domain(self) -> None:
        for path in sorted(REFERENCE_DIR.glob("*.py")):
            with self.subTest(module=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("modelhardwarestandard", text)
                self.assertNotIn("parents[5]", text)
                self.assertIn("protocol fixture", text.lower(), "the docstring says it is a fixture")

    def test_manifests_use_the_project_identity(self) -> None:
        for name in ("conveyor", "lab", "arm"):
            for manifest in build_endpoint(name).devices:
                with self.subTest(device=manifest["device_id"]):
                    self.assertNotIn("modelhardwarestandard", json.dumps(manifest))
                    self.assertTrue(manifest["provenance"]["adapter_id"].startswith(_ids.ADAPTER_ID_PREFIX + "reference."))
                    self.assertEqual(manifest["vendor"], {"name": f"{_ids.PROJECT_NAME} reference fixture"})
                    self.assertEqual(manifest["mhs_version"], _ids.WIRE_VERSION)


class FixtureReportTests(unittest.TestCase):
    """Published reports come from MHS_CONFORMANCE_REPORTS or the checkout, never a guessed parent."""

    def test_the_checkout_is_found_by_its_layout(self) -> None:
        root = _common.checkout_root()
        self.assertIsNotNone(root)
        self.assertTrue((root / "MHS" / "conformance" / "reports").is_dir())
        for name in ("conveyor", "lab", "arm", "arm-seeded", "replay"):
            with self.subTest(endpoint=name):
                self.assertTrue(any(path.is_file() for path in _common.report_candidates(name)), name)
                claim = _common.published_conformance(name)
                self.assertIsNotNone(claim)
                self.assertTrue(claim["report_digest"].startswith("sha256:"))

    def test_the_environment_directory_is_read_first(self) -> None:
        source = next(path for path in _common.report_candidates("conveyor") if path.is_file())
        report = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            shutil.copy(source, Path(directory) / source.name)
            with mock.patch.dict(os.environ, {_common.REPORTS_ENV: directory}), \
                    mock.patch.object(_common, "checkout_root", return_value=None):
                claim = _common.published_conformance("conveyor")
                manifest = build_endpoint("conveyor").devices[0]
        self.assertEqual(claim["report_digest"], report["report_digest"])
        self.assertEqual(manifest["conformance"]["report_digest"], report["report_digest"])

    def test_without_a_report_no_claim_is_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {_common.REPORTS_ENV: directory}), \
                    mock.patch.object(_common, "checkout_root", return_value=None):
                self.assertIsNone(_common.published_conformance("conveyor"))
                self.assertNotIn("conformance", build_endpoint("conveyor").devices[0])

    def test_a_report_without_a_suite_version_is_not_a_claim(self) -> None:
        source = next(path for path in _common.report_candidates("lab") if path.is_file())
        report = json.loads(source.read_text(encoding="utf-8"))
        report.pop("suite_version")
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / source.name).write_text(json.dumps(report), encoding="utf-8")
            with mock.patch.dict(os.environ, {_common.REPORTS_ENV: directory}), \
                    mock.patch.object(_common, "checkout_root", return_value=None):
                self.assertIsNone(_common.published_conformance("lab"))


class FixtureDriftTests(unittest.TestCase):
    """Only the documented drift remains; the fixable findings are fixed."""

    def test_remaining_strict_findings_are_the_documented_drift(self) -> None:
        documented = (DOCS / "reference-endpoints.md").read_text(encoding="utf-8")
        for name, expected in REMAINING_DRIFT.items():
            with self.subTest(endpoint=name):
                spec, server = _server(name)
                try:
                    found = {(item.rule, item.capability_id) for device in server.devices.values()
                             for item in _strict.resolve_device(device).findings}
                finally:
                    spec.close()
                self.assertEqual(found, expected)
                for _rule, capability_id in expected:
                    self.assertIn(f"`{capability_id}`", documented)

    def test_conveyor_ticks_start_at_one(self) -> None:
        spec, server = _server("conveyor")
        try:
            client = client_for(server)
            device_id = client.hello()["devices"][0]["device_id"]
            session = client.open_session(device_ids=[device_id], ttl_s=60)["session_id"]
            receipt = client.invoke("cap.world.step.v1", {"ticks": 0}, device_id=device_id, session_id=session)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
            self.assertEqual(spec.bridges[device_id].sim.tick, 0)
        finally:
            spec.close()

    def test_the_test_delay_envelope_exists_only_in_the_test_profile(self) -> None:
        plain = build_endpoint("conveyor").devices[0]["safety"]["envelope"]
        test = build_endpoint("conveyor", test_profile=True).devices[0]["safety"]["envelope"]
        self.assertNotIn("x-cap.mhs-test.delay.v1", plain)
        self.assertIn("x-cap.mhs-test.delay.v1", test)
        self.assertEqual(catalog.compile_manifest_limits(build_endpoint("conveyor").devices[0]).unused_envelope, ())

    def test_every_safe_state_action_is_bound_and_the_plate_reader_estop_succeeds(self) -> None:
        for manifest in build_endpoint("lab").devices:
            bound = {item["capability_id"] for item in manifest["capabilities"]}
            with self.subTest(device=manifest["device_id"]):
                self.assertLessEqual(set(manifest["safety"]["safe_state"]["achieved_by"]), bound)
        spec, server = _server("lab")
        try:
            client = client_for(server)
            reader = "mhs://localhost/lab/lab/plate-reader"
            session = client.open_session(device_ids=[reader], ttl_s=60)["session_id"]
            receipt = client.estop("test", device_id=reader, session_id=session)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertIs(receipt["output"]["safe_state_achieved"], True, receipt)
        finally:
            spec.close()


class FixtureCancellationTests(unittest.TestCase):
    """Bridges signal cancellation with mhs.signals.Cancelled, never a {'cancelled': True} output."""

    @staticmethod
    def _cancelled() -> BridgeContext:
        ctx = BridgeContext()
        ctx.cancel_event = threading.Event()
        ctx.cancel_event.set()
        return ctx

    def test_lab_and_arm_bridges_raise_before_any_effect(self) -> None:
        bench = LabBench()
        cases = [
            (PipetteBridge(bench), "cap.fluid.transfer.v1",
             {"source_well": "A1", "destination_well": "B1", "volume_ul": 5}),
            (PlateReaderBridge(bench), "cap.measure.spectrum.v1", {"plate_id": "plate-001", "wavelengths_nm": [600]}),
            (SampleMoverBridge(bench), "cap.sample.move.v1", {"plate_id": "plate-001", "to": "reader"}),
            (ArmBridge(), "cap.motion.home.v1", {}),
        ]
        for bridge, capability_id, args in cases:
            with self.subTest(capability=capability_id):
                try:
                    with self.assertRaises(Cancelled):
                        bridge.call(capability_id, args, self._cancelled())
                finally:
                    bridge.close()
        self.assertEqual(bench.wells["B1"]["volume_ul"], 0)
        self.assertEqual(bench.location, "liquid_handler")

    def test_conveyor_signals_a_cancelled_call_and_delay(self) -> None:
        bridge = ConveyorBridge(test_profile=True)
        try:
            with self.assertRaises(Cancelled):
                bridge.call("cap.world.step.v1", {"ticks": 1}, self._cancelled())
            with self.assertRaises(Cancelled):
                bridge.call("x-cap.mhs-test.delay.v1", {"ms": 50}, self._cancelled())
            self.assertEqual(bridge.call("x-cap.mhs-test.delay.v1", {"ms": 10}, BridgeContext()),
                             {"slept_ms": 10, "cancelled": False})
        finally:
            bridge.close()


if __name__ == "__main__":
    unittest.main()
