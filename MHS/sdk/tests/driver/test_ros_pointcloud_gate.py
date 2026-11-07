"""Stock source, admission and policy gates for lossless PointCloud2 capture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from mhs.adapter import LoadError, load
from mhs.driver.check import _Context
from tests.driver import gate_support as gs

CAP = "cap.sensing.point_cloud.v1"
SDK = Path(__file__).resolve().parents[2]
DRIVER = '''from mhs.driver import RosDriver
class Cloud(RosDriver):
    device_id, device_kind, mode, risk = "cloud-gate", "sensor.depth", "hardware", "R0"
    ros_version = 2
    backends = {"fake": ".fake:Transport", "hardware": ".native:connect"}
    commands = {"cap.sensing.point_cloud.v1": {
        "topic": "/points", "type": "sensor_msgs/msg/PointCloud2", "operation": "subscribe",
        "point_cloud": {}, "source_ref": "node.cpp:1"}}
'''
FAKE = '''from mhs.bridge.ros_transport import RecordingRosTransport
class Transport(RecordingRosTransport):
    def __init__(self):
        super().__init__(self.respond)
    def respond(self, request):
        if request["op"] == "subscribe":
            return {"op": "publish", "topic": request["topic"], "id": request["id"], "msg": {
                "header": {"stamp": {"sec": 2, "nanosec": 3}, "frame_id": "laser"},
                "width": 1, "height": 1, "point_step": 12, "row_step": 12,
                "is_dense": False, "is_bigendian": False,
                "fields": [{"name": n, "offset": i * 4, "datatype": 7, "count": 1}
                           for i, n in enumerate(("x", "y", "z"))],
                "data": [0, 0, 128, 63, 0, 0, 0, 64, 0, 0, 64, 64]}}
'''


def package(test):
    directory = gs.copy_tutorial(test, name="pointcloud")
    (directory / "driver.py").write_text(DRIVER)
    (directory / "fake.py").write_text(FAKE)
    (directory / "native.py").write_text('def connect(**options):\n    raise AssertionError("No hardware in SDK test")\n')
    (directory / "vendor/node.cpp").write_text('publish<sensor_msgs::msg::PointCloud2>("/points");\n')
    gs.edit_json(directory, "driver.lock.json", backends={"fake": ".fake:Transport", "hardware": ".native:connect"})
    gs.edit_json(directory, "task.json", safety={"expected_mode": "hardware", "risk_floor": "R0"}, entry_symbols=[],
                 driver_dir="MHS/sdk/examples/pointcloud")
    (directory / "site-limits.example.json").rename(directory.parent / "tutorial-overlay-original.json")
    gs.regenerate(directory)
    return directory


class RosPointCloudGateTests(unittest.TestCase):
    def test_complete_synthetic_package_passes_full_stock_cli_and_default_store(self):
        directory = package(self)
        result = gs.run_cli("check", str(directory), "--backend", "fake")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((directory / "check-report.json").read_text())
        self.assertEqual(report["failed"], [])
        self.assertEqual(gs.statuses(report)["G7"], "pass")
        context = _Context(directory, "fake", None, None, False)
        self.addCleanup(context.close)
        stores = []
        for factory in (context.endpoint, context.server_factory()):
            opened = factory()
            server, close = opened if isinstance(opened, tuple) else (opened.server, opened.close)
            store = server._artifact_store
            self.assertIsNotNone(store)
            stores.append(store)
            self.assertEqual(store.max_artifact_bytes, 2 * 1024 * 1024)
            close()
            self.assertFalse(store._root.exists())
        self.assertIsNot(stores[0], stores[1])

    def test_exact_pointcloud_source_endpoint_and_type_remain_required(self):
        for source, expected in [
            ('publish<sensor_msgs::msg::PointCloud2>("/wrong");\n', 'G7.ROS_ENDPOINT_NOT_UPSTREAM'),
            ('publish<sensor_msgs::msg::Image>("/points");\n', 'G7.ROS_TYPE_NOT_UPSTREAM'),
        ]:
            directory = package(self)
            (directory / "vendor/node.cpp").write_text(source)
            report = gs.check(directory, gates=("G7",))
            self.assertIn(expected, gs.findings(report))

    def test_pointcloud_policy_mutations_are_refused_by_stock_isolated_cli(self):
        attacks = [
            ('_TYPE_BYTES', 'module._TYPE_BYTES[7] = 1'),
            ('POINT_TYPES', 'module.POINT_TYPES.add("sensor_msgs/msg/Image")'),
            ('_MESSAGE_FIELDS', 'module._MESSAGE_FIELDS.discard("fields")'),
            ('convert_pointcloud', 'def replacement(*a, **k): return b"bad", 1, "map", {}\nmodule.convert_pointcloud=replacement'),
        ]
        for member, payload in attacks:
            with self.subTest(member=member):
                directory = package(self)
                path = directory / "driver.py"
                path.write_text(path.read_text() + '\nfrom importlib import import_module\n'
                    'module=import_module(".".join(["mhs","bridge","ros_pointcloud"]))\n' + payload + '\n')
                result = gs.run_cli("check", str(directory), "--backend", "fake")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads((directory / "check-report.json").read_text())
                self.assertIn('G3.GATE_TAMPERED', gs.findings(report))
                self.assertTrue(any(member in f['message'] for g in report['gates'] for f in g['findings']
                                    if f['code'] == 'G3.GATE_TAMPERED'))

    def test_hardware_opt_in_refuses_without_importing_or_calling_the_factory(self):
        directory = package(self)
        marker = directory / 'native-imported.txt'
        (directory / 'native.py').write_text('from pathlib import Path\n'
            f'Path({str(marker)!r}).write_text("unexpected import")\n'
            'def connect(**options):\n    raise AssertionError("unexpected factory call")\n')
        with self.assertRaisesRegex(LoadError, "a hardware backend needs allow_hardware=True"):
            load(directory, backend='hardware')
        self.assertFalse(marker.exists())

    def test_imports_require_no_ros_pcl_or_numeric_packages(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(SDK / 'src'))
        result = subprocess.run([sys.executable, '-c', 'import sys; import mhs.bridge.ros_pointcloud; '
            'import mhs.driver.check; assert not any(n.split(".")[0] in '
            '{"rospy","rclpy","pcl","numpy","PIL"} for n in sys.modules)'],
            env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
