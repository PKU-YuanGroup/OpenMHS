"""Config-only family drivers over the bundled bridges (python-object, serial, SCPI, Gymnasium, MuJoCo)."""

from __future__ import annotations

import json
import shutil
import socket
import tempfile
import types
import unittest
from pathlib import Path

from mhs.bridge.serial import FakeSerial
from mhs.driver import (
    Action,
    DriverDefinitionError,
    Field,
    GymnasiumDriver,
    Limit,
    MujocoDriver,
    PythonObjectDriver,
    ScpiDriver,
    SerialDriver,
    build_manifest,
    close_server,
    read,
)
from mhs.driver.build import strict_findings
from mhs.errors import MHSError
from mhs.schema import default_store, validate

from tests.bridges import support as bridge_support
from tests.driver import support
from tests.driver.support import code


def binding(manifest, capability_id):
    return next(item for item in manifest["capabilities"] if item["capability_id"] == capability_id)


class AsyncBathDriver(PythonObjectDriver):
    device_id, device_kind, mode, risk = "lab/async-bath", "thermal.zone", "hardware", "R2"
    native = "julabo.julabo:JulaboCF"
    backends = {"fake": bridge_support.AsyncBath}
    safe_state = "circulation stopped"
    estop_physical_ref = "front panel stop"
    native_setup = "setup"
    parameters = {
        "temperature": Field("number", unit="Cel"),
        "setpoint": Field("number", unit="Cel", writable=True,
                          limit=Limit(min=-20, max=150, source="vendor_doc", ref="manual.pdf:9")),
    }
    reads = {"temperature": {"native": "bath_temperature", "invoke": "await"}}
    writes = {"setpoint": {"native": "set_point_1", "invoke": "await"}}
    commands = {"cap.thermal.setpoint.v1": {
        "native": "set_point_1", "invoke": "await", "args": {"value": {"from": "input.target_temperature"}},
        "result": {"map": {"setpoint": "output.$"}}, "concurrency": "exclusive", "timeout_ms": 5000}}
    actions = {"cap.thermal.setpoint.v1": Action(name="set_temperature", input={
        "target_temperature": Limit(min=-20, max=150, source="vendor_doc", ref="manual.pdf:10")})}
    safety_bindings = {"estop": {"native": "stop", "invoke": "await"},
                       "interlocks": [{"id": "lid", "native": "lid_closed", "invoke": "get",
                                       "blocks": ["cap.thermal.setpoint.v1"]}]}


class PythonObjectFamilyTests(unittest.TestCase):
    def test_manifest_and_strictness(self) -> None:
        manifest = build_manifest(AsyncBathDriver)
        self.assertEqual(default_store().validate(manifest, "device.schema.json"), [])
        self.assertEqual(binding(manifest, "cap.thermal.setpoint.v1")["x-mhs-name"], "set_temperature")
        self.assertEqual(manifest["safety"]["estop"]["native"], "stop")
        self.assertEqual(manifest["safety"]["interlocks"],
                         [{"id": "lid", "required_for": ["cap.thermal.setpoint.v1"], "source": "hardware"}])
        self.assertEqual(strict_findings(AsyncBathDriver), [])

    def test_served_end_to_end(self) -> None:
        driver = AsyncBathDriver(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        driver.native.lid_closed = True
        self.assertEqual(client.read()["state"], {"temperature": 22.0})
        self.assertEqual(client.write({"setpoint": 30})["status"], "completed")
        self.assertEqual(code(client.write({"setpoint": 300})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        receipt = client.command("cap.thermal.setpoint.v1", {"target_temperature": 40})
        self.assertEqual((receipt["status"], receipt["output"]), ("completed", {"setpoint": 40.0}), receipt)
        driver.native.lid_closed = False
        self.assertEqual(code(client.command("cap.thermal.setpoint.v1", {"target_temperature": 41})),
                         "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertTrue(driver.native.setup_done)
        estop = client.estop()
        self.assertEqual(estop["output"]["estop"], "engaged")
        self.assertTrue(driver.native.stopped)

    def test_configuration_errors(self) -> None:
        class Broken(PythonObjectDriver):
            device_id, device_kind = "broken", "thermal.zone"
            parameters = {"setpoint": Field("number", unit="Cel", writable=True), "mode": Field("string")}
            commands = {"x-cap.example.pulse.v1": {"native": "pulse", "concurrency": "exclusive"}}

        with self.assertRaises(DriverDefinitionError) as caught:
            Broken.driver_model()
        text = "\n".join(caught.exception.problems)
        self.assertIn("writable but writes has no entry", text)
        self.assertIn("read-only parameter 'mode' has no entry in reads", text)
        self.assertIn("x-cap command needs actions", text)

        class BadBridge(PythonObjectDriver):
            device_id, device_kind = "bad-bridge", "thermal.zone"
            parameters = {"t": Field("number", unit="Cel")}
            reads = {"t": {"native": "t", "invoke": "teleport"}}

        with self.assertRaises(DriverDefinitionError) as caught:
            BadBridge.driver_model()
        self.assertIn("python-object configuration is invalid", str(caught.exception))

    def test_family_drivers_are_config_only(self) -> None:
        class Mixed(PythonObjectDriver):
            device_id, device_kind = "mixed", "thermal.zone"

            @read("t", unit="Cel")
            def t(self):
                return 1.0

        with self.assertRaises(DriverDefinitionError) as caught:
            Mixed.driver_model()
        self.assertIn("family drivers are config-only", str(caught.exception))

    def test_without_a_native_stop_the_latch_is_software_only(self) -> None:
        class NoStop(PythonObjectDriver):
            device_id, device_kind, mode = "no-stop", "thermal.zone", "hardware"
            backends = {"fake": bridge_support.AsyncBath}
            parameters = {"temperature": Field("number", unit="Cel"),
                          "setpoint": Field("number", unit="Cel", writable=True,
                                            limit=Limit(min=0, max=90, source="vendor_doc", ref="m.pdf:1"))}
            reads = {"temperature": {"native": "bath_temperature", "invoke": "await"}}
            writes = {"setpoint": {"native": "set_point_1", "invoke": "await"}}

        driver = NoStop(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.estop()["output"]["estop"], "software_only")
        self.assertIsNone(build_manifest(NoStop)["safety"]["estop"]["native"])


class Psu(SerialDriver):
    device_id, device_kind, mode, risk = "lab/psu", "instrument.psu", "hardware", "R1"
    safe_state = "output off"
    parameters = {
        "voltage": Field("number", unit="V", writable=True,
                         limit=Limit(min=0, max=30, source="vendor_doc", ref="psu.pdf:3")),
        "current": Field("number", unit="A"),
    }
    reads = {"voltage": {"command": "VOLT?", "parse": {"kind": "float"}},
             "current": {"command": "CURR?", "parse": {"kind": "float"}}}
    writes = {"voltage": {"command": "VOLT {value}", "type": "number"}}
    commands = {"x-cap.example.output.v1": {"command": "OUTP {on}", "response": False,
                                           "args": {"on": {"from": "input.on", "type": "integer"}}}}
    actions = {"x-cap.example.output.v1": Action(
        name="output",
        input={"on": Field("integer", limit=Limit(allowed=[0, 1], source="vendor_doc", ref="psu.pdf:5"))},
        output={"command": Field("string"), "response": Field("string", nullable=True, required=False)})}
    safety_bindings = {"estop": {"command": "OUTP 0"}}
    backends = {"fake": lambda: FakeSerial({"VOLT?": "1.5\n", "CURR?": "0.1\n"})}


class SerialFamilyTests(unittest.TestCase):
    def test_served_end_to_end(self) -> None:
        driver = Psu(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.read()["state"], {"voltage": 1.5, "current": 0.1})
        self.assertEqual(client.write({"voltage": 3})["status"], "completed")
        self.assertEqual(code(client.write({"voltage": 31})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(client.command("x-cap.example.output.v1", {"on": 1})["status"], "completed")
        self.assertEqual(code(client.command("x-cap.example.output.v1", {"on": 2})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        client.estop()
        written = [line.decode().strip() for line in driver.native.written]
        self.assertIn("VOLT 3", written)
        self.assertNotIn("VOLT 31", written)
        self.assertIn("OUTP 0", written)
        self.assertEqual(written.index("OUTP 1") < written.index("OUTP 0"), True)
        self.assertEqual(strict_findings(Psu), [])


class FakeLockin:
    """A stateful SCPI transport (write + read), answering from its own state."""

    def __init__(self) -> None:
        self.frequency = 1000.0
        self.written: list[str] = []
        self._pending: list[str] = []

    def write(self, line: str, *, timeout_s: float | None = None) -> None:
        self.written.append(line)
        if line == "*IDN?":
            self._pending.append("Stanford_Research_Systems,SR860,003456,v1.47")
        elif line == "FREQ?":
            self._pending.append(f"{self.frequency:g}")
        elif line.startswith("FREQ "):
            self.frequency = float(line.split()[1])

    def read(self, *, timeout_s: float | None = None) -> str:
        if not self._pending:
            raise TimeoutError("nothing pending")
        return self._pending.pop(0)

    def query(self, line: str, *, timeout_s: float | None = None) -> str:
        self.write(line)
        return self.read()


class Lockin(ScpiDriver):
    device_id, device_kind, mode, risk = "lab/sr860", "instrument.lockin", "hardware", "R1"
    native = "srsinst.sr860:SR860"
    safe_state = "sine output at minimum amplitude"
    idn = {"expect": "^Stanford_Research_Systems,SR860"}
    parameters = {"frequency": Field("number", unit="Hz", writable=True,
                                     limit=Limit(min=0.001, max=500000, source="vendor_doc", ref="sr860.pdf:112"))}
    reads = {"frequency": {"query": "FREQ?", "parse": {"kind": "float"}}}
    writes = {"frequency": {"write": "FREQ {value:g}", "type": "number"}}
    safety_bindings = {"estop": {"write": "SLVL 0"}}
    backends = {"fake": FakeLockin}


class ScpiFamilyTests(unittest.TestCase):
    def test_served_end_to_end(self) -> None:
        driver = Lockin(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.read()["state"], {"frequency": 1000.0})
        self.assertEqual(client.write({"frequency": 2000})["status"], "completed")
        self.assertEqual(client.read()["state"], {"frequency": 2000.0})
        self.assertEqual(code(client.write({"frequency": 600000})), "MHS.SAFETY.ENVELOPE_VIOLATION")
        client.estop()
        self.assertIn("SLVL 0", driver.native.written)
        self.assertNotIn("FREQ 600000", driver.native.written)
        self.assertEqual(build_manifest(Lockin)["safety"]["estop"]["native"], "SLVL 0")

    def test_transcript_fake(self) -> None:
        directory = support.temp_dir(self)
        (directory / "session.json").write_text(
            '{"transcript": "1.0", "exchanges": [{"send": "*IDN?", "recv": "Stanford_Research_Systems,SR860,1,1"},'
            ' {"send": "FREQ?", "recv": "1000"}]}', encoding="utf-8")

        class Replay(Lockin):
            backends = {}
            transcript = "session.json"

        driver = Replay(backend="fake", base_dir=directory)
        self.addCleanup(driver.close)
        self.assertEqual(driver.read("main"), {"frequency": 1000.0})


class FakeViewTransportTests(unittest.TestCase):
    """A fake view never falls back to the configured port or host (verifier probe_family)."""

    def listener(self) -> socket.socket:
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(5)
        server.setblocking(False)
        self.addCleanup(server.close)
        return server

    def assertNoConnection(self, server: socket.socket) -> None:
        try:
            connection, _address = server.accept()
        except BlockingIOError:
            return
        connection.close()
        self.fail("the fake view connected to the configured host")

    def assertNoTransport(self, driver) -> None:
        self.addCleanup(driver.close)
        with self.assertRaises(MHSError) as caught:
            driver.open()
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")
        self.assertIn("produced no transport", str(caught.exception))

    def test_scpi_fake_without_a_transport_is_refused(self) -> None:
        server = self.listener()

        class Networked(Lockin):
            host, port, timeout_s = "127.0.0.1", server.getsockname()[1], 0.2
            backends = {"fake": lambda **_options: None}

        self.assertNoTransport(Networked(backend="fake"))
        self.assertNoTransport(Networked(backend="fake", native=None))
        self.assertNoConnection(server)

    def test_scpi_fake_ignores_host_options(self) -> None:
        server = self.listener()

        class Optioned(Lockin):
            backends = {"fake": lambda **_options: FakeLockin()}

        driver = Optioned(backend="fake", options={"host": "127.0.0.1", "port": server.getsockname()[1]})
        self.addCleanup(driver.close)
        self.assertEqual(driver.read("main"), {"frequency": 1000.0})
        self.assertFalse({"host", "port", "visa_resource"} & set(driver.inner.config))
        self.assertNoConnection(server)

    def test_serial_fake_without_a_transport_is_refused(self) -> None:
        class Wired(Psu):
            port = "/dev/ttyUSB0"
            backends = {"fake": lambda **_options: None}

        self.assertNoTransport(Wired(backend="fake"))

        class Optioned(Psu):
            backends = {"fake": lambda **_options: FakeSerial({"VOLT?": "1.5\n", "CURR?": "0.1\n"})}

        driver = Optioned(backend="fake", options={"port": "/dev/ttyUSB0"})
        self.addCleanup(driver.close)
        self.assertEqual(driver.read("main"), {"voltage": 1.5, "current": 0.1})
        self.assertNotIn("port", driver.inner.config)

    def test_python_object_backend_must_produce_an_object(self) -> None:
        class Empty(AsyncBathDriver):
            backends = {"fake": lambda **_options: None}

        driver = Empty(backend="fake")
        self.addCleanup(driver.close)
        with self.assertRaises(MHSError) as caught:
            driver.open()
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_family_backend_names_follow_the_vocabulary(self) -> None:
        class Renamed(Lockin):
            backends = {"real": FakeLockin}

        with self.assertRaises(DriverDefinitionError) as caught:
            Renamed.driver_model()
        self.assertIn("backend name 'real'", str(caught.exception))


class CartPole(GymnasiumDriver):
    device_id = "gym/cartpole"
    env_id = "CartPole-v1"
    backends = {"fake": lambda: bridge_support.FakeWrapper(bridge_support.FakeCartPole(terminate_after=8))}
    safe_state = "simulation paused"


class GymnasiumFamilyTests(unittest.TestCase):
    def test_contract_is_derived_from_the_spaces(self) -> None:
        driver = CartPole(backend="fake")
        self.addCleanup(driver.close)
        manifest = build_manifest(driver)
        self.assertEqual(default_store().validate(manifest, "device.schema.json"), [])
        self.assertEqual(manifest["mode"], "simulated")
        self.assertEqual(manifest["device_id"], "mhs://localhost/gym/cartpole")
        self.assertNotIn("models", manifest)
        self.assertEqual(manifest["fidelity"]["engine"], "gymnasium:CartPole-v1")
        self.assertEqual(manifest["fidelity"]["determinism"], {"kind": "seeded", "seed_control": "parameter"})
        self.assertFalse(manifest["fidelity"]["snapshot_restore"])
        step = binding(manifest, "cap.world.step.v1")
        self.assertEqual(step["x-mhs-name"], "step")
        self.assertIn("action", step["input_schema"]["properties"])
        self.assertEqual(sorted(item["capability_id"] for item in manifest["capabilities"]),
                         ["cap.world.reset.v1", "cap.world.seed.v1", "cap.world.step.v1"])
        with self.assertRaises(DriverDefinitionError):
            CartPole.driver_model()  # the contract needs the environment

    def test_served_end_to_end(self) -> None:
        driver = CartPole(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.command("cap.world.reset.v1", {"seed": 3})["status"], "completed")
        step = client.command("cap.world.step.v1", {"action": {"index": 1}, "ticks": 5})
        self.assertEqual(step["status"], "completed", step)
        self.assertEqual(step["output"]["tick"], 5)
        refused = client.command("cap.world.step.v1", {"action": {"index": 2}, "ticks": 1})
        self.assertEqual(code(refused), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(client.read()["state"]["tick"], 5)

    def test_limits_derived_from_the_fake_backend_claim_no_upstream_source(self) -> None:
        # Wave D: the fake's (often placeholder) bounds were published as upstream_code <env_id>:action_space.
        driver = CartPole(backend="fake")
        self.addCleanup(driver.close)
        rule = binding(build_manifest(driver), "cap.world.step.v1")["limits"]["action.index"]
        self.assertEqual(rule, {"min": 0, "max": 1, "ref": "action_space of the fake backend CartPole.<lambda>"})
        step = next(item for item in driver._model.bindings if item.capability_id == "cap.world.step.v1")
        self.assertEqual(step.derived_limits, ("action.index",))
        self.assertEqual([item for item in strict_findings(driver, backend="fake") if item.refuse], [])

    def test_action_space_ref_makes_the_derived_limits_upstream_code(self) -> None:
        class Cited(CartPole):
            action_space_ref = "gymnasium/envs/classic_control/cartpole.py:151"

        driver = Cited(backend="fake")
        self.addCleanup(driver.close)
        rule = binding(build_manifest(driver), "cap.world.step.v1")["limits"]["action.index"]
        self.assertEqual((rule["min"], rule["max"], rule["source"], rule["ref"]),
                         (0, 1, "upstream_code", "gymnasium/envs/classic_control/cartpole.py:151"))
        self.assertNotIn("reason", rule)

    def test_action_space_ref_must_cite_a_path_and_line(self) -> None:
        for bad in ("cartpole.py", "CartPole-v1:action_space", "/abs/cartpole.py:3", "../cartpole.py:3", 151):
            with self.subTest(bad=bad):
                class Bad(CartPole):
                    action_space_ref = bad

                with self.assertRaises(DriverDefinitionError) as caught:
                    Bad(backend="fake")
                self.assertIn("action_space_ref must cite", str(caught.exception))

    def test_fidelity_override_and_mode(self) -> None:
        class Pendulum(CartPole):
            fidelity = {"fidelity_level": "F1", "gaps": ["no actuator dynamics"]}

        driver = Pendulum(backend="fake")
        self.addCleanup(driver.close)
        fidelity = build_manifest(driver)["fidelity"]
        self.assertEqual((fidelity["fidelity_level"], fidelity["gaps"]), ("F1", ["no actuator dynamics"]))
        with self.assertRaises(DriverDefinitionError):
            CartPole(backend="hardware")


def fake_mujoco_module() -> types.SimpleNamespace:
    module = bridge_support.fake_mujoco()

    class MjModel:
        @staticmethod
        def from_xml_string(_xml: str) -> bridge_support.FakeMjModel:
            return bridge_support.FakeMjModel()

        @staticmethod
        def from_xml_path(_path: str) -> bridge_support.FakeMjModel:
            return bridge_support.FakeMjModel()

    module.MjModel = MjModel
    module.MjData = bridge_support.FakeMjData
    return module


class Pendulums(MujocoDriver):
    device_id = "mujoco/pendulums"
    model_xml = "<mujoco/>"
    backends = {"fake": fake_mujoco_module}
    safe_state = "simulation paused"


class MujocoFamilyTests(unittest.TestCase):
    def test_ctrl_limits_come_from_the_model(self) -> None:
        driver = Pendulums(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        step = binding(server.devices[client.device_id].manifest(), "cap.world.step.v1")
        self.assertEqual(step["limits"]["action.ctrl"]["max"], [1.0, 0.5])
        self.assertEqual(server.devices[client.device_id].fidelity["timestep_ms"], 2.0)
        ok = client.command("cap.world.step.v1", {"action": {"ctrl": [0.5, 0.1]}, "ticks": 2})
        self.assertEqual(ok["status"], "completed", ok)
        refused = client.command("cap.world.step.v1", {"action": {"ctrl": [0.5, 0.6]}, "ticks": 1})
        self.assertEqual(code(refused), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(refused["error"]["details"]["path"], "action.ctrl[1]")

    def test_the_world_state_matches_the_state_schema_the_device_publishes(self) -> None:
        # Gate G6 reads the state and validates it against this schema; the wA MuJoCo cards all failed there (READ_INVALID).
        driver = Pendulums(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.command("cap.world.step.v1", {"action": {"ctrl": [0.5, 0.1]}, "ticks": 2})["status"], "completed")
        read = client.read()
        state = read.get("state", read)
        schema = client.device()["resources"][0]["state_schema"]
        self.assertEqual(validate(state, schema), [], state)
        self.assertEqual((state["tick"], state["timestep_ms"], len(state["ctrl"])), (2, 2.0, 2))

    def test_the_manifest_names_the_model_as_its_clone_does(self) -> None:
        # The ctrl limit's ref was the absolute model path, which put the build host's home directory into 40 reference files.
        root = Path(tempfile.mkdtemp(prefix="mujoco-family-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "robots" / "acme" / "arm" / ".git").mkdir(parents=True)
        (root / "robots" / "acme" / "arm" / "models").mkdir()
        (root / "robots" / "acme" / "arm" / "models" / "arm.xml").write_text("<mujoco/>", encoding="utf-8")
        (root / "MHS" / "drivers" / "robots" / "acme__arm").mkdir(parents=True)

        class Arm(MujocoDriver):
            device_id = "mujoco/arm"
            model_path = "../../../../robots/acme/arm/models/arm.xml"
            backends = {"fake": fake_mujoco_module}
            safe_state = "simulation paused"

        driver = Arm(backend="fake", base_dir=root / "MHS" / "drivers" / "robots" / "acme__arm")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        step = binding(server.devices[client.device_id].manifest(), "cap.world.step.v1")
        self.assertEqual(step["limits"]["action.ctrl"]["ref"], "models/arm.xml:actuator_ctrlrange")
        self.assertNotIn(str(root), json.dumps(server.devices[client.device_id].manifest()))
        shutil.rmtree(root / "robots" / "acme" / "arm" / ".git")  # a sandbox copy without git: the path as the driver says
        self.assertEqual(Arm(backend="fake", base_dir=root / "MHS" / "drivers" / "robots" / "acme__arm")._model_name(),
                         "../../../../robots/acme/arm/models/arm.xml")

    def test_the_reset_publishes_only_described_inputs(self) -> None:
        # An empty reset schema made the catalogue class's undescribed fields the published ones (G8.NO_DESCRIPTION).
        driver = Pendulums(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        reset = next(cap for cap in client.device()["capabilities"] if cap["capability_id"] == "cap.world.reset.v1")
        properties = reset["input_schema"]["properties"]
        self.assertEqual(sorted(properties), ["seed"], "the MuJoCo reset takes no scenario and no options")
        self.assertIn("does not use", properties["seed"]["description"])
        self.assertEqual(client.command("cap.world.reset.v1", {"seed": 3})["status"], "completed")
        self.assertEqual(code(client.command("cap.world.reset.v1", {"scenario": "x"})), "MHS.CAPABILITY.INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
