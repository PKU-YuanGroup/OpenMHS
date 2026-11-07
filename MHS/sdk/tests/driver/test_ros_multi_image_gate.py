"""Every finite image source remains inside stock source and policy gates."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.driver import gate_support as gs

CAP = "cap.sensing.image.v1"
SDK = Path(__file__).resolve().parents[2]
DRIVER = '''from mhs.driver import RosDriver
class Camera(RosDriver):
    device_id, device_kind, mode, risk = "multi-image-gate", "sensor.camera", "hardware", "R0"
    ros_version = 1
    backends = {"fake": ".fake:Transport", "hardware": ".native:connect"}
    commands = {"cap.sensing.image.v1": {"cameras": {
        name: {"topic": "/camera/" + name, "type": "sensor_msgs/Image", "operation": "subscribe", "image": {},
               "source_ref": "node.cpp:" + str(index + 1)}
        for index, name in enumerate(("color", "depth", "ir"))}}}
'''
FAKE = '''from mhs.bridge.ros_transport import RecordingRosTransport
class Transport(RecordingRosTransport):
    def __init__(self):
        super().__init__(self.respond)
    def respond(self, request):
        if request["op"] == "subscribe":
            return {"op": "publish", "topic": request["topic"], "id": request["id"], "msg": {
                "header": {"seq": 7, "stamp": {"secs": 2, "nsecs": 3}, "frame_id": request["topic"]},
                "width": 2, "height": 1, "step": 2, "encoding": "mono8", "is_bigendian": 0, "data": [3, 248]}}
'''


def package(test):
    directory = gs.copy_tutorial(test, name="multi-image")
    (directory / "driver.py").write_text(DRIVER)
    (directory / "fake.py").write_text(FAKE)
    (directory / "native.py").write_text('def connect(**options):\n    raise AssertionError("No hardware in SDK test")\n')
    (directory / "vendor/node.cpp").write_text(''.join(
        'publish<sensor_msgs::Image>("/camera/' + name + '");\n' for name in ("color", "depth", "ir")))
    gs.edit_json(directory, "driver.lock.json", backends={"fake": ".fake:Transport", "hardware": ".native:connect"})
    gs.edit_json(directory, "task.json", safety={"expected_mode": "hardware", "risk_floor": "R0"}, entry_symbols=[],
                 driver_dir="MHS/sdk/examples/multi-image")
    (directory / "site-limits.example.json").rename(directory.parent / "tutorial-overlay-original.json")
    gs.regenerate(directory)
    return directory


class RosMultiImageGateTests(unittest.TestCase):
    def test_complete_synthetic_package_passes_stock_full_isolated_cli(self):
        directory = package(self)
        result = gs.run_cli("check", str(directory), "--backend", "fake")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((directory / "check-report.json").read_text())
        self.assertEqual(report["failed"], [])
        self.assertEqual(gs.statuses(report)["G7"], "pass")

    def test_each_uncaptured_child_requires_its_own_exact_source_and_type(self):
        for edit, expected in (
            (lambda text: text.replace('"/camera/ir"', '"/camera/unrelated"'), "G7.ROS_ENDPOINT_NOT_UPSTREAM"),
            (lambda text: text.replace('sensor_msgs::Image>("/camera/ir"', 'std_msgs::String>("/camera/ir"'), "G7.ROS_TYPE_NOT_UPSTREAM"),
        ):
            with self.subTest(expected=expected):
                directory = package(self)
                path = directory / "vendor/node.cpp"
                path.write_text(edit(path.read_text()))
                report = gs.check(directory, gates=("G7",))
                self.assertIn(expected, gs.findings(report))
                self.assertTrue(any("ir" in str(f.get("path")) for g in report["gates"]
                                    for f in g["findings"] if f["code"] == expected))

    def test_wire_cannot_subscribe_to_a_caller_chosen_undeclared_endpoint(self):
        directory = package(self)
        from mhs.driver.check import Gate, _g7
        from mhs.driver.ros_check import _bindings
        from mhs.driver.upstream import UpstreamTree
        from mhs.testing.recorder import RecordLog
        from types import SimpleNamespace
        from mhs.driver.loader import driver_class
        cls = driver_class(directory)
        self.assertEqual(len(list(_bindings(cls))), 3)
        log = RecordLog("controlled wire")
        log.record("send", "call", ({"op": "subscribe", "topic": "/rogue", "type": "sensor_msgs/Image"},))
        gate = Gate("G7", "Native surface")
        _g7(SimpleNamespace(cls=cls, family="ros", tree=UpstreamTree(directory / "vendor", use_git=False), logs=[log]), gate)
        self.assertTrue(any(f.code == "G7.ROS_WIRE_UNDECLARED" for f in gate.findings))

    def test_computed_import_mutations_are_rejected_by_the_stock_cli(self):
        attacks = [
            ("mhs.bridge.ros_images", "source_metadata", "def forged(*a, **k): return {}\nmodule.source_metadata=forged"),
            ("mhs.bridge.ros_images", "camera_sources", "def forged(value): return dict(value)\nmodule.camera_sources=forged"),
            ("mhs.bridge.ros_images", "_ENCODINGS", "module._ENCODINGS.clear()"),
            ("mhs.artifacts", "_vendor_metadata", "def forged(value): return value\nmodule._vendor_metadata=forged"),
        ]
        for module, member, payload in attacks:
            with self.subTest(module=module, member=member):
                directory = package(self)
                driver = directory / "driver.py"
                source = '\nfrom importlib import import_module\nmodule=import_module(".".join(' + repr(module.split('.')) + '))\n' + payload + '\n'
                driver.write_text(driver.read_text() + source)
                result = gs.run_cli("check", str(directory), "--backend", "fake")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads((directory / "check-report.json").read_text())
                self.assertIn("G3.GATE_TAMPERED", gs.findings(report))
                self.assertTrue(any(member in f["message"] for g in report["gates"]
                                    for f in g["findings"] if f["code"] == "G3.GATE_TAMPERED"))

    def test_profile_imports_do_not_require_optional_image_numeric_or_native_dependencies(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(SDK / "src"))
        done = subprocess.run([sys.executable, "-c", 'import sys; import mhs.bridge.ros; import mhs.driver.check; '
            'assert not any(n.split(".")[0] in {"PIL","numpy","rospy","rclpy"} for n in sys.modules)'],
            env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
