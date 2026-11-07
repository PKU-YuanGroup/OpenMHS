"""OpenMHS driver for gh.msuarezrodriguez/python-instrument-control: the Lake Shore 336 temperature controller.

A direct Driver (decorated methods) over the upstream QCoDeS ``VisaInstrument``
``instruments.lakeshore_336:LakeShore336``.  The upstream class exposes plain methods that build SCPI-like text
commands from parts (``KRDG? A``, ``SETP 1,300.0``, ``RANGE 1,3``, ``OUTMODE 1,1,1,0``).  It declares no QCoDeS
Parameter object and no command table, so the card's QCoDeS family helper cannot bind it (its ``parameter_bindings``
must name ``Parameter.get()``/``Parameter.set()`` objects).  The package therefore uses the upstream object directly
with a ``native.py`` factory, as driver-authoring.md ("Choosing the shape") prescribes for commands assembled at run
time.

DEVIATION FROM THE CARD: a direct Driver with native.py rather than the QcodesDriver helper.  The card's entry list
also contains ``instruments.keithley_2634b:Keithley2634B``; one driver package serves one native class (G7 checks the
fake against that class), so this package integrates the temperature controller and does not serve the SMU.  The
repository's README lists both instruments (README.md:7-10); the LakeShore is the first entry of the card and its
optional instrument in ``main.py`` (main.py:154-168).

Served interface:

* reads: identity, temperature on input A, raw sensor units on input A, loop-1 setpoint, loop-1 ramp rate and state,
  output-1 heater range, and output-1 control mode, input and power-up flag;
* writes through ``cap.device.configure.v1``: setpoint, ramp rate and ramp state, heater range, control mode, control
  input and power-up flag, and the open-loop manual output level.  The setpoint and the ramp rate are
  ``Limit.operator_required``: no text of the clone states the accepted range of this controller, so the site states
  it and every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until an operator overlay exists;
* one extension action, ``x-cap.msuarezrodriguez.heaters_off.v1``: turn both heater outputs off with ``RANGE n,0`` and
  ``OUTMODE n,0,0,0`` and read the resulting ranges and modes back.  It is the safe-state action (SAFE-045) because
  no text of the clone documents an independent physical emergency stop.  The ``@estop`` sends the same off commands
  without waiting for a readback.

NOT COVERED:

* The Keithley 2634B SMU class of the same repository.  A package has one native class and the gate proves the fake
  against it; a second device needs its own card and package.
* ``wait_for_temperature`` and ``go_to_temperature`` (instruments/lakeshore_336.py:406-532): they poll the controller
  in an upstream loop with a default timeout of 600 s (instruments/lakeshore_336.py:411, 491) and do not observe the
  OpenMHS cancellation token, so they are not exposed as actions.
* ``set_manual_output`` has no corresponding query method in the upstream class; the write is served for open-loop
  operation but has no fresh readback.  The safe state disables the heater range itself, not only the manual level.
* Output 2 and control loops 2-4 are not exposed as separate writable resources; the e-stop and the safe-state action
  turn both outputs off, while the served reads and writes use output 1 and loop 1, the configuration ``main.py``
  applies (main.py:185-208).

Every Fact and every Limit cites the pinned clone at commit e56156e1ba6a2e5469094291fef91945ca9ee069.  This package
is model-authored and unreviewed (``driver.lock.json`` has ``reviewed_by: null``); it is checked on the fake backend
only and has never opened a VISA session.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SOURCE = "instruments/lakeshore_336.py"

SETPOINT_LIMIT = Limit.operator_required(
    "no text of the clone states the accepted setpoint range of the Lake Shore 336; the range depends on the "
    "installed sensor, heater and cryostat, so the site states it")
RAMP_RATE_LIMIT = Limit.operator_required(
    "the clone only says 'typically 0.1-100 K/min' in a comment and points to a manual that is not in the clone "
    "(instruments/lakeshore_336.py:243); the site states the allowed ramp rate of its installation")
HEATER_RANGE_LIMIT = Limit(
    allowed=["off", "low", "medium", "high"], source="upstream_code",
    ref=f"{SOURCE}:285-286")
OUTPUT_MODE_LIMIT = Limit(
    allowed=["off", "closed loop", "zone", "open loop", "monitor", "warmup"], source="upstream_code",
    ref=f"{SOURCE}:369-372")
OUTPUT_INPUT_LIMIT = Limit(
    allowed=["none", "A", "B", "C", "D"], source="upstream_code", ref=f"{SOURCE}:373")
MANUAL_OUTPUT_LIMIT = Limit(
    min=0, max=100, source="upstream_code", ref=f"{SOURCE}:310")


def _input_channel(text):
    """The native setter takes None or A-D, while the read reports the text 'none'."""
    return None if text == "none" else text


class LakeShore336(Driver):
    device_id = "lakeshore-336"
    device_kind = "thermal.zone"
    mode = "hardware"
    #: Heating a cryostat or an oven is R2 (MHS/spec/04-safety.md, section 2.1), equal to the card's floor.
    risk = "R2"
    native = "instruments.lakeshore_336:LakeShore336"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLakeShore336"}
    vendor, model = "Lake Shore Cryotronics", "Model 336 temperature controller"
    display_name = "Lake Shore 336 temperature controller (QCoDeS VisaInstrument)"
    tags = ["qcodes", "visa", "gpib", "temperature-controller", "cryostat", "heater", "lakeshore"]
    safe_state = (
        "heater outputs 1 and 2 commanded off: the e-stop sends RANGE n,0 and OUTMODE n,0,0,0 without a readback, and "
        "the safe-state action sends the same and fails unless RANGE? and OUTMODE? read off for both outputs; stored "
        "setpoints and ramps stay, nothing is cooled and no previous configuration is restored, so the sample can keep "
        "changing temperature; the class addresses heater outputs 1 and 2 only")
    facts = [
        Fact("LakeShore336 is a minimal QCoDeS driver for the Lake Shore Model 336 temperature controller",
             source="upstream_code", ref=f"{SOURCE}:10-12"),
        Fact("The class reads inputs A-D, gets and sets loops 1-4, gets and sets heater ranges on outputs 1-2, "
             "configures OUTMODE and RAMP, and offers manual heater output MOUT", source="upstream_code",
             ref=f"{SOURCE}:14-20"),
        Fact("The class does not send *RST on init, to preserve sensor curves and setup; it sends only *CLS",
             source="upstream_code", ref=f"{SOURCE}:22-26"),
        Fact("The constructor passes name and address to VisaInstrument and writes *CLS", source="upstream_code",
             ref=f"{SOURCE}:95-110"),
        Fact("The valid sensor channels are A, B, C and D", source="upstream_code", ref=f"{SOURCE}:30"),
        Fact("Heater ranges off, low, medium and high map to codes 0, 1, 2 and 3, and max is an alias for high",
             source="upstream_code", ref=f"{SOURCE}:32-40"),
        Fact("Output modes off, closed loop, zone, open loop, monitor and warmup map to codes 0 to 5",
             source="upstream_code", ref=f"{SOURCE}:45-60"),
        Fact("The control input code maps none to 0 and A to D to 1 to 4", source="upstream_code",
             ref=f"{SOURCE}:70-79"),
        Fact("get_temperature sends KRDG? <channel> and returns a float in Kelvin", source="upstream_code",
             ref=f"{SOURCE}:150-170"),
        Fact("get_sensor_units sends SRDG? <channel> and returns the raw float sensor reading", source="upstream_code",
             ref=f"{SOURCE}:172-192"),
        Fact("get_setpoint and set_setpoint use SETP? and SETP with the loop index, in the preferred units of the "
             "control input, which the docstrings call usually Kelvin", source="upstream_code",
             ref=f"{SOURCE}:197-217"),
        Fact("get_ramp and set_ramp use RAMP? and RAMP with the rate and state", source="upstream_code",
             ref=f"{SOURCE}:219-248"),
        Fact("get_heater_range and set_heater_range use RANGE? and RANGE with the output index and range code; "
             "set_heater_range accepts the text names off, low, medium and high", source="upstream_code",
             ref=f"{SOURCE}:253-299"),
        Fact("set_manual_output sends MOUT <output>,<percent> and documents 0 to 100 percent of full scale",
             source="upstream_code", ref=f"{SOURCE}:301-316"),
        Fact("get_output_mode parses OUTMODE? into mode code and text, input code and text, and a power-up flag",
             source="upstream_code", ref=f"{SOURCE}:321-353"),
        Fact("set_output_mode sends OUTMODE <output>,<mode>,<input>,<powerup> and documents the accepted mode and "
             "input names", source="upstream_code", ref=f"{SOURCE}:355-401"),
        Fact("main.py configures output 1 in closed loop with sensor A, heater range high, and a 1 K/min ramp "
             "disabled", source="upstream_code", ref="main.py:189-202"),
        Fact("main.py closes the LakeShore instrument", source="upstream_code", ref="main.py:407"),
        Fact("The README lists the Keithley 2634B source-measure unit and the LakeShore 336 temperature controller "
             "as the supported instruments", source="vendor_doc", ref="README.md:7-10"),
    ]

    # -- reads -------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Reply of *IDN? from the Lake Shore 336")
    def identity(self):
        return self.native.get_idn()

    @read("temperature", unit="K", description="Temperature reported by input A with KRDG? A")
    def temperature(self):
        return self.native.get_temperature("A")

    @read("sensor_units", type="number",
          description="Raw sensor value reported by input A with SRDG? A; the unit depends on the configured sensor")
    def sensor_units(self):
        return self.native.get_sensor_units("A")

    @read("setpoint", unit="K", description="Setpoint of control loop 1 with SETP? 1 (control input unit, kelvin assumed)")
    def setpoint(self):
        return self.native.get_setpoint(1)

    @read("ramp_rate", unit="K/min", description="Ramp rate of control loop 1 in K/min")
    def ramp_rate(self):
        return self.native.get_ramp(1)[0]

    @read("ramp_enabled", type="boolean", description="True when the ramp of control loop 1 is enabled")
    def ramp_enabled(self):
        return bool(self.native.get_ramp(1)[1])

    @read("heater_range", type="string", description="Heater range text of output 1: off, low, medium or high")
    def heater_range(self):
        return self.native.get_heater_range(1, as_text=True)

    @read("output_mode", type="string", description="Control mode text of output 1")
    def output_mode(self):
        return self.native.get_output_mode(1)["mode_text"]

    @read("output_input", type="string", description="Control input text of output 1 (none or A to D)")
    def output_input(self):
        return self.native.get_output_mode(1)["input_text"]

    @read("output_powerup_enable", type="boolean",
          description="True when output 1 restores its state after a power cycle")
    def output_powerup_enable(self):
        return bool(self.native.get_output_mode(1)["powerup_enable"])

    # -- writes ------------------------------------------------------------------------------------------------
    @write("setpoint", unit="K", limit=SETPOINT_LIMIT,
           description="Setpoint of control loop 1 in K; holds only while the control input unit is kelvin")
    def set_setpoint(self, value):
        self.native.set_setpoint(loop=1, value=value)
        return self.native.get_setpoint(1)

    @write("ramp_rate", unit="K/min", limit=RAMP_RATE_LIMIT,
           description="Ramp rate of control loop 1; the current ramp state is preserved")
    def set_ramp_rate(self, value):
        _rate, enabled = self.native.get_ramp(1)
        self.native.set_ramp(loop=1, rate_K_per_min=value, enable=bool(enabled))
        return self.native.get_ramp(1)[0]

    @write("ramp_enabled", type="boolean",
           description="Enable or disable the ramp of control loop 1; the current rate is preserved")
    def set_ramp_enabled(self, value):
        rate, _enabled = self.native.get_ramp(1)
        self.native.set_ramp(loop=1, rate_K_per_min=rate, enable=bool(value))
        return bool(self.native.get_ramp(1)[1])

    @write("heater_range", type="string", limit=HEATER_RANGE_LIMIT,
           description="Heater range of output 1: off, low, medium or high")
    def set_heater_range(self, value):
        self.native.set_heater_range(output=1, heater_range=value)
        return self.native.get_heater_range(1, as_text=True)

    @write("output_mode", type="string", limit=OUTPUT_MODE_LIMIT,
           description="Control mode of output 1; the current input and power-up flag are preserved")
    def set_output_mode(self, value):
        current = self.native.get_output_mode(1)
        self.native.set_output_mode(output=1, mode=value,
                                    input_channel=_input_channel(current["input_text"]),
                                    powerup_enable=bool(current["powerup_enable"]))
        return self.native.get_output_mode(1)["mode_text"]

    @write("output_input", type="string", limit=OUTPUT_INPUT_LIMIT,
           description="Control input of output 1: none or A to D; the current mode and power-up flag are preserved")
    def set_output_input(self, value):
        current = self.native.get_output_mode(1)
        self.native.set_output_mode(output=1, mode=current["mode_text"],
                                    input_channel=_input_channel(value),
                                    powerup_enable=bool(current["powerup_enable"]))
        return self.native.get_output_mode(1)["input_text"]

    @write("output_powerup_enable", type="boolean",
           description="Restore output 1 after a power cycle; the current mode and input are preserved")
    def set_output_powerup_enable(self, value):
        current = self.native.get_output_mode(1)
        self.native.set_output_mode(output=1, mode=current["mode_text"],
                                    input_channel=_input_channel(current["input_text"]),
                                    powerup_enable=bool(value))
        return bool(self.native.get_output_mode(1)["powerup_enable"])

    @write("manual_output", unit="%", limit=MANUAL_OUTPUT_LIMIT,
           description="Manual heater output of output 1 as a percentage of full scale; it only has an effect in "
                       "open-loop mode and the upstream class has no query for it")
    def set_manual_output(self, value):
        self.native.set_manual_output(output=1, percent=value)
        return float(value)

    # -- safe state and stop -----------------------------------------------------------------------------------
    def _heaters_off(self):
        for output in (1, 2):
            self.native.set_heater_range(output=output, heater_range="off")
            self.native.set_output_mode(output=output, mode="off", input_channel=None, powerup_enable=False)

    @action(name="x-cap.msuarezrodriguez.heaters_off.v1", safe_state=True,
            description="Turn both heater outputs off (RANGE n,0 and OUTMODE n,0,0,0) and read the ranges and modes "
                        "back; this is the safe-state action",
            output={
                "heater_range_1": Field("string", description="Range read back from output 1"),
                "heater_range_2": Field("string", description="Range read back from output 2"),
                "output_mode_1": Field("string", description="Mode read back from output 1"),
                "output_mode_2": Field("string", description="Mode read back from output 2"),
            })
    def heaters_off(self):
        self._heaters_off()
        readback = {
            "heater_range_1": self.native.get_heater_range(1, as_text=True),
            "heater_range_2": self.native.get_heater_range(2, as_text=True),
            "output_mode_1": self.native.get_output_mode(1)["mode_text"],
            "output_mode_2": self.native.get_output_mode(2)["mode_text"],
        }
        # Model review: a completed safe-state action asserts the safe state, so a read-back that is not "off"
        # for both outputs must fail instead of being reported as data.
        not_off = sorted(name for name, value in readback.items() if value != "off")
        if not_off:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               "heater outputs not confirmed off after RANGE n,0 and OUTMODE n,0,0,0: "
                               + ", ".join(f"{name}={readback[name]}" for name in not_off))
        return readback

    @estop
    def stop(self):
        """The native stop: turn both heater outputs and both control loops off without waiting for a readback."""
        self._heaters_off()

    def teardown(self):
        """Close the QCoDeS instrument; main.py also closes it at the end of a session (main.py:407)."""
        self.native.close()
