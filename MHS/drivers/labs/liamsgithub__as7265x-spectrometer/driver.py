"""OpenMHS driver for gh.liamsgithub/as7265x-spectrometer: a SparkFun Triad AS7265x spectrometer over I2C.

The upstream clone is one Python 2.7 module of module-level functions, not a class (``spectrometer.py:1-20``).
It builds ``SMBus(1)`` at import time and talks to the AS7265x at address 0x49 (``spectrometer.py:10-20``); every
public operation is a function such as ``init``, ``readRAW`` and ``readCAL``.  This package is a direct
:class:`~mhs.driver.Driver` over a Python 3 port of those functions: ``native.py`` opens the SMBus and returns an
object with the same public methods, while ``fake.py`` is the in-memory stand-in.  ``native`` is the explicit
module selector ``pyfile:spectrometer.py#*`` (the card's entry symbol): gate G7 reads the pinned module's top-level
functions from the clone's AST and checks the fake's methods and the driver's calls against their names and
signatures; nothing imports the clone.

Covered:

* reads: board presence, the hardware version tuple, the three device temperature registers, and the configuration
  the upstream writes (integration time register, gain, LED drive current, blue LED and the three shutter LEDs);
* writes through ``cap.device.configure.v1``: those same configuration values.  The bounds are the ones the clone
  checks (integration time 0 through 254 from ``range(0,255)``, gain 0 through 3, LED drive current 0 through 3);
* ``cap.measure.intensity.v1``: one calibrated channel value from ``readCAL``; the optional channel is 1 through 18
  in the ascending-frequency order of the clone, and leaving it out returns the brightest channel;
* ``x-cap.liamsgithub.read_spectrum.v1``: all 18 raw and all 18 calibrated values;
* ``x-cap.liamsgithub.factory_reset.v1``: the native ``init`` factory reset;
* the native LED-off path (blue LED and all three shutter LEDs) is the e-stop and the safe-state action
  ``x-cap.liamsgithub.leds_off.v1``.

Stop and ownership.  Every effectful call (a configuration write, the factory reset, the LED-off path) runs under
one package I/O fence.  The e-stop first marks the device stopped, so an effectful call admitted before the
runtime latched but not yet at the device is refused instead of writing after the stop; it then waits at most
``STOP_WAIT_S`` for an effectful call already at the device, switches every LED off (it attempts all four even
when one fails) and reads register 0x07 of the three devices back.  It succeeds only when that fresh read-back
shows every LED off; otherwise it raises and the runtime keeps its latch (``MHS.SAFETY.SAFE_STATE_UNREACHED``).
Measurements are reads and never hold the fence, so a stop does not wait for them; ``native.py`` keeps each
register transaction atomic and each thread's device selection coherent.  The stopped mark is released only by the
``@reset`` hook after an accepted ``mhs.safety.reset``; it writes nothing to the device.

What it does not cover: the clone states no wavelength axis for the 18 channels (README.md only names the three LED
peaks), so ``cap.measure.spectrum.v1`` cannot be bound without inventing one; the raw and calibrated arrays are an
extension.  The Python 2 module cannot be imported by the Python 3 runtime; ``native.py`` is an independent port and
was never run.  The package is model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null); no
hardware was attached and no hardware run is claimed.  The upstream licence is NOASSERTION, so no publication is
claimed.
"""

import threading

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, action, estop, read, reset, write
from mhs.errors import MHSError

#: The three AS7265x devices the clone addresses by name (spectrometer.py:195-201).
DEVICES = ("AS72651", "AS72652", "AS72653")

#: The 18 channels are addressed by this order in the clone's readCAL/readRAW (spectrometer.py:340, 368).
CHANNELS = tuple(str(index) for index in range(1, 19))

#: The clone checks the integration time with range(0,255), so its legal values are 0 through 254 even though the
#: docstring says 0 to 255 (spectrometer.py:274, 280).
INTEGRATION_LIMIT = Limit(min=0, max=254, unit="1", source="upstream_code", ref="spectrometer.py:280",
                          reason="range(0,255) accepts 0 through 254")

#: The clone checks gain against the four codes 0, 1, 2 and 3 (spectrometer.py:303).
GAIN_LIMIT = Limit(allowed=[0, 1, 2, 3], unit="1", source="upstream_code", ref="spectrometer.py:303",
                   reason="the clone accepts the four gain codes 0, 1, 2 and 3")

#: The clone checks the LED drive current against the four codes 0, 1, 2 and 3 (spectrometer.py:258).
LED_CURRENT_LIMIT = Limit(allowed=[0, 1, 2, 3], unit="1", source="upstream_code", ref="spectrometer.py:258",
                          reason="the clone accepts the four LED drive current codes 0, 1, 2 and 3")

#: Host bounds of the package I/O fence, not device limits: how long an effectful call or a stop waits for an
#: effectful call already at the device (the factory reset holds it for the clone's 4 s firmware wait).
IO_WAIT_S = 5.0
STOP_WAIT_S = 5.0

#: Guards the lazy creation of each driver's fence (setup() does not run when a backend object is injected).
_FENCES_LOCK = threading.Lock()


class _Fence:
    """The package I/O fence of one driver: a lock over effectful native calls and the stopped mark."""

    def __init__(self):
        self.io = threading.Lock()
        self.stopped = False


def _require(applied, what):
    """Turn an upstream ``bool`` return into a typed failure when the device reported that it did not apply it."""
    if applied is False:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned False")
    return applied


class As7265xSpectrometer(Driver):
    device_id = "as7265x-spectrometer"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R1"
    native = "pyfile:spectrometer.py#*"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAs7265xSpectrometer"}
    vendor, model = "SparkFun", "Triad Spectroscopy Sensor (AS7265x)"
    display_name = "SparkFun Triad AS7265x spectrometer"
    tags = ["spectrometer", "as7265x", "sparkfun", "triad", "i2c", "led"]
    facts = [
        Fact("The clone is a Python 2.7 module: line 341 is a print statement, so the Python 3 ast parser cannot "
             "read the file", source="upstream_code", ref="spectrometer.py:341"),
        Fact("The module constructs SMBus(1) at import time and talks to the AS7265x at I2C address 0x49",
             source="upstream_code", ref="spectrometer.py:10-20"),
        Fact("init() writes register 0x04 with 1 and sleeps 4 seconds after the factory reset", source="upstream_code",
             ref="spectrometer.py:155-160"),
        Fact("boardPresent() reads register 0x00 and returns True or False", source="upstream_code",
             ref="spectrometer.py:167-172"),
        Fact("hwVersion() reads registers 0x00 and 0x01 and returns a tuple of the device type and hardware version",
             source="upstream_code", ref="spectrometer.py:178-184"),
        Fact("temperatures() selects AS72651, AS72652 and AS72653 and reads register 0x06 from each into a list of "
             "three values", source="upstream_code", ref="spectrometer.py:194-201"),
        Fact("setBlueLED(state) selects AS72651 and writes bit 0 of register 0x07", source="upstream_code",
             ref="spectrometer.py:208-220"),
        Fact("shutterLED(device,state) selects one of AS72651, AS72652 or AS72653 and writes bit 3 of register 0x07",
             source="upstream_code", ref="spectrometer.py:226-247"),
        Fact("setLEDDriveCurrent accepts 0, 1, 2 or 3 and writes bits 4-5 of register 0x07 on all three devices; "
             "the docstring maps them to 12.5, 25, 50 and 100 mA", source="upstream_code",
             ref="spectrometer.py:252-269"),
        Fact("setIntegrationTime checks range(0,255), so it accepts 0 through 254, and writes register 0x05 on all "
             "three devices; the docstring says 0 to 255", source="upstream_code", ref="spectrometer.py:273-292"),
        Fact("setGain accepts 0, 1, 2 or 3 and writes bits 4-5 of register 0x04 on all three devices; the docstring "
             "maps them to 1x, 3.7x, 16x and 64x", source="upstream_code", ref="spectrometer.py:296-318"),
        Fact("readRAW() reads six 16-bit register pairs from each of the three devices, giving 18 raw values, and "
             "reorders them into ascending frequency order", source="upstream_code", ref="spectrometer.py:325-343"),
        Fact("readCAL() reads six IEEE754 quadruples from each of the three devices, giving 18 calibrated values, "
             "and reorders them into ascending frequency order", source="upstream_code",
             ref="spectrometer.py:350-371"),
        Fact("reorderData maps the 18 values from the device read order to the monotonic frequency order",
             source="upstream_code", ref="spectrometer.py:138-146"),
        Fact("The README calls the project a Python module to drive the SparkFun Triad Spectroscopy Sensor",
             source="vendor_doc", ref="README.md:1-3"),
        Fact("The board consists of three devices with six sensors each and passbands from UV to IR; the three "
             "on-board LEDs peak at about 400, 475 and 875 nm", source="vendor_doc", ref="README.md:5-9"),
        Fact("The README targets Python 2.7 on a Raspberry Pi 3B", source="vendor_doc", ref="README.md:19"),
        Fact("The README lists setIntegrationTime legal input values 0 to 255, setGain 0 to 3 and "
             "setLEDDriveCurrent 0 to 3", source="vendor_doc", ref="README.md:66-87"),
        Fact("The README says readRAW and readCAL return 18 values sorted into ascending frequency order",
             source="vendor_doc", ref="README.md:88-101"),
    ]
    safe_state = ("all on-board LEDs off: the blue LED and the three shutter LEDs are disabled and read back off (the "
                  "LED drive current register is left at its configured code)")

    # -- state ----------------------------------------------------------------------------------------------------
    @read("board_present", type="boolean", description="True when the board answers on the I2C bus")
    def board_present(self):
        return bool(self.native.boardPresent())

    @read("hardware_version", type="array", items="integer", length=2,
          description="Device type and hardware version register values of the board")
    def hardware_version(self):
        values = list(self.native.hwVersion())
        if len(values) != 2:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"hwVersion returned {len(values)} values, not 2")
        return [int(item) for item in values]

    @read("temperatures", type="array", items="integer", length=3,
          description="Temperature register values of AS72651, AS72652 and AS72653 (the clone states no unit)")
    def temperatures(self):
        values = list(self.native.temperatures())
        if len(values) != 3:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"temperatures returned {len(values)} values, not 3")
        return [int(item) for item in values]

    @read("integration_time_register", type="integer", unit="1",
          description="Integration time register value applied to all three devices (0 through 254)")
    def integration_time_register(self):
        return self._register("AS72651", 0x05)

    @read("gain", type="integer", unit="1",
          description="Gain code of all three devices (0, 1, 2 or 3; the clone maps them to 1x, 3.7x, 16x, 64x)")
    def gain(self):
        return (self._register("AS72651", 0x04) >> 4) & 0x03

    @read("led_drive_current", type="integer", unit="1",
          description="LED drive current code of all three devices (0, 1, 2 or 3; the clone maps them to 12.5, "
                      "25, 50 and 100 mA)")
    def led_drive_current(self):
        return (self._register("AS72651", 0x07) >> 4) & 0x03

    @read("blue_led", type="boolean", description="True while the master blue LED on AS72651 is on")
    def blue_led(self):
        return bool(self._register("AS72651", 0x07) & 0x01)

    @read("shutter_leds", type="array", items="boolean", length=3,
          description="Shutter LED states of AS72651, AS72652 and AS72653")
    def shutter_leds(self):
        return [bool(self._register(device, 0x07) & 0x08) for device in DEVICES]

    # -- configuration --------------------------------------------------------------------------------------------
    @write("integration_time_register", type="integer", unit="1",
           description="Integration time register value to apply to all three devices (0 through 254)",
           limit=INTEGRATION_LIMIT)
    def set_integration_time_register(self, value):
        self._effect("setIntegrationTime",
                     lambda: _require(self.native.setIntegrationTime(int(value)), "setIntegrationTime"))
        return self._register("AS72651", 0x05)

    @write("gain", type="integer", unit="1",
           description="Gain code to apply to all three devices (0, 1, 2 or 3)",
           limit=GAIN_LIMIT)
    def set_gain(self, value):
        self._effect("setGain", lambda: _require(self.native.setGain(int(value)), "setGain"))
        return (self._register("AS72651", 0x04) >> 4) & 0x03

    @write("led_drive_current", type="integer", unit="1",
           description="LED drive current code to apply to all three devices (0, 1, 2 or 3)",
           limit=LED_CURRENT_LIMIT)
    def set_led_drive_current(self, value):
        self._effect("setLEDDriveCurrent",
                     lambda: _require(self.native.setLEDDriveCurrent(int(value)), "setLEDDriveCurrent"))
        return (self._register("AS72651", 0x07) >> 4) & 0x03

    @write("blue_led", type="boolean", description="Turn the master blue LED on AS72651 on or off")
    def set_blue_led(self, value):
        self._effect("setBlueLED", lambda: _require(self.native.setBlueLED(bool(value)), "setBlueLED"))
        return bool(self._register("AS72651", 0x07) & 0x01)

    @write("shutter_leds", type="array", items="boolean", length=3,
           description="Turn the shutter LEDs of AS72651, AS72652 and AS72653 on or off")
    def set_shutter_leds(self, value):
        states = [bool(item) for item in value]
        if len(states) != 3:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"shutter_leds needs 3 values, got {len(states)}")

        def apply():
            for device, state in zip(DEVICES, states):
                _require(self.native.shutterLED(device, state), f"shutterLED({device!r}, {state})")

        self._effect("shutterLED", apply)
        return [bool(self._register(device, 0x07) & 0x08) for device in DEVICES]

    # -- measurement ----------------------------------------------------------------------------------------------
    @action(cap="cap.measure.intensity.v1",
            description="Read one calibrated channel value of the current acquisition; the optional channel is "
                        "1 through 18 in the ascending-frequency order of readCAL, and leaving it out returns the "
                        "brightest channel",
            input={"channel": Field("string",
                                    description="Channel number 1 through 18 in the ascending-frequency order of "
                                                "readCAL; leave it out for the brightest channel",
                                    enum=list(CHANNELS))})
    def measure_intensity(self, channel=None):
        values = [float(item) for item in self.native.readCAL()]
        self.check_cancelled()
        if len(values) != 18:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"readCAL returned {len(values)} values, not 18")
        if channel is None:
            return {"intensity": max(values)}
        return {"intensity": values[int(channel) - 1]}

    @action(name="x-cap.liamsgithub.read_spectrum.v1",
            description="Read all 18 raw and all 18 calibrated channel values in the ascending-frequency order of "
                        "the clone",
            output={
                "raw": Field("array", items=Field("integer", description="Raw 16-bit channel value"),
                             length=18, description="Raw values of readRAW"),
                "calibrated": Field("array", items=Field("number", description="Calibrated channel value"),
                                    length=18, description="Calibrated values of readCAL"),
            })
    def read_spectrum(self):
        raw = [int(item) for item in self.native.readRAW()]
        self.check_cancelled()
        calibrated = [float(item) for item in self.native.readCAL()]
        self.check_cancelled()
        if len(raw) != 18 or len(calibrated) != 18:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"readRAW/readCAL returned {len(raw)}/{len(calibrated)} values, not 18")
        return {"raw": raw, "calibrated": calibrated}

    @action(name="x-cap.liamsgithub.factory_reset.v1",
            description="Reset all three AS7265x devices to their factory defaults with the native init and report "
                    "whether the board is present afterwards",
            output={"board_present": Field("boolean", description="True when the board answers after the reset")})
    def factory_reset(self):
        self._effect("init", self.native.init)
        self.check_cancelled()
        return {"board_present": bool(self.native.boardPresent())}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.liamsgithub.leds_off.v1", safe_state=True,
            description="Turn off the master blue LED and the shutter LEDs of all three devices (the safe state) and "
                        "read them back; it takes no input",
            output={
                "blue_led": Field("boolean", description="False once the master blue LED reads back off"),
                "shutter_leds": Field("array", items=Field("boolean", description="False once the shutter LED is off"),
                                      length=3, description="Shutter LED states of AS72651, AS72652 and AS72653"),
            })
    def leds_off(self):
        blue, shutters = self._leds_off_confirmed("x-cap.liamsgithub.leds_off.v1")
        return {"blue_led": blue, "shutter_leds": shutters}

    @estop(native="setBlueLED")
    def emergency_stop(self):
        """The native stop: refuse late effectful calls, turn off every LED and read them back off."""
        self._fence().stopped = True
        self._leds_off_confirmed("e-stop")

    @reset
    def release_fence(self):
        """After an accepted safety reset, release the stopped mark; nothing is written to the device."""
        fence = self._fence()
        if not fence.io.acquire(timeout=IO_WAIT_S):
            raise MHSError("MHS.SAFETY.RESET_REFUSED",
                           f"an effectful native call still owns the device after {IO_WAIT_S} s")
        try:
            fence.stopped = False
        finally:
            fence.io.release()

    # -- helpers --------------------------------------------------------------------------------------------------
    def _fence(self):
        with _FENCES_LOCK:
            fence = getattr(self, "_as7265x_fence", None)
            if fence is None:
                fence = _Fence()
                self._as7265x_fence = fence
        return fence

    def _effect(self, what, call):
        """Run one effectful native sequence under the package I/O fence; refuse it after an e-stop."""
        fence = self._fence()
        if not fence.io.acquire(timeout=IO_WAIT_S):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"{what}: another effectful call owned the device for "
                               f"{IO_WAIT_S} s; nothing was written")
        try:
            if fence.stopped:
                raise Cancelled(f"{what}: refused after an LED-off e-stop until an accepted safety reset; nothing "
                                "was written")
            return call()
        finally:
            fence.io.release()

    def _register(self, device, address):
        """Select one AS7265x device and read one virtual register."""
        _require(self.native.setDEVSEL(device), f"setDEVSEL({device!r})")
        return int(self.native.readReg(address))

    def _leds_off_confirmed(self, what):
        """Switch every LED off (all four attempts are made), read register 0x07 back and confirm they are off."""
        fence = self._fence()
        if not fence.io.acquire(timeout=STOP_WAIT_S):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"{what}: an earlier effectful call still owned the device after "
                               f"{STOP_WAIT_S} s; the LEDs were not switched off")
        try:
            problems = []
            steps = [("setBlueLED(False)", lambda: self.native.setBlueLED(False))]
            steps += [(f"shutterLED({device!r}, False)", lambda device=device: self.native.shutterLED(device, False))
                      for device in DEVICES]
            for label, step in steps:
                try:
                    if step() is False:
                        problems.append(f"{label} returned False")
                except Exception as exc:  # noqa: BLE001 - every LED is attempted; the failure is raised below
                    problems.append(f"{label} raised {type(exc).__name__}")
            blue, shutters = None, [None, None, None]
            try:
                blue = bool(self._register("AS72651", 0x07) & 0x01)
                shutters = [bool(self._register(device, 0x07) & 0x08) for device in DEVICES]
            except Exception as exc:  # noqa: BLE001 - an unreadable LED state is an unconfirmed stop
                problems.append(f"the LED read-back raised {type(exc).__name__}")
            if not problems and (blue or any(shutters)):
                problems.append(f"the LED read-back shows blue={blue} shutters={shutters}")
            if problems:
                raise DriverFailed("MHS.DEVICE.FAULTED", f"{what}: the LEDs are not confirmed off: "
                                   + "; ".join(problems))
            return blue, shutters
        finally:
            fence.io.release()
