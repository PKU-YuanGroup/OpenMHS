"""mhs.adapter.load and the driver package loader: backend rules, review gate, mhs-adapter.json, templates."""

from __future__ import annotations

import copy
import json
import socket
import textwrap
import unittest
from pathlib import Path

from mhs import _ids
from mhs.adapter import LoadError, load, load_driver
from mhs.driver import DriverDefinitionError, FAKE_FIDELITY, close_server, scaffold
from mhs.driver.loader import driver_class, read_lock
from mhs.errors import MHSError

from tests.driver import support

DRIVER_PY = textwrap.dedent('''
    """A test driver package (relative imports and relative backends)."""

    from mhs.driver import Driver, Limit, estop, read, write

    from .fake import FakeBath


    class Bath(Driver):
        device_id, device_kind = "lab/bath", "thermal.zone"
        mode, risk = "hardware", "{risk}"
        native = "julabo.julabo:JulaboCF"
        backends = {{"hardware": ".native:connect", "fake": ".fake:FakeBath"}}
        safe_state = "heater off"
        estop_physical_ref = "front panel stop switch"

        @read("temperature", unit="Cel")
        def temperature(self):
            return self.native.temperature

        @write("setpoint", unit="Cel", limit=Limit(min=-20, max=150, source="vendor_doc", ref="manual.pdf:4"))
        def set_setpoint(self, value):
            self.native.setpoint = value

        @estop
        def stop(self):
            self.native.stopped = True


    LOCAL_FAKE = FakeBath
''')

FAKE_PY = textwrap.dedent('''
    class FakeBath:
        def __init__(self, **options):
            self.options = options
            self.temperature = 22.0
            self.setpoint = 20.0
            self.stopped = False
''')

NATIVE_PY = textwrap.dedent('''
    def connect(**options):
        from .fake import FakeBath

        bath = FakeBath(**options)
        bath.hardware = True
        return bath
''')


def package(test: unittest.TestCase, *, risk: str = "R2", lock: dict | None | str = "model",
            extra: dict | None = None) -> Path:
    directory = support.temp_dir(test) / "labs" / "example__bath"
    files = {"driver.py": DRIVER_PY.format(risk=risk), "fake.py": FAKE_PY, "native.py": NATIVE_PY}
    if isinstance(lock, dict):
        files["driver.lock.json"] = json.dumps(lock)
    elif lock == "model":
        files["driver.lock.json"] = json.dumps(support.lock_document())
    files.update(extra or {})
    return support.write_package(directory, files)


class FakeBackendTests(unittest.TestCase):
    def test_fake_backend_serves_mode_simulated_strictly(self) -> None:
        directory = package(self)
        server = load(directory)
        self.addCleanup(close_server, server)
        self.assertIs(server.strict, True)
        [device] = server.devices.values()
        self.assertEqual(device.device_id, "mhs://localhost/lab/bath/fake")
        self.assertEqual(device.mode, "simulated")
        self.assertEqual(device.models, ["mhs://localhost/lab/bath"])
        self.assertEqual(device.fidelity, FAKE_FIDELITY)
        self.assertEqual(device.provenance["source_commit"], "a" * 40)
        self.assertFalse(getattr(device.bridge.native, "hardware", False))
        client = support.Client(server)
        self.assertEqual(client.write({"setpoint": 40})["status"], "completed")
        self.assertEqual(support.code(client.write({"setpoint": 400})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(list(directory.rglob("__pycache__")), [])

    def test_a_model_authored_r2_driver_still_serves_its_fake_without_review(self) -> None:
        server = load(package(self, lock=support.lock_document(reviewed=False)), backend="fake")
        self.addCleanup(close_server, server)
        self.assertEqual(next(iter(server.devices.values())).mode, "simulated")

    def test_site_limits_for_the_hardware_id_narrow_the_fake(self) -> None:
        overlay = {"openmhs": "0.9", "site": "t", "issued_by": {"id": "operator:t"}, "issued_at": "2026-10-22T09:00:00Z",
                   "devices": {"mhs://localhost/lab/bath": {
                       "setpoint": {"max": 90, "unit": "Cel", "source": "operator", "reason": "fluid"}}}}
        server = load(package(self), site_limits=overlay)
        self.addCleanup(close_server, server)
        client = support.Client(server)
        self.assertEqual(support.code(client.write({"setpoint": 95})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(client.write({"setpoint": 85})["status"], "completed")

    def test_load_driver_options_and_native(self) -> None:
        directory = package(self)
        driver = load_driver(directory, options={"port": "COM3"})
        self.addCleanup(driver.close)
        self.assertEqual(driver.native.options, {"port": "COM3"})
        sentinel = type("Recorded", (), {"temperature": 1.0, "setpoint": 0.0, "stopped": False})()
        other = load_driver(directory, native=sentinel)
        self.addCleanup(other.close)
        self.assertIs(other.native, sentinel)

    def test_strict_cannot_be_turned_off_and_unknown_backends_fail(self) -> None:
        directory = package(self)
        with self.assertRaises(TypeError):
            load(directory, strict=False)
        for backend in ("transcript", "real", ""):
            with self.subTest(backend=backend):
                with self.assertRaises(LoadError) as caught:
                    load(directory, backend=backend)
                self.assertEqual(caught.exception.reason, "backend_unknown")
                with self.assertRaises(LoadError):
                    load_driver(directory, backend=backend)
        with self.assertRaises(MHSError) as caught:
            load(directory, backend="sim")  # a known name the package does not declare
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")


MARKING_NATIVE_PY = textwrap.dedent('''
    from pathlib import Path


    def connect(**options):
        from .fake import FakeBath

        Path(options["marker"]).write_text("connected", encoding="utf-8")
        return FakeBath(**options)
''')


class FailClosedLoadTests(unittest.TestCase):
    """A load that is refused never reaches the hardware entry point (verifier probes 5 and 7)."""

    def marker(self) -> Path:
        return support.temp_dir(self) / "connected"

    def test_a_sim_backend_reusing_the_hardware_entry_point_is_refused(self) -> None:
        driver_py = DRIVER_PY.format(risk="R2").replace(
            '"fake": ".fake:FakeBath"}', '"fake": ".fake:FakeBath", "sim": ".native:connect"}')
        directory = package(self, extra={"driver.py": driver_py, "native.py": MARKING_NATIVE_PY})
        marker = self.marker()
        with self.assertRaises(DriverDefinitionError) as caught:
            load(directory, backend="sim", options={"marker": str(marker)})
        self.assertIn("hardware entry point", str(caught.exception))
        self.assertFalse(marker.exists())

    def test_an_unknown_backend_name_in_the_package_is_a_definition_error(self) -> None:
        driver_py = DRIVER_PY.format(risk="R2").replace('"hardware": ".native:connect"', '"real": ".native:connect"')
        directory = package(self, extra={"driver.py": driver_py, "native.py": MARKING_NATIVE_PY})
        with self.assertRaises(DriverDefinitionError) as caught:
            load(directory, options={"marker": str(self.marker())})
        self.assertIn("backend name 'real' is not one of", str(caught.exception))

    def test_strict_refusal_comes_before_the_backend_opens(self) -> None:
        # R2 hardware with neither a physical e-stop nor a safe_state action: SAFE-045 refuses it.
        driver_py = DRIVER_PY.format(risk="R2").replace('estop_physical_ref = "front panel stop switch"', "")
        driver_py = driver_py.replace("LOCAL_FAKE = FakeBath", textwrap.dedent('''
            def _setup(self):
                raise AssertionError("setup() ran")


            Bath.setup = _setup
        '''))
        directory = package(self, lock=support.lock_document(reviewed=True),
                            extra={"driver.py": driver_py, "native.py": MARKING_NATIVE_PY})
        marker = self.marker()
        with self.assertRaises(DriverDefinitionError) as caught:
            load(directory, backend="hardware", allow_hardware=True, state_dir=support.temp_dir(self),
                 options={"marker": str(marker)})
        self.assertIn("SAFE-045", str(caught.exception))
        self.assertFalse(marker.exists())
        self.assertIn("SAFE-045", {item.rule for item in caught.exception.findings})
        self.assertIn("Bath.setup = _setup", (directory / "driver.py").read_text(encoding="utf-8"))


class HardwareBackendRuleTests(unittest.TestCase):
    def test_hardware_needs_allow_hardware(self) -> None:
        with self.assertRaises(LoadError) as caught:
            load(package(self, lock=support.lock_document(reviewed=True)), backend="hardware")
        self.assertEqual(caught.exception.reason, "hardware_not_allowed")

    def test_hardware_needs_a_state_dir(self) -> None:
        with self.assertRaises(LoadError) as caught:
            load(package(self, lock=support.lock_document(reviewed=True)), backend="hardware", allow_hardware=True)
        self.assertEqual(caught.exception.reason, "state_dir_required")

    def test_model_authored_r2_hardware_without_review_is_refused(self) -> None:
        state_dir = support.temp_dir(self)
        with self.assertRaises(LoadError) as caught:
            load(package(self, lock=support.lock_document(reviewed=False)), backend="hardware", allow_hardware=True,
                 state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")
        self.assertIn("reviewed_by", str(caught.exception))
        self.assertEqual(list(state_dir.iterdir()), [])  # refused before anything started

    def test_reviewed_model_driver_serves_hardware(self) -> None:
        server = load(package(self, lock=support.lock_document(reviewed=True)), backend="hardware",
                      allow_hardware=True, state_dir=support.temp_dir(self))
        self.addCleanup(close_server, server)
        [device] = server.devices.values()
        self.assertEqual((device.device_id, device.mode), ("mhs://localhost/lab/bath", "hardware"))
        self.assertIsNone(device.fidelity)
        self.assertTrue(device.bridge.native.hardware)

    def test_human_authored_driver_needs_no_reviewer(self) -> None:
        server = load(package(self, lock=support.lock_document(kind="human")), backend="hardware",
                      allow_hardware=True, state_dir=support.temp_dir(self))
        self.addCleanup(close_server, server)

    def test_r2_hardware_needs_a_valid_lock(self) -> None:
        for lock in (None, {"package_id": "broken"}):
            with self.subTest(lock=lock):
                with self.assertRaises(LoadError) as caught:
                    load(package(self, lock=lock), backend="hardware", allow_hardware=True,
                         state_dir=support.temp_dir(self))
                self.assertEqual(caught.exception.reason, "review_required")

    def test_below_r2_the_review_gate_does_not_apply(self) -> None:
        server = load(package(self, risk="R1", lock=support.lock_document(reviewed=False)), backend="hardware",
                      allow_hardware=True, state_dir=support.temp_dir(self))
        self.addCleanup(close_server, server)

    def test_a_simulated_driver_has_no_hardware_backend(self) -> None:
        directory = support.write_package(support.temp_dir(self) / "sim", {"driver.py": textwrap.dedent('''
            from mhs.driver import FAKE_FIDELITY, Driver, Limit, write

            class Sim(Driver):
                device_id, device_kind, mode = "sim", "instrument", "simulated"
                fidelity = dict(FAKE_FIDELITY, engine="analytic")
                backends = {"fake": dict}

                @write("level", unit="1", limit=Limit(min=0, max=1, source="vendor_doc", ref="sim.md:1"))
                def set_level(self, value):
                    self.native["level"] = value
        ''')})
        with self.assertRaises(LoadError) as caught:
            load(directory, backend="hardware", allow_hardware=True, state_dir=support.temp_dir(self))
        self.assertEqual(caught.exception.reason, "no_hardware_backend")
        server = load(directory)
        self.addCleanup(close_server, server)
        [device] = server.devices.values()
        self.assertEqual((device.device_id, device.mode), ("mhs://localhost/sim", "simulated"))
        self.assertEqual(device.fidelity["engine"], "analytic")
        self.assertIsNone(device.models)


class LoaderTests(unittest.TestCase):
    def test_not_a_driver_directory(self) -> None:
        with self.assertRaises(LoadError) as caught:
            load(support.temp_dir(self))
        self.assertEqual(caught.exception.reason, "not_found")

    def test_one_driver_class_or_DRIVER(self) -> None:
        two = DRIVER_PY.format(risk="R2") + textwrap.dedent('''
            class Second(Bath):
                device_id = "lab/second"
        ''')
        directory = package(self, extra={"driver.py": two})
        with self.assertRaises(DriverDefinitionError):
            driver_class(directory)
        chosen = package(self, extra={"driver.py": two + "\nDRIVER = Second\n"})
        self.assertEqual(driver_class(chosen).__name__, "Second")

    def test_import_errors_are_definition_errors(self) -> None:
        directory = package(self, extra={"driver.py": "import not_a_module_anywhere\n"})
        with self.assertRaises(DriverDefinitionError) as caught:
            load(directory)
        self.assertIn("cannot be imported", str(caught.exception))

    def test_a_changed_file_is_imported_again(self) -> None:
        directory = package(self)
        first = driver_class(directory)
        (directory / "fake.py").write_text(FAKE_PY + "\nCHANGED = True\n", encoding="utf-8")
        second = driver_class(directory)
        self.assertIsNot(first, second)
        # A file inside a subpackage counts too.
        support.write_package(directory / "helpers", {"__init__.py": "", "units.py": "SCALE = 1\n"})
        third = driver_class(directory)
        self.assertIsNot(second, third)
        (directory / "helpers" / "units.py").write_text("SCALE = 2\n", encoding="utf-8")
        self.assertIsNot(third, driver_class(directory))
        self.assertIs(driver_class(directory), driver_class(directory))

    def test_read_lock_validates(self) -> None:
        document, problems = read_lock(package(self))
        self.assertEqual(problems, [])
        self.assertEqual(document["authored_by"]["kind"], "model")
        _document, problems = read_lock(package(self, lock={"package_id": "x"}))
        self.assertTrue(problems)


class AdapterManifestTests(unittest.TestCase):
    def manifest(self, mode: str = "simulated") -> dict:
        device = {
            "mhs_version": "1.0", "device_id": "mhs://localhost/json/bath", "instance_id": "01JB2C3D4E5F6G7H8J9KAMBNCP",
            "display_name": "JSON bath", "mode": mode,
            "resources": [{"resource_id": "bath", "kind": "thermal.zone", "state_schema": {
                "type": "object", "properties": {"setpoint": {"type": "number", "x-mhs-unit": "Cel"}},
                "additionalProperties": False}}],
            "capabilities": [{"capability_id": "cap.device.configure.v1", "resource": "bath",
                              "limits": {"setpoint": {"min": 0, "max": 80, "source": "vendor_doc", "ref": "m.pdf:1"}}}],
            "safety": {"risk_class": "R1", "estop": {"kind": "software", "latching": True},
                       "safe_state": {"description": "idle", "achieved_by": []}},
        }
        if mode == "simulated":
            device["fidelity"] = dict(FAKE_FIDELITY)
        return {
            "mhs_adapter": "1.0", "adapter_id": "com.example.json-bath", "family": "python-object",
            "source": {"repo": "https://github.com/example/bath", "license": "MIT"},
            "runtime": {"kind": "python"},
            "devices": [device],
            "bridges": [{"bridge_id": "bath", "kind": "python-object", "config": {
                "target": "tests.driver.support:FakeBath", "factory": {"kind": "class"},
                "writes": {"bath": {"params": {"setpoint": {"native": "setpoint", "invoke": "set"}}}},
                "reads": {"bath": {"fields": {"setpoint": "setpoint"}}}}}],
        }

    def write(self, document: dict) -> Path:
        path = support.temp_dir(self) / "mhs-adapter.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_python_object_adapter_json_is_served_strictly(self) -> None:
        server = load(self.write(self.manifest()))
        self.addCleanup(close_server, server)
        self.assertIs(server.strict, True)
        client = support.Client(server)
        self.assertEqual(client.write({"setpoint": 30})["status"], "completed")
        self.assertEqual(support.code(client.write({"setpoint": 81})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(client.read()["state"]["setpoint"], 30)

    def test_simulated_manifest_has_no_hardware_backend(self) -> None:
        path = self.write(self.manifest())
        with self.assertRaises(LoadError) as caught:
            load(path, backend="hardware", allow_hardware=True, state_dir=support.temp_dir(self))
        self.assertEqual(caught.exception.reason, "no_hardware_backend")
        with self.assertRaises(LoadError) as caught:
            load(path, backend="real")
        self.assertEqual(caught.exception.reason, "backend_unknown")
        server = load(path, backend="sim")
        self.addCleanup(close_server, server)

    def test_hardware_manifest_has_no_fake(self) -> None:
        path = self.write(self.manifest(mode="hardware"))
        with self.assertRaises(LoadError) as caught:
            load(path)
        self.assertEqual(caught.exception.reason, "no_fake_backend")
        with self.assertRaises(LoadError) as caught:
            load(path, backend="hardware")
        self.assertEqual(caught.exception.reason, "hardware_not_allowed")

    def test_invalid_document_and_unsupported_bridge(self) -> None:
        with self.assertRaises(LoadError) as caught:
            load(self.write({"mhs_adapter": "1.0"}))
        self.assertEqual(caught.exception.reason, "adapter_invalid")
        document = self.manifest()
        document["bridges"][0]["kind"] = "ros2"
        with self.assertRaises(LoadError) as caught:
            load(self.write(document))
        self.assertEqual(caught.exception.reason, "bridge_unsupported")

    def test_driver_bridge_points_at_a_driver_package(self) -> None:
        directory = package(self)
        document = self.manifest()
        document["bridges"] = [{"bridge_id": "driver", "kind": "driver", "config": {"path": "."}}]
        (directory / "mhs-adapter.json").write_text(json.dumps(document), encoding="utf-8")
        server = load(directory / "mhs-adapter.json")
        self.addCleanup(close_server, server)
        self.assertEqual(list(server.devices), ["mhs://localhost/lab/bath/fake"])

    def test_driver_bridge_must_name_a_driver_directory(self) -> None:
        # config.path "." next to the mhs-adapter.json itself would load that file again (verifier probe_loop).
        document = self.manifest()
        document["bridges"] = [{"bridge_id": "driver", "kind": "driver", "config": {"path": "."}}]
        for path in (self.write(document), self.write(document).parent):
            with self.subTest(path=path.name):
                with self.assertRaises(LoadError) as caught:
                    load(path)
                self.assertEqual(caught.exception.reason, "adapter_invalid")
                self.assertIn("driver directory", str(caught.exception))

    def transport_bridge(self, kind: str, transport: dict) -> dict:
        reads = {"bath": {"fields": {"setpoint": {"query": "SETP?", "parse": {"kind": "float"}}}}}
        writes = {"bath": {"params": {"setpoint": {"write": "SETP {value:g}"}}}}
        return {"bridge_id": f"bath-{kind}", "kind": kind, "config": dict(transport, timeout_s=0.2, reads=reads,
                                                                          writes=writes)}

    def test_a_simulated_device_never_drives_a_physical_transport(self) -> None:
        # Verifier probe_adapter_scpi_sim: a simulated label on a real host, port or VISA resource.
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(5)
        listener.setblocking(False)
        self.addCleanup(listener.close)
        port = listener.getsockname()[1]
        transports = {"scpi": {"host": "127.0.0.1", "port": port},
                      "scpi-visa": {"visa_resource": f"TCPIP0::127.0.0.1::{port}::SOCKET"},
                      "serial": {"port": "/dev/ttyMHS-test"}}
        hardware = {"backend": "hardware", "allow_hardware": True, "state_dir": support.temp_dir(self)}
        for kind, transport in transports.items():
            simulated = self.manifest()
            simulated["bridges"] = [self.transport_bridge(kind, transport)]
            # Also next to a hardware device, under the hardware rules: the simulated label is still false.
            mixed = self.manifest(mode="hardware")
            lockin = copy.deepcopy(simulated["devices"][0])
            lockin["device_id"] = "mhs://localhost/json/lockin"
            mixed["devices"].append(lockin)
            mixed["bridges"].append(self.transport_bridge(kind, transport))
            for label, document, options in (("fake", simulated, {}), ("sim", simulated, {"backend": "sim"}),
                                             ("hardware", simulated, hardware), ("mixed", mixed, hardware)):
                with self.subTest(kind=kind, case=label):
                    with self.assertRaises(LoadError) as caught:
                        load(self.write(document), **options)
                    self.assertEqual(caught.exception.reason, "no_fake_backend")
                    self.assertIn("physical transport", str(caught.exception))
        with self.assertRaises(BlockingIOError):
            connection, _address = listener.accept()
            connection.close()

    def test_strict_refusal_comes_before_any_bridge_is_built(self) -> None:
        # Verifier probe_adapter_risk_mark: R1 declared under the R2 floor of cap.thermal.setpoint.v1.
        marker = support.temp_dir(self) / "constructed"
        document = self.manifest(mode="hardware")
        device = document["devices"][0]
        device["capabilities"].append({"capability_id": "cap.thermal.setpoint.v1", "resource": "bath", "limits": {
            name: {"min": 0, "max": 80, "source": "vendor_doc", "ref": "m.pdf:1"}
            for name in ("target_temperature", "rate", "tolerance")}})
        device["safety"]["estop"] = {"kind": "both", "latching": True, "physical_ref": "front panel stop"}
        config = document["bridges"][0]["config"]
        config.update({"target": "tests.driver.support:marking_bath",
                       "factory": {"kind": "factory", "kwargs": {"marker": str(marker)}},
                       "capabilities": {"cap.thermal.setpoint.v1": {
                           "resource": "bath", "native": "set_pump", "invoke": "call", "concurrency": "exclusive",
                           "timeout_ms": 1000, "args": {"value": {"from": "input.target_temperature",
                                                                  "type": "number"}}}}})
        path = self.write(document)
        (path.parent / "driver.lock.json").write_text(json.dumps(support.lock_document(kind="human")),
                                                      encoding="utf-8")
        with self.assertRaises(DriverDefinitionError) as caught:
            load(path, backend="hardware", allow_hardware=True, state_dir=support.temp_dir(self))
        self.assertIn("risk-floor", {item.rule for item in caught.exception.findings})
        self.assertFalse(marker.exists())


class TemplateTests(unittest.TestCase):
    def test_every_template_kind_renders_with_a_valid_lock(self) -> None:
        for kind in scaffold.KINDS:
            with self.subTest(kind=kind):
                values = scaffold.default_values(kind, class_name="Thing", device_id="thing")
                files = scaffold.render(kind, values)
                self.assertIn("driver.py", files)
                self.assertIn("test_driver.py", files)
                directory = support.write_package(support.temp_dir(self) / kind, files)
                document, problems = read_lock(directory)
                self.assertEqual(problems, [])
                self.assertEqual(document["sdk_version"], _ids.SDK_VERSION)
                compile(files["driver.py"], f"{kind}/driver.py", "exec")

    def test_fake_backed_templates_load(self) -> None:
        for kind in ("direct", "python-object", "serial", "scpi"):
            with self.subTest(kind=kind):
                files = scaffold.render(kind, scaffold.default_values(kind, class_name="Thing", device_id=f"t-{kind}"))
                directory = support.write_package(support.temp_dir(self) / kind, files)
                server = load(directory)
                self.addCleanup(close_server, server)
                [device] = server.devices.values()
                self.assertEqual(device.mode, "simulated")
                self.assertIn("status", device.bridge.read(device.resources[0].resource_id))
                self.assertEqual(list(directory.rglob("__pycache__")), [])

    def test_missing_placeholder_fails(self) -> None:
        with self.assertRaises(KeyError):
            scaffold.render("direct", {"class_name": "X"})
        with self.assertRaises(ValueError):
            scaffold.render("unknown-family", scaffold.default_values())


if __name__ == "__main__":
    unittest.main()
