"""Acceptance run of the AS7265x package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.

The ``As7265xNativePort*`` cases drive the package's own Python 3 port (``native.py``) with a controlled
virtual-register bus through the stock endpoint.  The bus implements the status/write/read handshake of
``spectrometer.py:29-83`` and the device select register 0x4F; it is test equipment, not a hardware emulator, and
nothing here opens an SMBus, imports the clone or claims a hardware run.
"""

import importlib
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import Cancelled, DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


def _port_module():
    """The package's native.py, imported through the loaded driver's package (connect() alone imports smbus)."""
    cls = type(load_driver(HERE, backend="fake"))
    return importlib.import_module(cls.__module__.rsplit(".", 1)[0] + ".native")


class RegisterBus:
    """Controlled AS7265x virtual-register handshake (spectrometer.py:29-83) with optional holds and faults."""

    def __init__(self, port):
        self.port = port
        self.guard = threading.Lock()
        self.selected = 0
        self.pending = None          # ("read" | "write", register, owner thread)
        self.values = {}             # (device index, register) -> byte
        self.writes = []             # (device index, register, value) of completed virtual-register writes
        self.interleaved = 0         # protocol steps of one thread inside another thread's pending transaction
        self.hold = None             # callable(kind, register, value) -> threading.Event to wait on, or None
        self.fail = None             # callable(kind, register, value) -> exception to raise, or None
        self.stuck_tx = False        # TX_VALID never clears

    def _gate(self, kind, register, value=None):
        if self.fail is not None:
            error = self.fail(kind, register, value)
            if error is not None:
                raise error
        if self.hold is not None:
            event = self.hold(kind, register, value)
            if event is not None and not event.wait(10):
                raise AssertionError("the test must release its controlled bus hold")

    def read_byte_data(self, address, register):
        assert address == self.port.I2C_ADDR
        with self.guard:
            pending = self.pending
        if register == self.port.STATUS_REG:
            status = self.port.TX_VALID if self.stuck_tx else 0
            if pending is not None and pending[0] == "read":
                status |= self.port.RX_VALID
            return status
        assert register == self.port.READ_REG and pending is not None and pending[0] == "read"
        self._gate("data", pending[1])
        with self.guard:
            if pending[2] is not threading.current_thread():
                self.interleaved += 1
            self.pending = None
            return self.values.get((self.selected, pending[1]), 0)

    def write_byte_data(self, address, register, value):
        assert address == self.port.I2C_ADDR and register == self.port.WRITE_REG
        with self.guard:
            pending = self.pending
        if pending is not None and pending[0] == "write":
            self._gate("write", pending[1], value)
            with self.guard:
                if pending[2] is not threading.current_thread():
                    self.interleaved += 1
                if pending[1] == 0x4F:  # DEVSEL (spectrometer.py:130)
                    self.selected = value
                else:
                    self.values[(self.selected, pending[1])] = value
                    self.writes.append((self.selected, pending[1], value))
                self.pending = None
            return
        self._gate("address", value & 0x7F)
        with self.guard:
            if pending is not None:
                self.interleaved += 1
            self.pending = ("write" if value & 0x80 else "read", value & 0x7F, threading.current_thread())

    def leds(self):
        return [self.values.get((index, 0x07), 0) & (0x09 if index == 0 else 0x08) for index in range(3)]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class As7265xCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_and_the_fake_defaults(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["board_present"], True)
        self.assertEqual(state["hardware_version"], [0x40, 0x01])
        self.assertEqual(state["temperatures"], [25, 26, 27])
        self.assertEqual(state["integration_time_register"], 10)
        self.assertEqual(state["gain"], 0)
        self.assertEqual(state["led_drive_current"], 0)
        self.assertEqual(state["blue_led"], False)
        self.assertEqual(state["shutter_leds"], [False, False, False])

    def test_the_configuration_reaches_the_fake(self) -> None:
        client = self.serve()
        result = self.configure(client, integration_time_register=120, gain=2, led_drive_current=3,
                                blue_led=True, shutter_leds=[True, False, True])
        self.assertEqual(result["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["integration_time_register"], 120)
        self.assertEqual(state["gain"], 2)
        self.assertEqual(state["led_drive_current"], 3)
        self.assertEqual(state["blue_led"], True)
        self.assertEqual(state["shutter_leds"], [True, False, True])

    def test_the_allowed_sets_are_refused_outside(self) -> None:
        client = self.serve()
        for patch in ({"integration_time_register": 255}, {"integration_time_register": -1},
                      {"gain": 4}, {"led_drive_current": 4}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.state(client)["integration_time_register"], 10)

    def test_the_intensity_action(self) -> None:
        client = self.serve()
        brightest = client.invoke("cap.measure.intensity.v1", {}, **self.ids)
        self.assertEqual(brightest["status"], "completed")
        self.assertEqual(brightest["output"]["intensity"], 18.0)
        channel = client.invoke("cap.measure.intensity.v1", {"channel": "3"}, **self.ids)
        self.assertEqual(channel["output"]["intensity"], 3.0)
        refused = client.invoke("cap.measure.intensity.v1", {"channel": "19"}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_the_raw_and_calibrated_arrays(self) -> None:
        client = self.serve()
        result = client.invoke("x-cap.liamsgithub.read_spectrum.v1", {}, **self.ids)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["output"]["raw"]), 18)
        self.assertEqual(len(result["output"]["calibrated"]), 18)
        self.assertEqual(result["output"]["raw"][0], 100)
        self.assertEqual(result["output"]["calibrated"][-1], 18.0)

    def test_the_factory_reset_restores_the_fake_defaults(self) -> None:
        client = self.serve()
        self.configure(client, integration_time_register=120, gain=3)
        result = client.invoke("x-cap.liamsgithub.factory_reset.v1", {}, **self.ids)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["output"]["board_present"], True)
        state = self.state(client)
        self.assertEqual(state["integration_time_register"], 10)
        self.assertEqual(state["gain"], 0)

    def test_the_estop_turns_off_the_leds_and_latches(self) -> None:
        client = self.serve()
        self.configure(client, blue_led=True, shutter_leds=[True, True, True])
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertEqual(state["blue_led"], False)
        self.assertEqual(state["shutter_leds"], [False, False, False])
        refused = self.configure(client, blue_led=True)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_safe_state_action_also_turns_off_the_leds(self) -> None:
        client = self.serve()
        self.configure(client, blue_led=True, shutter_leds=[True, True, True])
        result = client.invoke("x-cap.liamsgithub.leds_off.v1", {}, **self.ids)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["output"], {"blue_led": False, "shutter_leds": [False, False, False]})
        self.assertEqual(self.state(client)["shutter_leds"], [False, False, False])

    def test_a_late_effectful_call_after_the_estop_is_refused_until_the_reset(self) -> None:
        driver = load_driver(HERE, backend="fake")
        driver.emergency_stop()
        with self.assertRaises(Cancelled):
            driver.set_blue_led(True)
        self.assertFalse(driver.blue_led())
        driver.release_fence()
        self.assertTrue(driver.set_blue_led(True))

    def test_reset_after_the_estop_restores_ordinary_configuration(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.configure(client, blue_led=True)["status"], "completed")
        self.assertEqual(self.state(client)["blue_led"], True)


class As7265xNativePortCases(unittest.TestCase):
    """The package's port over a controlled register bus, through the stock endpoint where a receipt matters."""

    def setUp(self) -> None:
        self.port = _port_module()
        self.bus = RegisterBus(self.port)
        for index in range(3):
            self.bus.values[(index, 0x07)] = 0x09 if index == 0 else 0x08   # every LED on
            self.bus.values[(index, 0x05)] = 10
            for offset, register in enumerate(range(0x08, 0x2C)):
                self.bus.values[(index, register)] = (index * 50 + offset) & 0xFF

    def serve(self, native):
        server = load(HERE, backend="fake", native=native)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_estop_switches_every_led_off_and_reads_them_back(self) -> None:
        client = self.serve(self.port.AS7265x(self.bus))
        receipt = client.estop("controlled responsive bus", deadline_ms=1000, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.bus.leds(), [0, 0, 0])
        self.assertEqual(self.bus.interleaved, 0)

    def test_a_permanently_busy_bus_ends_each_wait_on_the_host_bound(self) -> None:
        clock = [0.0]
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        self.bus.stuck_tx = True
        port = self.port.AS7265x(self.bus, poll_timeout_s=0.5, clock=lambda: clock[0], sleep=sleep)
        with self.assertRaises(TimeoutError):
            port.setBlueLED(False)
        self.assertLessEqual(len(sleeps), 11)
        self.assertLessEqual(clock[0], 0.55 + 1e-9)
        self.assertEqual(self.bus.writes, [])

    def test_a_held_bus_fails_the_estop_closed_and_keeps_the_latch(self) -> None:
        released = threading.Event()
        self.bus.hold = lambda kind, register, value: released if kind == "address" else None
        client = self.serve(self.port.AS7265x(self.bus, lock_timeout_s=0.2))
        try:
            receipt = client.estop("controlled held bus", deadline_ms=100, **self.ids)
            self.assertEqual(receipt["status"], "failed", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
            self.assertFalse(receipt["output"]["safe_state_achieved"])
            refused = client.invoke("cap.device.configure.v1", {"blue_led": True}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        finally:
            released.set()

    def test_a_stop_interleaved_with_a_measurement_keeps_every_device_coherent(self) -> None:
        port = self.port.AS7265x(self.bus)
        expected = []
        for index in range(3):
            for quad in [(0x14, 0x15, 0x16, 0x17), (0x18, 0x19, 0x1A, 0x1B), (0x1C, 0x1D, 0x1E, 0x1F),
                         (0x20, 0x21, 0x22, 0x23), (0x24, 0x25, 0x26, 0x27), (0x28, 0x29, 0x2A, 0x2B)]:
                expected.append(port.IEEE754toFloat([self.bus.values[(index, register)] for register in quad]))
        expected = port.reorderData(expected)
        reached, released = threading.Event(), threading.Event()

        def hold(kind, register, value):
            # Hold the measurement right after it read its first register of AS72652.
            if (kind == "data" and register == 0x15 and self.bus.selected == 1
                    and threading.current_thread().name == "measurement"):
                reached.set()
                return released
            return None

        result = {}
        self.bus.hold = hold
        worker = threading.Thread(target=lambda: result.setdefault("cal", port.readCAL()), name="measurement")
        worker.start()
        self.assertTrue(reached.wait(5))
        stopper = threading.Thread(target=lambda: [port.setBlueLED(False)]
                                   + [port.shutterLED(device, False) for device in ("AS72651", "AS72652",
                                                                                      "AS72653")],
                                   name="stop")
        stopper.start()
        time.sleep(0.05)
        self.assertTrue(stopper.is_alive(), "the stop waits for the one register transaction that is in flight")
        released.set()
        stopper.join(5)
        worker.join(5)
        self.assertFalse(stopper.is_alive() or worker.is_alive())
        self.assertEqual(self.bus.leds(), [0, 0, 0])
        self.assertEqual(self.bus.interleaved, 0)
        self.assertEqual(result["cal"], expected, "the measurement read every register from its own device")

    def test_the_estop_waits_for_an_led_write_already_at_the_device_and_confirms_off(self) -> None:
        for index in range(3):
            self.bus.values[(index, 0x07)] = 0
        reached, released = threading.Event(), threading.Event()

        def hold(kind, register, value):
            if kind == "write" and register == 0x07 and value & 0x01 and not reached.is_set():
                reached.set()
                return released
            return None

        self.bus.hold = hold
        client = self.serve(self.port.AS7265x(self.bus))
        outcome = {}
        writer = threading.Thread(target=lambda: outcome.setdefault(
            "write", client.invoke("cap.device.configure.v1", {"blue_led": True}, **self.ids)))
        writer.start()
        self.assertTrue(reached.wait(5))
        timer = threading.Timer(0.05, released.set)
        timer.start()
        receipt = client.estop("stop during an LED write", deadline_ms=1000, **self.ids)
        writer.join(5)
        timer.join(5)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.bus.leds(), [0, 0, 0], "the stop ran after the in-flight write and won")
        self.assertEqual(self.bus.interleaved, 0)

    def test_every_led_is_attempted_when_one_device_fails(self) -> None:
        def fail(kind, register, value):
            if kind in ("address", "write") and register == 0x07 and self.bus.selected == 0:
                return OSError("controlled I2C failure on AS72651")
            return None

        self.bus.fail = fail
        driver = load_driver(HERE, backend="fake", native=self.port.AS7265x(self.bus))
        with self.assertRaises(DriverFailed):
            driver.emergency_stop()
        self.assertEqual(self.bus.leds()[1:], [0, 0], "AS72652 and AS72653 were still switched off")

    def test_configuration_measurement_and_factory_reset_on_the_port(self) -> None:
        port = self.port.AS7265x(self.bus, sleep=lambda seconds: None)
        client = self.serve(port)
        done = client.invoke("cap.device.configure.v1", {"integration_time_register": 120, "gain": 2,
                                                         "led_drive_current": 3}, **self.ids)
        self.assertEqual(done["status"], "completed", done)
        for index in range(3):
            self.assertEqual(self.bus.values[(index, 0x05)], 120)
            self.assertEqual((self.bus.values.get((index, 0x04), 0) >> 4) & 0x03, 2)
            self.assertEqual((self.bus.values[(index, 0x07)] >> 4) & 0x03, 3)
        spectrum = client.invoke("x-cap.liamsgithub.read_spectrum.v1", {}, **self.ids)
        self.assertEqual(spectrum["status"], "completed", spectrum)
        raw = []
        for index in range(3):
            for high, low in [(0x08, 0x09), (0x0A, 0x0B), (0x0C, 0x0D), (0x0E, 0x0F), (0x10, 0x11), (0x12, 0x13)]:
                raw.append((self.bus.values[(index, high)] << 8) | self.bus.values[(index, low)])
        self.assertEqual(spectrum["output"]["raw"], port.reorderData(raw))
        reset = client.invoke("x-cap.liamsgithub.factory_reset.v1", {}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertIn((self.bus.selected, 0x04, 1), self.bus.writes)
        self.assertEqual(self.bus.interleaved, 0)


if __name__ == "__main__":
    unittest.main()
