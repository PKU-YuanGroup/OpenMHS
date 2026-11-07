"""OpenMHS driver for gh.benpruitt/tecancavro: a Tecan Cavro XCalibur D syringe pump with a distribution valve.

A direct Driver (decorated methods) over the upstream device class ``tecancavro.models:XCaliburD``.

The card says ``family: serial`` / ``SerialDriver``.  That shape cannot express this interface: every command is
wrapped in the Tecan OEM API frame (STX 0x02, address, sequence byte, command payload, ETX 0x03 and an XOR checksum,
``tecancavro/tecanapi.py:87-91``) and ``XCaliburD`` assembles the payload from parts (a letter and a number:
``S{code}``, ``v{speed}``, ``V{speed}``, ``c{speed}``, ``L{slope}``, ``A{position}``, ``P{steps}``, ``O{port}``,
``tecancavro/models.py:453-565``).  A command table cannot reproduce bytes the upstream builds at run time, so this
package uses a direct Driver with a ``native.py`` factory instead (driver-authoring.md, "Choosing the shape").
The card's candidate classes do not bind a syringe pump either (``cap.fluid.dispense.v1`` binds a liquid handler or
a pipette, ``cap.motion.*`` binds a robot or an axis); the actions are extensions (RESULT.json catalogue_requests).

* reads: the plunger position and encoder count, the valve port, the start/top/cutoff speeds, the command buffer
  status and the microstep mode;
* writes: the start, top and cutoff speeds, the OEM speed code, the slope code and microstep mode; each bound is the
  range the upstream code states;
* actions: move the plunger to an absolute position, dispense a volume from a valve port, and stop; the port and the
  volume of a dispense are ``Limit.operator_required`` (the port count and the syringe size are constructor options,
  so the site states them, ``site-limits.example.json``);
* the e-stop is ``terminateCmd()`` (the T command, ``tecancavro/models.py:713-717``); the same native call is the
  safe-state action, which also clears the queued command chain.

Every Fact and Limit cites a line of the clone at the pinned commit 5267fd2ed48b7e38d2261459cbf4a381e54c33c1.  This
package is model-authored and unreviewed: it is checked on the fake backend only (never on hardware).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

MODELS = "tecancavro/models.py"


class Xcalibur(Driver):
    device_id = "tecancavro"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "tecancavro.models:XCaliburD"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeXCaliburD"}
    vendor, model = "Tecan", "Cavro XCalibur D syringe pump with distribution valve"
    display_name = "Tecan Cavro XCalibur D syringe pump"
    tags = ["syringe pump", "cavro", "xcalibur", "distribution valve", "serial"]
    facts = [
        Fact("The package controls Tecan Cavro syringe pumps; XCaliburD covers the XCalibur with a distribution valve",
             source="vendor_doc", ref="README.md:3"),
        Fact("A command frame is built as STX, address, sequence byte, command payload, ETX and an XOR checksum",
             source="upstream_code", ref="tecancavro/tecanapi.py:87-91"),
        Fact("The standard-mode plunger travel is 0 to 3000 encoder steps and 0 to 24000 in microstep mode",
             source="upstream_code", ref=f"{MODELS}:465-466"),
        Fact("A volume in microliters becomes encoder steps as volume * (3000 / syringe_ul) in standard mode",
             source="upstream_code", ref=f"{MODELS}:866"),
        Fact("The valve has 9 ports and the syringe 1000 uL by default; both are constructor options",
             source="upstream_code", ref=f"{MODELS}:42"),
        Fact("dispense() selects the port and then moves the plunger by minus the volume in steps",
             source="upstream_code", ref=f"{MODELS}:415-417"),
        Fact("A negative relative plunger move dispenses and a positive one extracts",
             source="upstream_code", ref=f"{MODELS}:498-499"),
        Fact("The command buffer status is 0 when empty and 1 when non-empty", source="upstream_code",
             ref=f"{MODELS}:690"),
        Fact("The encoder count of the plunger axis is read with ?4", source="upstream_code", ref=f"{MODELS}:667-673"),
        Fact("setSpeed takes an OEM speed code from 0 to 40 and SPEED_CODES maps a code to pulses per second",
             source="upstream_code", ref=f"{MODELS}:34-40"),
        Fact("setStartSpeed states 50 to 1000 pulses per second and setTopSpeed 5 to 6000", source="upstream_code",
             ref=f"{MODELS}:530-541"),
        Fact("setCutoffSpeed states 50 to 2700 pulses per second", source="upstream_code", ref=f"{MODELS}:548-549"),
        Fact("setSlope accepts a slope code from 1 to 20", source="upstream_code", ref=f"{MODELS}:560-561"),
        Fact("Chainable commands are queued in cmd_chain and sent only when executeChain() sends the chain",
             source="upstream_code", ref=f"{MODELS}:283-292"),
        Fact("terminateCmd() sends T as an executable command, which terminates the running command",
             source="upstream_code", ref=f"{MODELS}:713-717"),
        Fact("setMicrostep sends N0 or N1 immediately instead of queueing it", source="upstream_code",
             ref=f"{MODELS}:701-707"),
    ]
    safe_state = "plunger motion terminated and the queued command chain cleared (terminateCmd, then resetChain)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("plunger_position", type="integer", unit="1",
          description="Absolute plunger position in encoder steps (0-3000, or 0-24000 in microstep mode)")
    def plunger_position(self):
        return int(self.native.getPlungerPos())

    @read("encoder_position", type="integer", unit="1", description="Encoder count of the plunger axis")
    def encoder_position(self):
        return int(self.native.getEncoderPos())

    @read("port", type="integer", unit="1", description="Distribution valve port the pump is on (1 to num_ports)")
    def port(self):
        return int(self.native.getCurPort())

    @read("start_speed", type="integer", unit="1/s", description="Start speed in pulses per second")
    def start_speed(self):
        return int(self.native.getStartSpeed())

    @read("top_speed", type="integer", unit="1/s", description="Top speed in pulses per second")
    def top_speed(self):
        return int(self.native.getTopSpeed())

    @read("cutoff_speed", type="integer", unit="1/s", description="Cutoff speed in pulses per second")
    def cutoff_speed(self):
        return int(self.native.getCutoffSpeed())

    @read("buffer_status", type="integer", unit="1", description="Command buffer status: 0 empty, 1 non-empty")
    def buffer_status(self):
        return int(self.native.getBufferStatus())

    @read("microstep", type="boolean", description="True while the plunger runs in microstep mode")
    def microstep(self):
        return bool(self.native.microstep)

    # -- configuration writes ----------------------------------------------------------------------------------
    @write("start_speed", type="integer", unit="1/s", description="Start speed in pulses per second (v command)",
           limit=Limit(min=50, max=1000, source="upstream_code", ref=f"{MODELS}:531",
                       reason="setStartSpeed states the range [50-1000] pulses per second"))
    def set_start_speed(self, value):
        self.native.setStartSpeed(value)
        self.native.executeChain()
        return self.native.getStartSpeed()

    @write("top_speed", type="integer", unit="1/s", description="Top speed in pulses per second (V command)",
           limit=Limit(min=5, max=6000, source="upstream_code", ref=f"{MODELS}:540",
                       reason="setTopSpeed states the range [5-6000] pulses per second"))
    def set_top_speed(self, value):
        self.native.setTopSpeed(value)
        self.native.executeChain()
        return self.native.getTopSpeed()

    @write("cutoff_speed", type="integer", unit="1/s", description="Cutoff speed in pulses per second (c command)",
           limit=Limit(min=50, max=2700, source="upstream_code", ref=f"{MODELS}:549",
                       reason="setCutoffSpeed states the range [50-2700] pulses per second"))
    def set_cutoff_speed(self, value):
        self.native.setCutoffSpeed(value)
        self.native.executeChain()
        return self.native.getCutoffSpeed()

    @write("speed_code", type="integer", unit="1",
           description="OEM speed code that selects the top speed (S command, see SPEED_CODES)",
           limit=Limit(min=0, max=40, source="upstream_code", ref=f"{MODELS}:521",
                       reason="setSpeed refuses a code outside 0 to 40"))
    def set_speed_code(self, value):
        self.native.setSpeed(value)
        self.native.executeChain()

    @write("slope", type="integer", unit="1", description="Slope code of the speed ramp (L command)",
           limit=Limit(min=1, max=20, source="upstream_code", ref=f"{MODELS}:560",
                       reason="setSlope refuses a code outside 1 to 20"))
    def set_slope(self, value):
        self.native.setSlope(value)
        self.native.executeChain()

    @write("microstep", type="boolean", description="Operate the plunger in microstep mode (N1 on, N0 off)")
    def set_microstep(self, value):
        self.native.setMicrostep(on=bool(value))
        return bool(self.native.microstep)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.benpruitt.move_plunger.v1",
            description="Move the plunger to an absolute position and execute the queued command",
            input={"position": Field(
                "integer", unit="1",
                description="Absolute plunger position in encoder steps (0-3000 in standard mode)",
                limit=Limit(min=0, max=3000, source="upstream_code", ref=f"{MODELS}:478",
                            reason="movePlungerAbs refuses a position outside 0-3000 in standard mode (0-24000 in "
                                   "microstep mode, models.py:473)"))},
            output={"position": Field("integer", unit="1",
                                     description="Absolute plunger position reported after the move")})
    def move_plunger(self, position):
        self.native.movePlungerAbs(position)
        self.native.executeChain()
        return {"position": int(self.native.getPlungerPos())}

    @action(name="x-cap.benpruitt.dispense.v1",
            description="Select a valve port, dispense a volume from it and execute the queued command",
            input={"port": Field(
                       "integer", unit="1", description="Valve port to dispense from (1 to num_ports of the valve)",
                       limit=Limit.operator_required(
                           "the port count is a constructor option of the upstream class (num_ports, 9 by default, "
                           "models.py:80; changePort checks 1 to num_ports, models.py:441): the site states the "
                           "ports of its valve")),
                   "volume": Field(
                       "number", unit="uL", description="Volume to dispense in microliters",
                       limit=Limit.operator_required(
                           "the syringe size is a constructor option of the upstream class (syringe_ul, 1000 uL by "
                           "default, models.py:42; the move is volume * 3000 / syringe_ul steps, models.py:866): the "
                           "site states the volume of its syringe"))},
            output={"dispensed_volume": Field("number", unit="uL",
                                              description="Volume dispensed in microliters"),
                    "port": Field("integer", unit="1", description="Valve port after the dispense")})
    def dispense(self, port, volume):
        self.native.dispense(port, volume)
        self.native.executeChain()
        return {"dispensed_volume": volume, "port": int(self.native.getCurPort())}

    @action(name="x-cap.benpruitt.stop.v1", safe_state=True,
            description="Terminate the running command and clear the queued command chain",
            output={"stopped": Field("boolean", description="True once the command chain was cleared")})
    def stop_pump(self):
        self.native.terminateCmd()
        self.native.resetChain()
        return {"stopped": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="terminateCmd")
    def emergency_stop(self):
        """The native stop: the T command terminates the running command chain."""
        self.native.terminateCmd()
