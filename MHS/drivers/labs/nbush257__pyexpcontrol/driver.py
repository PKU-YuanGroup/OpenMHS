"""OpenMHS driver for gh.nbush257/pyexpcontrol: the nebPod NPX rig controller.

A direct Driver (decorated methods) over the upstream class ``nebPod:Controller`` (python/nebPod.py:223).  The
controller talks to a Teensy 3.2 over ArCOM serial and builds its commands from a command letter, a subcommand
letter and integer parameters (python/nebPod.py:786-806, 1705-1707, 1954-1991), so a command table cannot express
it: this is a decorated Driver over the upstream object with a ``native.py`` factory.

Covered here:

* reads: the commanded laser amplitude, the commanded state of the eight olfactometer valves, the commanded state of
  the eight GPIO pins and the camera-trigger state.  The upstream class has no state query: it sends actuator
  commands and most then wait for one reply byte (``block_until_read``, python/nebPod.py:1288-1299), while the
  camera-trigger commands return without waiting (python/nebPod.py:1258-1286).  These reads report the last command
  this driver sent (documented in facts.md, and not a measurement of the hardware);
* one write: the laser amplitude in V (python/nebPod.py:782-783);
* actions: open or close one olfactometer valve, set all eight valves from an eight-character binary pattern, set one
  GPIO pin high or low, start and stop the camera trigger, and the safe-state action;
* safety: ``@estop`` turns the laser off (the upstream ``turn_off_laser``, python/nebPod.py:793-806) and the
  ``safe_state=True`` action also closes every olfactometer valve and stops the camera trigger.  No line of the clone
  documents an independent hardware e-stop, so ``estop_physical_ref`` is not set; the safe-state action is the
  independent stop this R3 hardware driver declares.

Risk: the upstream README says the analog output drives a "cobalt MLD laser" (README.md:50), a Cobolt MLD head; Cobolt's
owner's manual classes every 06-01 series MLD head 3B (IEC 60825-1), so a model review declared the device and the laser
write R3 (MHS/spec/04-safety.md: class 3B+ laser) instead of R2; the GPIO pins share the controller and can carry a
laser pulse line.  The safe-state action stays callable without a permit (SAFE-029).

Every Fact cites a line of the clone at the pinned commit (06e94c4d22ac2d9fc542a3ebee035a8b9e360ea7).  This package
is model-authored and unreviewed: its loader refuses the hardware backend at R3 until a human signs ``reviewed_by``,
and the acceptance gate runs the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class Pyexpcontrol(Driver):
    device_id = "npx-rig"
    device_kind = "process.controller"
    mode = "hardware"
    risk = "R3"
    native = "nebPod:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeController"}
    vendor, model = "nbush257", "nebPod NPX rig controller"
    display_name = "nebPod NPX rig controller (nebPod.Controller)"
    tags = ["teensy", "olfactometer", "laser", "gpio", "camera-trigger", "serial"]
    facts = [
        Fact("Controller opens the Teensy serial link with ArCOMObject(port, 115200)",
             source="upstream_code", ref="python/nebPod.py:267-270"),
        Fact("The olfactometer has eight valves: the leftmost bit of the binary string is Valve 1 and the rightmost "
             "bit is Valve 8", source="upstream_code", ref="python/nebPod.py:1743-1745"),
        Fact("set_all_olfactometer_valves asserts an eight-character pattern, reverses it and sends its decimal "
             "value as a uint8", source="upstream_code", ref="python/nebPod.py:1757-1762"),
        Fact("open_olfactometer sends the smell command, the open letter and the valve number as a uint8",
             source="upstream_code", ref="python/nebPod.py:1705-1707"),
        Fact("close_olfactometer sends the smell command, the close letter and the valve number as a uint8",
             source="upstream_code", ref="python/nebPod.py:1729-1731"),
        Fact("A laser amplitude is a float between 0 and 1 V", source="upstream_code",
             ref="python/nebPod.py:782-783"),
        Fact("_amp2int clips the amplitude to 0 to 1 and scales it to an integer between 0 and 100",
             source="upstream_code", ref="python/nebPod.py:1318-1340"),
        Fact("turn_on_laser writes the letter o twice and the scaled amplitude; turn_off_laser writes o then x and "
             "the scaled amplitude", source="upstream_code", ref="python/nebPod.py:786-806"),
        Fact("set_gpio accepts pins 0 to 7 (pins = list(range(8))) and the modes pulse, high and low",
             source="upstream_code", ref="python/nebPod.py:1972-1976"),
        Fact("start_camera_trig sends the auxiliary begin command and an integer frame rate; stop_camera_trig sends "
             "the auxiliary end command and 0", source="upstream_code", ref="python/nebPod.py:1258-1284"),
        Fact("block_until_read waits until a reply byte is available and then reads one uint8",
             source="upstream_code", ref="python/nebPod.py:1288-1299"),
        Fact("set_all_olfactometer_valves waits through wait_for_response, whose default timeout is 10 seconds",
             source="upstream_code", ref="python/nebPod.py:1765-1776"),
        Fact("start_camera_trig and stop_camera_trig send their command and return without waiting for a reply byte",
             source="upstream_code", ref="python/nebPod.py:1258-1286"),
    ]
    safe_state = "laser off (0 V command), all olfactometer valves closed, camera trigger stopped"

    def __init__(self, **options):
        super().__init__(**options)
        # The upstream class has no state query, so these are the driver's last-command shadows, not a measurement.
        self._laser_amplitude = 0.0
        self._valves = [False] * 8
        self._gpio = ["low"] * 8
        self._camera_triggering = False

    # -- reads ------------------------------------------------------------------------------------------------
    @read("laser_amplitude", unit="V", description="Last commanded laser amplitude (0 to 1 V command)")
    def laser_amplitude(self):
        return self._laser_amplitude

    @read("valves", type="array", items="boolean", length=8,
          description="Last commanded state of olfactometer valves 1 to 8 (True open), in valve order")
    def valves(self):
        return list(self._valves)

    @read("gpio", type="array", items=Field("string", enum=["high", "low", "pulse"]), length=8,
          description="Last commanded state of GPIO pins 0 to 7 ('high', 'low' or 'pulse')")
    def gpio(self):
        return list(self._gpio)

    @read("camera_triggering", type="boolean",
          description="True while the camera trigger was started through this driver and not stopped since")
    def camera_triggering(self):
        return self._camera_triggering

    # -- the write ---------------------------------------------------------------------------------------------
    @write("laser_amplitude", unit="V", risk="R3",
           description="Commanded laser amplitude, scaled by the firmware to 0 to 100",
           limit=Limit(min=0, max=1, unit="V", source="upstream_code", ref="python/nebPod.py:783"))
    def set_laser_amplitude(self, value):
        self.native.turn_on_laser(value)
        self._laser_amplitude = int(float(value) * 100) / 100.0    # _amp2int scale, python/nebPod.py:1340
        return self._laser_amplitude

    # -- olfactometer valves -----------------------------------------------------------------------------------
    @action(name="x-cap.nbush257.set_valve.v1",
            description="Open or close one olfactometer valve",
            input={"valve": Field("integer", unit="1",
                                  description="Olfactometer valve number (1 to 8, leftmost pattern bit is Valve 1)",
                                  limit=Limit(min=1, max=8, unit="1", source="upstream_code",
                                              ref="python/nebPod.py:1743-1745")),
                   "state": Field("string", enum=["open", "closed"],
                                  description="Requested valve state: 'open' or 'closed'")},
            output={"valve": Field("integer", unit="1", description="Valve number that was commanded"),
                    "state": Field("string", enum=["open", "closed"], description="State that was commanded")})
    def set_valve(self, valve, state):
        if state == "open":
            self.native.open_olfactometer(valve)
            self._valves[int(valve) - 1] = True
        else:
            self.native.close_olfactometer(valve)
            self._valves[int(valve) - 1] = False
        return {"valve": int(valve), "state": state}

    @action(name="x-cap.nbush257.set_all_valves.v1",
            description="Set all eight olfactometer valves from an eight-character binary pattern "
                        "(leftmost character is Valve 1, '1' is open)",
            input={"pattern": Field("string", pattern=r"^[01]{8}$",
                                    description="Eight characters, '1' opens and '0' closes, leftmost is Valve 1")},
            output={"valves": Field("array", items=Field("boolean"), length=8,
                                    description="Commanded valve states in valve order (True open)")})
    def set_all_valves(self, pattern):
        self.native.set_all_olfactometer_valves(pattern)
        self._valves = [character == "1" for character in pattern]
        return {"valves": list(self._valves)}

    # -- GPIO --------------------------------------------------------------------------------------------------
    @action(name="x-cap.nbush257.set_gpio.v1",
            description="Drive one GPIO pin high or low",
            input={"pin": Field("integer", unit="1", description="GPIO pin number (0 to 7)",
                                limit=Limit(allowed=[0, 1, 2, 3, 4, 5, 6, 7], unit="1",
                                            source="upstream_code", ref="python/nebPod.py:1972-1976")),
                   "mode": Field("string", enum=["high", "low"],
                                 description="Pin level: 'high' or 'low'")},
            output={"pin": Field("integer", unit="1", description="GPIO pin number that was commanded"),
                    "mode": Field("string", enum=["high", "low"], description="Level that was commanded")})
    def set_gpio(self, pin, mode):
        self.native.set_gpio(pin, mode)
        self._gpio[int(pin)] = mode
        return {"pin": int(pin), "mode": mode}

    # -- camera trigger ----------------------------------------------------------------------------------------
    @action(name="x-cap.nbush257.start_camera_trigger.v1",
            description="Start the camera trigger with the upstream default frame rate",
            output={"camera_triggering": Field("boolean", description="True once the start command was sent")})
    def start_camera_trigger(self):
        self.native.start_camera_trig()
        self._camera_triggering = True
        return {"camera_triggering": True}

    @action(name="x-cap.nbush257.stop_camera_trigger.v1",
            description="Stop the camera trigger",
            output={"camera_triggering": Field("boolean", description="False once the stop command was sent")})
    def stop_camera_trigger(self):
        self.native.stop_camera_trig()
        self._camera_triggering = False
        return {"camera_triggering": False}

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.nbush257.safe_state.v1", safe_state=True,
            description="Safe state: laser off at 0 V, all olfactometer valves closed, camera trigger stopped",
            output={"safe": Field("boolean",
                                  description="True once the laser-off, all-valves-closed and camera-stop commands "
                                              "were sent")})
    def all_off(self):
        self.native.turn_off_laser(0)
        self.native.set_all_olfactometer_valves("00000000")
        self.native.stop_camera_trig()
        self._laser_amplitude = 0.0
        self._valves = [False] * 8
        self._camera_triggering = False
        return {"safe": True}

    @estop(native="turn_off_laser")
    def stop(self):
        """The native laser-off command: the runtime latches first, then this sends 0 V."""
        self.native.turn_off_laser(0)
        self._laser_amplitude = 0.0
