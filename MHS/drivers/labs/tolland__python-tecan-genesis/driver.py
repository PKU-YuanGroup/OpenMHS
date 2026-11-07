"""OpenMHS driver for gh.tolland/python-tecan-genesis: a Tecan Genesis RSP 200 liquid handler.

The clone is a Python 2 script set.  ``bin/tecan_funcs.py`` opens ``/dev/ttyUSB0`` at 9600 baud (line 13), builds
every frame from a rotating sequence letter, the unit address and the ASCII command (``STX`` + sequence + unit +
command + ``ETX`` + XOR + newline, lines 147-164), and reads replies with ``read`` (lines 210-281).  The only class
is ``Cmd_delayed`` (line 57): it stacks ``(command, unit)`` pairs in ``cmdStack`` and ``start`` sends ``GFC``, each
stacked command and ``GSC`` (lines 70-108).

The card proposes a ``SerialDriver`` (family ``serial``, decision ``family-config``).  That helper is line-oriented
and its manifest rejects control characters, so it cannot send the STX/ETX frame or the XOR checksum; the honest
shape is a direct Driver over the card's class ``Cmd_delayed``, with a package ``native.py`` transport that
reimplements the frame for Python 3 (DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: how many commands this driver has added to the stack and how many are queued;
* actions: initialize the arms (``PIS``/``PIA``), home the ROMA (``PAZ2480``/``PAR0``/``PAY0``/``PAX0``), run the
  clone's fixed dispense sequence on D1-D8, and move the LiHa Z axis with a site-supplied position range;
* BLOCKED on the stop path: the class and the module define no stop, abort, halt or emergency command.  ``close()``
  (lines 201-203) only closes the serial port, so an R2 e-stop cannot stop a move already started, and SAFE-045
  cannot be met without inventing a command.  RESULT.json records the block.

Every Fact cites a line of the clone at the pinned commit (37e825db120b56199519bea72c82116f75269608).  This package
is model-authored and unreviewed; it is checked on the fake backend only and never ran on hardware.  The clone is
Python 2, so the gate's G7 cannot parse ``bin/tecan_funcs.py`` at all.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

SOURCE = "bin/tecan_funcs.py"
DOC = "bin/tecan"

#: The Z coordinate is commanded in 0.1 mm units; the PAZ doc block says "Zi: distance in 0.1 mm" (bin/tecan:243).
Z_TICKS_PER_MM = 10

#: No text of the clone states the Z travel range; the PAZ doc says it is "set by SRA cmd" (bin/tecan:243).
_Z_LIMIT = Limit.operator_required(
    "no text of the clone states the Z travel range: the PAZ doc block says the range is set by the SRA command "
    "(bin/tecan:243), which is a per-instrument setting, so the site supplies the range")


class TecanGenesis(Driver):
    device_id = "tecan-genesis"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "tecan_funcs:Cmd_delayed"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTecanGenesis"}
    vendor, model = "Tecan", "Genesis RSP 200"
    display_name = "Tecan Genesis RSP 200 liquid handler"
    tags = ["tecan", "genesis", "rsp 200", "liquid handler", "pipetting", "serial", "rs-232"]
    facts = [
        Fact("The project is a Python module for controlling the Tecan Genesis RSP 200",
             source="vendor_doc", ref="README.md:2"),
        Fact("The module opens /dev/ttyUSB0 at 9600 baud with a 1 s read timeout and a 5 s write timeout; the "
             "portmon dump above it shows 8 data bits, no parity and one stop bit",
             source="upstream_code", ref=f"{SOURCE}:9-13"),
        Fact("A command frame is STX (0x02), the sequence letter, the unit address, the ASCII command, ETX (0x03), "
             "the XOR of those bytes, and a trailing newline", source="upstream_code", ref=f"{SOURCE}:147-164"),
        Fact("The sequence letters rotate through A-G", source="upstream_code", ref=f"{SOURCE}:39-51"),
        Fact("do_cmd reads a first acknowledgement and then a second acknowledgement/data frame",
             source="upstream_code", ref=f"{SOURCE}:166-176"),
        Fact("read consumes the byte after ETX as the XOR and does not compare it before returning a frame",
             source="upstream_code", ref=f"{SOURCE}:210-281"),
        Fact("Cmd_delayed stores (command, unit) pairs in cmdStack and start sends GFC, every stacked command and "
             "then GSC to the M1 controller", source="upstream_code", ref=f"{SOURCE}:57-108"),
        Fact("add_cmd appends to cmdStack and increments the class counter cmdCount",
             source="upstream_code", ref=f"{SOURCE}:65-67"),
        Fact("The logged firmware reply is @M1@GENESIS-V1.61-07/2001",
             source="upstream_code", ref="rs232_logs/BIOBULLS-L3YMYO.LOG:51"),
        Fact("The logged write 02 41 4D 31 52 46 56 30 03 4E is STX A M1 RFV0 ETX and the XOR 0x4E",
             source="upstream_code", ref="rs232_logs/BIOBULLS-L3YMYO.LOG:52"),
        Fact("PAZ moves all installed tips to absolute Z positions in 0.1 mm; the range is set by the SRA command",
             source="upstream_code", ref=f"{DOC}:241-243"),
        Fact("The ROMA home action sends PAZ2480, PAR0, PAY0 and PAX0 to the R1 unit",
             source="upstream_code", ref=f"{DOC}:43-46"),
        Fact("The initialization sequence sends PIS to the M1 controller and PIA to the R1 arm",
             source="upstream_code", ref=f"{DOC}:182-189"),
        Fact("The dispense example sends V3600c900D217M0R to each of the diluter units D1 through D8",
             source="upstream_code", ref="bin/dispense_1.py:30-31"),
        Fact("Cmd_delayed defines only __init__, add_cmd and start (lines 57-108), and the module's only close() "
             "closes the serial port (lines 201-203); no stop, abort, halt or emergency command exists",
             source="upstream_code", ref=f"{SOURCE}:57-203"),
    ]
    safe_state = ("unreachable through this library: the clone defines no stop, abort, halt or emergency command, "
                  "and close() only closes the serial port, so a latched e-stop cannot stop a move in flight")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("commands_added", type="integer",
          description="Commands this driver has added to the command stack (Cmd_delayed.cmdCount)")
    def commands_added(self):
        return int(self.native.cmdCount)

    @read("queued_commands", type="integer",
          description="Commands currently waiting in the command stack (len(Cmd_delayed.cmdStack))")
    def queued_commands(self):
        return len(self.native.cmdStack)

    # -- internal helpers -----------------------------------------------------------------------------------------
    def _start(self, commands):
        """Clear the stack, add the commands and send the three-phase group feed of Cmd_delayed.start."""
        self.native.cmdStack.clear()
        self.native.runningStack.clear()
        for cmd, dev in commands:
            self.native.add_cmd(cmd, dev)
        result = self.native.start()
        if not isinstance(result, dict) or not result.get("started"):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the command stack did not start")
        return result

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.tolland.run_initialize.v1",
            description="Initialize the Tecan arms with the PIS/PIA sequence",
            output={"commands": Field("array", description="Commands sent, as unit:payload",
                                      items=Field("string", description="One command")),
                    "started": Field("boolean", description="True when the group feed completed")})
    def run_initialize(self):
        return self._start([("PIS", "M1"), ("PIA", "R1")])

    @action(name="x-cap.tolland.run_home_roma.v1",
            description="Run the clone's ROMA home sequence (PAZ2480, PAR0, PAY0, PAX0)",
            output={"commands": Field("array", description="Commands sent, as unit:payload",
                                      items=Field("string", description="One command")),
                    "started": Field("boolean", description="True when the group feed completed")})
    def run_home_roma(self):
        return self._start([("PAZ2480", "R1"), ("PAR0", "R1"), ("PAY0", "R1"), ("PAX0", "R1")])

    @action(name="x-cap.tolland.run_fixed_dispense.v1",
            description="Run the clone's fixed dispense sequence V900P187M200R on the eight diluter units",
            output={"commands": Field("array", description="Commands sent, as unit:payload",
                                      items=Field("string", description="One command")),
                    "started": Field("boolean", description="True when the group feed completed")})
    def run_fixed_dispense(self):
        return self._start([("V3600c900D217M0R", f"D{index}") for index in range(1, 9)])

    @action(name="x-cap.tolland.move_liha_z.v1",
            description="Move the eight LiHa tips to an absolute Z position (PAZ, in 0.1 mm units)",
            input={"z_mm": Field("number", unit="mm",
                                 description="Absolute Z position in millimetres; the site supplies the range",
                                 limit=_Z_LIMIT)},
            output={"command": Field("string", description="The PAZ command sent to the A1 unit"),
                    "started": Field("boolean", description="True when the group feed completed")})
    def move_liha_z(self, z_mm):
        ticks = int(round(z_mm * Z_TICKS_PER_MM))
        command = "PAZ" + ",".join([str(ticks)] * 8)
        result = self._start([(command, "A1")])
        return {"command": command, "started": bool(result.get("started"))}
