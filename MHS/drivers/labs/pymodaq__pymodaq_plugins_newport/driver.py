"""OpenMHS driver for the Newport SMC100 single-axis motion controller.

The upstream class is ``pymodaq_plugins_newport.hardware.smc100:SMC100``: a
pyvisa wrapper that prefixes every command with the controller's device number
and sends the SMC100 mnemonics (``PA``, ``PR``, ``OR``, ``ST`` and so on).  A
SerialDriver/SCPI command table cannot express that wire syntax: the first
token of ``1PA10`` is not a word the clone spells out, and the device number is
part of the line.  This package therefore uses a direct Driver over the
upstream class, with ``native.py`` as the hardware factory.

The driver is deliberately conservative about units and travel:

* ``SMC100`` documents positions and distances only "in the stage's units"
  (``smc100.py:171-172`` and ``smc100.py:178-179``).  The stage depends on the
  installed positioner, so position reads have no unit and the numeric move
  inputs are published as UCUM ``1`` (the controller's own stage units) while
  their travel bounds come from ``Limit.operator_required``: the operator
  supplies the axis envelope in ``site-limits.json``.
* Reads: position, motion state, speed, acceleration and identity.
* Actions: absolute and relative moves, a move to position 0, and the native
  stop.  The e-stop calls the same ``ST`` command as the stop action.

Every Fact cites a line of the clone at commit
bad8a714aa079f9ae2aab95851efedc32a8505ba.  The package is model-authored and
unreviewed; nothing here ran an instrument.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

CLONE = "src/pymodaq_plugins_newport"


class Smc100(Driver):
    device_id = "smc100"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pymodaq_plugins_newport.hardware.smc100:SMC100"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSmc100"}
    vendor, model = "Newport", "SMC100"
    display_name = "Newport SMC100 single-axis motion controller"
    tags = ["newport", "smc100", "motion controller", "positioner", "serial"]
    facts = [
        Fact("The clone lists SMC100 as a single-axis motion controller",
             source="vendor_doc", ref="README.rst:39"),
        Fact("SMC100 is the class for a controller device for positioners and works over USB",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:44-48"),
        Fact("Every command is prefixed with the controller's device number before it is written",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:91-94"),
        Fact("A query is prefixed with the device number and the first three characters of the reply are stripped",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:96-107"),
        Fact("move_abs sends PA followed by the position, which is in the stage's units",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:176-181"),
        Fact("move_rel sends PR followed by the distance, which is in the stage's units",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:169-174"),
        Fact("home sends PA0 and moves the device to position 0",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:189-193"),
        Fact("homing sends OR and works only when the controller state is NOT REFERENCED",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:109-111"),
        Fact("stop sends ST to stop motion", source="upstream_code",
             ref=f"{CLONE}/hardware/smc100.py:201-203"),
        Fact("reset sends RS and leaves the controller in NOT REFERENCED state",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:195-199"),
        Fact("enable sends MM1 (READY) and disable sends MM0 (DISABLE)",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:120-126"),
        Fact("position queries PA? and returns the reply as a float",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:183-187"),
        Fact("speed queries VA? and is set with VA followed by the value",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:205-213"),
        Fact("acceleration queries AC? and is set with AC followed by the value",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:215-223"),
        Fact("is_moving reads the controller status with TS and compares it with 0x28",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:134-140"),
        Fact("get_last_command_error queries TE and clears the controller's error buffer",
             source="upstream_code", ref=f"{CLONE}/hardware/smc100.py:160-167"),
        Fact("The upstream plugin was tested with an SMC100PP controller and a URS150 rotation stage",
             source="vendor_doc", ref="README.rst:68"),
        Fact("The PyMoDAQ move plugin sets the controller unit to degrees for its URS150 stage and says the unit "
             "should be changed for linear actuators", source="upstream_code",
             ref=f"{CLONE}/daq_move_plugins/daq_move_Newport_SMC100.py:21-22"),
        Fact("The PyMoDAQ move plugin sets _controller_units to the degree sign for its SMC100 stage",
             source="upstream_code", ref=f"{CLONE}/daq_move_plugins/daq_move_Newport_SMC100.py:39"),
    ]
    safe_state = "motion stopped with the controller's ST command; the controller stays powered"

    @read("identity", type="string", description="Controller identity string (ID?)")
    def identity(self):
        return self.native.idn

    @read("position", description="Stage position from PA?, in the stage's units")
    def position(self):
        return self.native.position

    @read("is_moving", type="boolean", description="True while the controller reports the moving state (TS)")
    def is_moving(self):
        return self.native.is_moving

    @read("speed", description="Constant moving speed from VA?, in the controller's own units")
    def speed(self):
        return self.native.speed

    @read("acceleration", description="Acceleration and deceleration from AC?, in the controller's own units")
    def acceleration(self):
        return self.native.acceleration

    @action(name="x-cap.pymodaq.smc100_move_abs.v1",
            description="Command an absolute move with PA; the controller reports completion through is_moving",
            input={"position": Field("number", unit="1",
                                     description="Target position in the stage's units",
                                     limit=Limit.operator_required(
                                         "the clone gives no travel range for the installed stage; SMC100 "
                                         "positions are in the stage's units (smc100.py:176-181), so the "
                                         "operator supplies the axis envelope"))},
            output={"position": Field("number", unit="1",
                                      description="Absolute position commanded in the stage's units")})
    def move_abs(self, position):
        self.native.move_abs(position)
        return {"position": position}

    @action(name="x-cap.pymodaq.smc100_move_rel.v1",
            description="Command a relative move with PR; the controller reports completion through is_moving",
            input={"distance": Field("number", unit="1",
                                     description="Relative distance in the stage's units",
                                     limit=Limit.operator_required(
                                         "the clone gives no travel range for the installed stage; SMC100 "
                                         "distances are in the stage's units (smc100.py:169-174), so the "
                                         "operator supplies the axis envelope"))},
            output={"distance": Field("number", unit="1",
                                      description="Relative distance commanded in the stage's units")})
    def move_rel(self, distance):
        self.native.move_rel(distance)
        return {"distance": distance}

    @action(cap="cap.motion.home.v1",
            description="Move the stage to position 0 with PA0 (the clone's home)",
            input={"axes": Field("array", items="string",
                                 description="Axis names; the SMC100 has one axis, so the value is accepted for "
                                             "the class shape and ignored")})
    def home(self, axes=None):
        self.native.home()
        return {"homed": True}

    @action(name="x-cap.pymodaq.smc100_stop.v1",
            description="Stop motion with the controller's ST command",
            output={"stopped": Field("boolean", description="True once ST has been sent")})
    def stop_motion(self):
        self.native.stop()
        return {"stopped": True}

    @estop(native="stop")
    def emergency_stop(self):
        self.native.stop()
