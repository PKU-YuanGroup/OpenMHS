"""OpenMHS driver for gh.cdbaird/tl-rotation-control: a Thorlabs Elliptec rotation stage over serial.

A direct Driver over the upstream class ``elliptec.rotation:Motor``.  The upstream builds every command at run
time from an address digit, a two-letter instruction and an optional hexadecimal data field
(``elliptec/rotation.py:28-76``, ``elliptec/cmd.py:2-20``); a family command table cannot reproduce those bytes,
so this package uses a direct Driver and a ``native.py`` factory.

* reads: the absolute position, the step size, the status/error code and the serial number reported at connect;
* writes: the absolute position (the angle is an operator-required bound because the travel range is the ``Range``
  field that the motor reports at connect, not a constant in the clone) and the step size (bounded 1 to 359 degrees
  by the upstream GUI, ``td_gui.py:109-110``);
* the home action sends the upstream ``ho`` move;
* the e-stop isolates the module with ``set_('isolate', '01')``, the isolate action of the upstream GUI
  (``main.py:56-58``).

Every Fact cites a line of the clone at the pinned commit
(759dc3fc58efd975c37c7ee954fa6152618cd58e), as does the step-size limit; the position limit is
operator_required because the clone states no numeric travel range.  This package is model-authored and
unreviewed: it is checked on the fake backend only, and nothing here ran on a stage.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class TlRotation(Driver):
    device_id = "elliptec-rotation"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "elliptec.rotation:Motor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMotor"}
    vendor, model = "Thorlabs", "Elliptec rotation stage"
    display_name = "Thorlabs Elliptec rotation stage (elliptec.rotation.Motor)"
    tags = ["rotation stage", "elliptec", "serial", "motion"]
    facts = [
        Fact("The upstream controller drives a Thorlabs Elliptec rotation stage", source="vendor_doc",
             ref="README.md:2"),
        Fact("Motor is a pyserial Serial subclass; its constructor opens the port and calls _get_motor_info",
             source="upstream_code", ref="elliptec/rotation.py:8-24"),
        Fact("The information query is get_['info'] = b'in'", source="upstream_code", ref="elliptec/cmd.py:3"),
        Fact("The motor information reply carries Motor Type, Serial No., Year, Firmware, Thread, Hardware, Range "
             "and Pulse/Rev", source="upstream_code", ref="elliptec/helper.py:34-43"),
        Fact("The conversion factor is Range / Pulse/Rev", source="upstream_code",
             ref="elliptec/rotation.py:22-24"),
        Fact("deg_to_hex uses the integer factor counts_per_rev // range and writes eight hexadecimal digits",
             source="upstream_code", ref="elliptec/rotation.py:78-81"),
        Fact("A get_ query, a set_ setting and a do_ move are an address digit, a two-letter instruction and "
             "optional data", source="upstream_code", ref="elliptec/rotation.py:28-76"),
        Fact("get_ and set_ store the parsed reply in Motor.status instead of returning it", source="upstream_code",
             ref="elliptec/rotation.py:44-76"),
        Fact("A position reply is a PO or BO code and a 32-bit hexadecimal field", source="upstream_code",
             ref="elliptec/helper.py:46-48"),
        Fact("s32 interprets the position field as a signed 32-bit integer", source="upstream_code",
             ref="elliptec/helper.py:74-75"),
        Fact("A status reply is a GS code and a hexadecimal error code", source="upstream_code",
             ref="elliptec/helper.py:50-52"),
        Fact("Error code 0 is Status OK, 5 is Module Isolated and 12 is Out of Range", source="upstream_code",
             ref="elliptec/errcodes.py:2-17"),
        Fact("The stepsize query instruction is 'gj' and the setting instruction is 'sj'", source="upstream_code",
             ref="elliptec/cmd.py:6-12"),
        Fact("The parser returns the code and data field of a reply that is not IN, PO, BO or GS", source="upstream_code",
             ref="elliptec/helper.py:54-55"),
        Fact("The move commands are home 'ho', forward 'fw', backward 'bw', absolute 'ma' and relative 'mr'",
             source="upstream_code", ref="elliptec/cmd.py:14-20"),
        Fact("The upstream GUI bounds the step-size slider to 1 to 359 degrees", source="upstream_code",
             ref="td_gui.py:109-110"),
        Fact("The upstream GUI bounds the step-size spin box to 1 to 359 degrees", source="upstream_code",
             ref="td_gui.py:128-129"),
        Fact("The upstream GUI labels the field Step Size (deg)", source="upstream_code", ref="td_gui.py:202"),
        Fact("The upstream GUI sets both motors' step size from the slider value through deg_to_hex",
             source="upstream_code", ref="main.py:13-16"),
        Fact("On slider release the upstream GUI writes the slider value through deg_to_hex and reads it back",
             source="upstream_code", ref="main.py:66-72"),
        Fact("The upstream isolate action puts a motor in isolation with set_('isolate', '01')",
             source="upstream_code", ref="main.py:56-58"),
    ]
    safe_state = "stage isolated: the motor module is put in isolation and reports Module Isolated"

    # -- conversion helpers -----------------------------------------------------------------------------------
    def _counts_per_degree(self):
        """The integer factor deg_to_hex uses, or a failed receipt when the motor did not report one."""
        try:
            factor = int(self.native.counts_per_rev) // int(self.native.range)
        except (AttributeError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               "the motor did not report a usable Range and Pulse/Rev") from exc
        if factor < 1:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               "the motor reported a Range larger than its Pulse/Rev; no degree conversion")
        return factor

    def _reply(self, request):
        """Send a get_ query and return the parsed reply that the upstream stores in Motor.status."""
        self.native.get_(request)
        return self.native.status

    def _position(self):
        reply = self._reply("position")
        if not (isinstance(reply, tuple) and len(reply) == 2 and reply[0] in ("PO", "BO")):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the position query returned {reply!r}")
        return int(reply[1]) / self._counts_per_degree()

    def _step_size(self):
        reply = self._reply("stepsize")
        if not (isinstance(reply, tuple) and len(reply) == 2 and reply[0] == "GJ"):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the stepsize query returned {reply!r}")
        return int(reply[1], 16) / self._counts_per_degree()

    # -- reads -------------------------------------------------------------------------------------------------
    @read("position", unit="deg", description="Absolute rotation position of the stage")
    def position(self):
        return self._position()

    @read("step_size", unit="deg", description="Step size of the forward and backward moves")
    def step_size(self):
        return self._step_size()

    @read("status_code", type="integer",
          description="Status or error code of the module (0 OK, 5 isolated, 12 out of range)")
    def status_code(self):
        reply = self._reply("status")
        if not (isinstance(reply, tuple) and len(reply) == 2 and reply[0] == "GS"):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the status query returned {reply!r}")
        return int(reply[1])

    @read("serial_number", type="string", description="Serial number the module reports on connect")
    def serial_number(self):
        try:
            return str(self.native.info["Serial No."])
        except (AttributeError, KeyError, TypeError) as exc:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the motor information has no serial number") from exc

    # -- writes ------------------------------------------------------------------------------------------------
    @write("position", unit="deg", description="Absolute rotation position of the stage",
           limit=Limit.operator_required(
               "the travel range is the Range field that the motor reports at connect (elliptec/rotation.py:22-24), "
               "not a constant in the clone; the site sets the allowed angles of its stage"))
    def set_position(self, value):
        self.native.do_("absolute", self.native.deg_to_hex(int(round(float(value)))))
        return self._position()

    @write("step_size", unit="deg", description="Step size of the forward and backward moves",
           limit=Limit(min=1, max=359, source="upstream_code", ref="td_gui.py:109-110",
                       reason="the upstream GUI bounds its step-size control to 1 to 359 degrees"))
    def set_step_size(self, value):
        self.native.set_("stepsize", self.native.deg_to_hex(int(round(float(value)))))
        return self._step_size()

    # -- action ------------------------------------------------------------------------------------------------
    @action(name="x-cap.cdbaird.home.v1", description="Home the rotation stage",
            output={"homed": Field("boolean", description="True once the home move completed"),
                    "position": Field("number", unit="deg", description="Position after the home move")})
    def home(self):
        self.native.do_("home", "0")
        return {"homed": True, "position": self._position()}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then isolates the motor module."""
        self.native.set_("isolate", "01")
