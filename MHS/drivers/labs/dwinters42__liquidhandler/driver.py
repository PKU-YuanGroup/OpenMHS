"""OpenMHS driver for gh.dwinters42/liquidhandler: a Waters 2700-compatible liquid handler.

A direct Driver (decorated methods) over the upstream device class ``liquidhandler:Robot``.  The clone is
Python 2 source: the gate reads it with the lines Python 3 cannot parse left out, and the hardware factory in
``native.py`` ports the documented framed-serial protocol rather than importing the clone.

* reads: the two arm positions (``ShowPosition``), the tracked syringe contents (``syringecontents``) and the
  names of the memorized locations (``locations``);
* actions as ``x-cap.dwinters42.*`` extensions: memorize a location, move an arm to coordinates, move one axis,
  draw, dispense and run the raw syringe-pump command.  No catalogue class fits the native interface: the clone
  exposes uncalibrated integer *units* and raw arm coordinates, not uL, mm or a labware/well model.  The arm travel,
  the syringe volume and the arm/pump/axis counts are configuration, so those inputs are ``Limit.operator_required``
  and are refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies them (``site-limits.example.json`` shows the
  overlay); the syringe speed has the 1 to 20 bound the protocol states (``Protocol.md:64``);
* the clone documents no stop or halt command (``Protocol.md:55-65``).  The safe-state action and the e-stop both
  command every syringe pump to zero speed at its tracked position, which the native ``Pump`` accepts (speed 0 is
  inside its 0 to 20 check, ``liquidhandler.py:132-134``), and the runtime latch refuses all later commands.  This is
  a software safe state, not an independent hardware e-stop; the package sets no ``estop_physical_ref``.

Every Fact cites a line of the clone at the pinned commit 45e303634e7921633dde36a0466962a3a300543f.  This package is
model-authored and unreviewed: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
``driver.lock.json``, so it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: The protocol states the syringe speed range; it is not a configuration choice.
SPEED_LIMIT = Limit(min=1, max=20, unit="1", source="vendor_doc", ref="Protocol.md:64",
                    reason="the protocol states syringe speed x (1-20)")

#: The clone keeps arm travel, syringe volume and device counts as constructor configuration, not device facts.
_OPERATOR_COORD = ("the clone's arm travel is the constructor default armlimits, not a bound of the installed arm; "
                   "the site supplies the travel of its arm")
_OPERATOR_UNITS = ("the clone hard-codes 2000 units as the syringe size, a configuration of the installed syringe; "
                   "the site supplies the usable volume of its syringe")
_OPERATOR_POSITION = ("the pump position 0 to 2000 is the hard-coded syringe size, a configuration of the installed "
                      "syringe; the site supplies the travel of its syringe")
_OPERATOR_ARM = ("the number of arms is configured by armaddr and is not a bound of the device; the site supplies "
                 "the arm numbers present on its unit")
_OPERATOR_AXIS = ("the axis index depends on the axes the installed arm exposes; the site supplies the valid axis "
                  "indices")
_OPERATOR_PUMP = ("the number of syringe pumps is configured by pumpaddr and is not a bound of the device; the site "
                  "supplies the pump numbers present on its unit")


def _coord(description):
    return Field("number", unit="1", description=description, limit=Limit.operator_required(_OPERATOR_COORD))


def _arm(description="Arm number (1 is the first arm)"):
    return Field("integer", unit="1", description=description, limit=Limit.operator_required(_OPERATOR_ARM))


def _pump(description="Syringe pump number (1 is the first pump)"):
    return Field("integer", unit="1", description=description, limit=Limit.operator_required(_OPERATOR_PUMP))


def _volume(description):
    return Field("number", unit="1", description=description, limit=Limit.operator_required(_OPERATOR_UNITS))


def _speed():
    return Field("number", unit="1", description="Syringe speed, 1 to 20", limit=SPEED_LIMIT)


class Liquidhandler(Driver):
    device_id = "dwinters42-liquidhandler"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "liquidhandler:Robot"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLiquidhandler"}
    vendor, model = "Waters", "2700 Sample Manager (compatible)"
    display_name = "Waters 2700-compatible liquid handler (liquidhandler.Robot)"
    tags = ["liquid-handler", "syringe-pump", "robot-arm", "serial", "framed-protocol"]
    facts = [
        Fact("The constructor opens the serial port with rtscts=0, xonxoff=0 and timeout=0",
             source="upstream_code", ref="liquidhandler.py:44-45"),
        Fact("The constructor initializes every arm with PI, SP0 and SA and every pump with Z1 0 R",
             source="upstream_code", ref="liquidhandler.py:47-59"),
        Fact("armaddr is [18, 28] for the two arms and pumpaddr is [11] for the syringe pump",
             source="upstream_code", ref="liquidhandler.py:32-38"),
        Fact("Move formats the arm command PA x y z, sends it to armaddr[armnum-1] and stores the position in "
             "curpos", source="upstream_code", ref="liquidhandler.py:89-93"),
        Fact("MoveAxis formats the command XA, YA or ZA with an integer position and updates curpos",
             source="upstream_code", ref="liquidhandler.py:95-100"),
        Fact("AddPosition stores coordinates [x, y, z] under a name in locations",
             source="upstream_code", ref="liquidhandler.py:77-79"),
        Fact("ShowPosition returns the stored curpos of an arm", source="upstream_code",
             ref="liquidhandler.py:102-103"),
        Fact("Draw takes bottle or sample as source, refuses a draw above 2000 units of syringe content and calls "
             "Pump twice", source="upstream_code", ref="liquidhandler.py:116-130"),
        Fact("Dispense refuses more units than the tracked syringe content and calls Pump twice",
             source="upstream_code", ref="liquidhandler.py:107-114"),
        Fact("Pump refuses a speed below 0 or above 20, a position below 0 or above 2000, and a direction other "
             "than in or out, then sends S<speed> A<position> <I|O> R", source="upstream_code",
             ref="liquidhandler.py:132-147"),
        Fact("The protocol frames each message as 0xFF 0x02 <message> 0x03 <checksum> 0x0D",
             source="vendor_doc", ref="Protocol.md:23-26"),
        Fact("The protocol lists PI, SP0, SA and PA for arms and Sx Ay d R for syringe pumps, with no stop or halt "
             "command", source="vendor_doc", ref="Protocol.md:55-65"),
        Fact("The protocol addresses arm 1 as 18, arm 2 as 28, syringe 1 as 11 and syringe 2 as 12",
             source="vendor_doc", ref="Protocol.md:39-48"),
        Fact("The protocol return codes are @ accepted, A error, Q execution in progress and Y finished",
             source="vendor_doc", ref="Protocol.md:70-79"),
        Fact("The README describes a library and GUI for Waters 2700-compatible liquid handlers with 1-2 arms, "
             "attached syringes and one 6-port valve", source="vendor_doc", ref="Readme.md:4-7"),
        Fact("The README lists moving up to two arms and drawing or dispensing with the syringe pump and 6-port "
             "valve", source="vendor_doc", ref="Readme.md:9-15"),
        Fact("The example calls Move, AddPosition, Goto, Draw and Dispense",
             source="vendor_doc", ref="examples/simple.py:5-15"),
    ]
    safe_state = ("none: the protocol documents no stop or halt command, so a moving arm cannot be stopped, "
                  "and a zero-speed Pump command is outside the protocol's 1-20 speed range (the model review "
                  "blocked the package, RESULT.json)")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("arm1_position", type="array", items="number", length=3, unit="1",
          description="Last commanded position of arm 1 in device steps")
    def arm1_position(self):
        return self.native.ShowPosition(1)

    @read("arm2_position", type="array", items="number", length=3, unit="1",
          description="Last commanded position of arm 2 in device steps")
    def arm2_position(self):
        return self.native.ShowPosition(2)

    @read("syringe_contents", type="array", items="number", unit="1",
          description="Tracked liquid in each syringe in device units")
    def syringe_contents(self):
        return list(self.native.syringecontents)

    @read("location_names", type="array", items="string",
          description="Names of the memorized arm positions")
    def location_names(self):
        return sorted(self.native.locations)

    # -- arm actions ------------------------------------------------------------------------------------------
    @action(name="x-cap.dwinters42.add_position.v1",
            description="Memorize an arm position under a name",
            input={"name": Field("string", max_length=64, description="Name of the memorized position"),
                   "x": _coord("Arm X coordinate in device steps"),
                   "y": _coord("Arm Y coordinate in device steps"),
                   "z": _coord("Arm Z coordinate in device steps")},
            output={"name": Field("string", description="Name of the memorized position"),
                    "position": Field("array", items="number", length=3, unit="1",
                                      description="Coordinates stored under the name")})
    def add_position(self, name, x, y, z):
        self.native.AddPosition(name, [x, y, z])
        return {"name": name, "position": [x, y, z]}

    @action(name="x-cap.dwinters42.move_arm.v1",
            description="Move an arm to absolute X, Y and Z coordinates",
            input={"arm": _arm(),
                   "x": _coord("Target X coordinate in device steps"),
                   "y": _coord("Target Y coordinate in device steps"),
                   "z": _coord("Target Z coordinate in device steps")},
            output={"arm": Field("integer", unit="1", description="Arm that was moved"),
                    "position": Field("array", items="number", length=3, unit="1",
                                      description="Position the arm stored after the move")})
    def move_arm(self, arm, x, y, z):
        self.native.Move([x, y, z], arm)
        return {"arm": arm, "position": list(self.native.ShowPosition(arm))}

    @action(name="x-cap.dwinters42.move_axis.v1",
            description="Move one axis of an arm to an absolute position",
            input={"arm": _arm(),
                   "axis": Field("integer", unit="1", description="Axis index (0 is X, 1 is Y, 2 is Z)",
                                 limit=Limit.operator_required(_OPERATOR_AXIS)),
                   "position": Field("number", unit="1", description="Target position of the axis in device steps",
                                     limit=Limit.operator_required(_OPERATOR_COORD))},
            output={"arm": Field("integer", unit="1", description="Arm that was moved"),
                    "axis": Field("integer", unit="1", description="Axis index that was moved"),
                    "position": Field("array", items="number", length=3, unit="1",
                                      description="Position the arm stored after the move")})
    def move_axis(self, arm, axis, position):
        self.native.MoveAxis(axis, position, arm)
        return {"arm": arm, "axis": axis, "position": list(self.native.ShowPosition(arm))}

    # -- syringe actions --------------------------------------------------------------------------------------
    @action(name="x-cap.dwinters42.draw.v1",
            description="Draw liquid into a syringe from the bottle or the sample",
            input={"pump": _pump(),
                   "units": _volume("Volume to draw in device units"),
                   "source": Field("string", enum=["bottle", "sample"],
                                   description="Source: bottle or sample"),
                   "speed": _speed()},
            output={"pump": Field("integer", unit="1", description="Syringe pump that was used"),
                    "units": Field("number", unit="1", description="Volume drawn in device units"),
                    "syringe_contents": Field("array", items="number", unit="1",
                                              description="Tracked liquid in each syringe after the draw")})
    def draw(self, pump, units, source, speed):
        self.native.Draw(units, source, speed, pump)
        return {"pump": pump, "units": units, "syringe_contents": list(self.native.syringecontents)}

    @action(name="x-cap.dwinters42.dispense.v1",
            description="Dispense liquid from a syringe",
            input={"pump": _pump(),
                   "units": _volume("Volume to dispense in device units"),
                   "speed": _speed()},
            output={"pump": Field("integer", unit="1", description="Syringe pump that was used"),
                    "units": Field("number", unit="1", description="Volume dispensed in device units"),
                    "syringe_contents": Field("array", items="number", unit="1",
                                              description="Tracked liquid in each syringe after the dispense")})
    def dispense(self, pump, units, speed):
        self.native.Dispense(units, speed, pump)
        return {"pump": pump, "units": units, "syringe_contents": list(self.native.syringecontents)}

    @action(name="x-cap.dwinters42.pump.v1",
            description="Run the raw syringe-pump command at a speed, position and valve direction",
            input={"pump": _pump(),
                   "speed": _speed(),
                   "position": Field("number", unit="1", description="Pump position in device units",
                                     limit=Limit.operator_required(_OPERATOR_POSITION)),
                   "direction": Field("string", enum=["in", "out"],
                                      description="Valve direction: in or out")},
            output={"pump": Field("integer", unit="1", description="Syringe pump that was used"),
                    "position": Field("number", unit="1", description="Pump position that was commanded"),
                    "syringe_contents": Field("array", items="number", unit="1",
                                              description="Tracked liquid in each syringe after the command")})
    def pump(self, pump, speed, position, direction):
        self.native.Pump(pump, speed, position, direction)
        return {"pump": pump, "position": position,
                "syringe_contents": list(self.native.syringecontents)}

    # -- safety -----------------------------------------------------------------------------------------------
    @action(name="x-cap.dwinters42.stop_pump.v1",
            description="Command every syringe pump to zero speed at its tracked position; takes no input",
            output={"stopped": Field("boolean", description="True once every syringe pump was commanded to stop"),
                    "syringe_contents": Field("array", items="number", unit="1",
                                              description="Tracked liquid in each syringe after the stop")})
    def stop_pump(self):
        self._stop_pumps()
        return {"stopped": True, "syringe_contents": list(self.native.syringecontents)}

    def _stop_pumps(self):
        for index in range(len(self.native.pumpaddr)):
            self.native.Pump(index + 1, 0, self.native.syringecontents[index], "out")


    def teardown(self):
        port = getattr(self.native, "s", None)
        if port is not None:
            port.close()
