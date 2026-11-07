"""OpenMHS driver for gh.freespace/pysmc100: the Newport SMC100 single-axis motion controller.

The upstream clone is one Python 2 module (``smc100.py``) whose class ``SMC100`` builds every command from the
controller ID, a command word and an argument, writes the bytes followed by CR LF, and parses the ID-prefixed
reply.  A command table cannot reproduce that framing (the ID is part of every line), so this package is a direct
``Driver`` over the upstream class.  The hardware backend in ``native.py`` is a Python 3 port of the same wire
protocol because the upstream module cannot be imported under Python 3 (its ``print`` statement and
``except Exception, ex`` are Python 2 syntax); the gate never imports either module.

* reads: the stage position in millimetres and the controller error code and state from ``TS?``;
* actions: home (``OR`` plus the upstream move to zero), absolute move (``PA``) and relative move (``PR``);
* the e-stop sends ``ST``, the upstream ``stop()`` command.

The stage travel is a property of the mounted stage, not of the controller, and the clone states no range: the
position and distance inputs use ``Limit.operator_required`` and the operator supplies the range in site-limits.json.
Every Fact cites ``smc100.py`` at commit 8c65638934edb9c50381b7a25488bdc728619ffc.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

POSITION_LIMIT = Limit.operator_required(
    "the travel is set by the mounted stage and the clone states no range; the operator supplies it")
DISTANCE_LIMIT = Limit.operator_required(
    "the relative travel is set by the mounted stage and the clone states no range; the operator supplies it")


class Smc100(Driver):
    device_id = "smc100"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "smc100:SMC100"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSMC100"}
    vendor, model = "Newport", "SMC100"
    display_name = "Newport SMC100 single-axis motion controller"
    tags = ["newport", "smc100", "motion", "stage", "serial", "rs232"]

    facts = [
        Fact("SMC100 is Newport's single-axis motion controller",
             source="upstream_code", ref="smc100.py:49"),
        Fact("Commands are <ID><command><arguments><CR><LF> and replies are <ID><command><result><CR><LF>",
             source="upstream_code", ref="smc100.py:51-57"),
        Fact("The serial link is 57600 baud, 8 data bits, no parity, 1 stop bit, XON/XOFF flow control "
             "with a 50 ms read timeout",
             source="upstream_code", ref="smc100.py:112-119"),
        Fact("A command is the controller ID, the command word and the argument, then CR LF",
             source="upstream_code", ref="smc100.py:371-386"),
        Fact("A query passes '?' as the argument; sendcmd refuses a command that ends with '?'",
             source="upstream_code", ref="smc100.py:348-363"),
        Fact("TS? returns a four-hex-digit error code followed by the two-character controller state",
             source="upstream_code", ref="smc100.py:187-191"),
        Fact("TP? returns the position in millimetres",
             source="upstream_code", ref="smc100.py:239-241"),
        Fact("PR moves by a relative distance in millimetres and PA to an absolute position in millimetres",
             source="upstream_code", ref="smc100.py:246-277"),
        Fact("OR starts homing; after homing the upstream moves the stage to 0 mm",
             source="upstream_code", ref="smc100.py:169-176"),
        Fact("ST stops the stage",
             source="upstream_code", ref="smc100.py:178-179"),
        Fact("The stage units are stage-dependent; the author's TRB25CC stage uses millimetres",
             source="upstream_code", ref="smc100.py:65-68"),
        Fact("The controller reports the DISABLE states 3C, 3D and 3E",
             source="upstream_code", ref="smc100.py:22-24"),
        Fact("wait_states gives up after MAX_WAIT_TIME_SEC = 12 s",
             source="upstream_code", ref="smc100.py:8"),
        Fact("A command that expects no reply is followed by at least COMMAND_WAIT_TIME_SEC = 0.06 s",
             source="upstream_code", ref="smc100.py:12"),
        Fact("PR and OR are never retried automatically",
             source="upstream_code", ref="smc100.py:374-377"),
    ]

    safe_state = "stage motion stopped by the ST command"

    @read("position", unit="mm", description="Stage position")
    def position(self):
        return self.native.get_position_mm()

    @read("error_code", type="integer", description="Controller error code from TS? (four hex digits)")
    def error_code(self):
        return self.native.get_status()[0]

    @read("state", type="string", description="Controller state from TS? (two hexadecimal characters)")
    def state(self):
        return self.native.get_status()[1]

    @action(name="x-cap.freespace.home.v1", risk="R1",
            description="Home the stage and leave it at the origin",
            output={"homed": Field("boolean", description="True when homing completed"),
                    "position": Field("number", unit="mm", description="Position after homing")})
    def home(self):
        self.native.home()
        return {"homed": True, "position": self.native.get_position_mm()}

    @action(name="x-cap.freespace.move_absolute.v1", risk="R1",
            description="Move the stage to an absolute position in millimetres",
            input={"position": Field("number", unit="mm", description="Target stage position",
                                     limit=POSITION_LIMIT)},
            output={"position": Field("number", unit="mm", description="Position reported after the move")})
    def move_absolute(self, position):
        self.native.move_absolute_mm(position)
        return {"position": self.native.get_position_mm()}

    @action(name="x-cap.freespace.move_relative.v1", risk="R1",
            description="Move the stage by a relative distance in millimetres",
            input={"distance": Field("number", unit="mm", description="Relative distance",
                                     limit=DISTANCE_LIMIT)},
            output={"position": Field("number", unit="mm", description="Position reported after the move")})
    def move_relative(self, distance):
        self.native.move_relative_mm(distance)
        return {"position": self.native.get_position_mm()}

    @estop
    def stop(self):
        self.native.stop()
