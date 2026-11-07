"""Stock G3 covers lazy camera pixels and finite ownership policy."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

SDK = Path(__file__).resolve().parents[2]

CHILD = r'''from pathlib import Path
import json,shutil,sys,tempfile
from mhs.driver.check import run_check,static_findings
sdk=Path(sys.argv[1])
with tempfile.TemporaryDirectory() as temp:
    package=Path(temp)/"thermostat"
    shutil.copytree(sdk/"examples/thermostat",package)
    driver=package/"driver.py"
    driver.write_text(driver.read_text()+"\n"+sys.argv[2])
    static=static_findings(package)
    report=run_check(package,gates=["G3"],write_report=False)
    gate=next(g for g in report["gates"] if g["id"]=="G3")
    print(json.dumps({"static":static,"gate":gate,
        "optional_imports":sorted(n for n in sys.modules if n.split('.')[0] in
            {"numpy","PIL","pymmcore","pymmcore_plus","imswitch"})}))
'''


class CameraPolicyIntegrityTests(unittest.TestCase):
    def stock(self, module, payload):
        source = ("from importlib import import_module\n"
                  "camera_module=import_module('.'.join(['mhs','bridge'," + repr(module) + "]))\n"
                  + payload + "\n")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(SDK / "src"))
        run = subprocess.run([sys.executable, "-c", CHILD, str(SDK), source],
                             env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        result = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(result["static"], [], result)
        self.assertEqual(result["optional_imports"], [], result)
        return result

    def tampered(self, result, member):
        self.assertEqual(result["gate"]["status"], "fail", result)
        self.assertTrue(any(f["code"] == "G3.GATE_TAMPERED" and member in f["message"]
                            for f in result["gate"]["findings"]), result)

    def test_lazy_pixel_functions_cannot_be_replaced_in_computed_import(self):
        for name in ("detach_pixels", "require_numpy"):
            with self.subTest(name=name):
                result = self.stock("camera_pixels", "def fabricated(*args, **kwargs): return None\n"
                                    + "camera_module." + name + "=fabricated")
                self.tampered(result, "camera_pixels." + name)

    def test_lazy_pixel_encoder_method_is_covered(self):
        result = self.stock("camera_pixels", "def fabricated(self, max_bytes): return b'not png'\n"
                            "camera_module.CameraPixels.png=fabricated")
        self.tampered(result, "camera_pixels.CameraPixels")

    def test_ordinary_policy_cannot_be_cleared_in_place(self):
        result = self.stock("pymmcore_camera", "camera_module._ORDINARY.clear()")
        self.assertEqual(result["gate"]["status"], "fail", result)

    def test_ordinary_policy_replacement_is_detected(self):
        result = self.stock("pymmcore_camera", "camera_module._ORDINARY=set()")
        self.tampered(result, "pymmcore_camera._ORDINARY")

    def test_unmodified_imports_need_no_optional_numeric_or_native_packages(self):
        for module in ("camera_pixels", "pymmcore_camera"):
            with self.subTest(module=module):
                result = self.stock(module, "")
                self.assertEqual(result["gate"]["status"], "pass", result)

    def test_live_core_lease_is_runtime_state_not_immutable_policy(self):
        from types import SimpleNamespace
        from mhs.bridge.pymmcore_camera import CameraLease
        from mhs.driver import check
        from tests.bridges.pymmcore_fixture import CameraScenario, CameraCore
        scenario = CameraScenario(SimpleNamespace(shape=(2, 3)))
        core = CameraCore(scenario)
        lease = CameraLease("Camera", scenario.factory())
        before = check._integrity_snapshot()
        try:
            lease.register_core(core)
            self.assertIs(lease.core, core)
            self.assertEqual(check._integrity_changes(before, check._integrity_snapshot()), [])
        finally:
            lease.release_core()
        self.assertEqual(check._integrity_changes(before, check._integrity_snapshot()), [])


if __name__ == "__main__":
    unittest.main()
