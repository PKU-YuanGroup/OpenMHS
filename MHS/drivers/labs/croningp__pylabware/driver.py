"""OpenMHS driver for gh.croningp/pylabware: a Tricontinent C3000 syringe pump.

A direct Driver (decorated methods) over the upstream serial class
``PyLabware.devices.tricontinent_c3000:C3000SyringePump``.  The upstream class builds every DT-protocol command from a
switch address, a command letter and an argument: the prefix is ``"/"`` plus the switch address, the terminator is the
autorun ``"R\\r\\n"`` and ``args_delimiter`` is empty (PyLabware/devices/tricontinent_c3000.py:321-333).  A command
table cannot reproduce bytes the upstream assembles at run time, so this is a direct driver over the upstream class,
not the card's PythonObjectDriver helper (see RESULT.json notes).

* reads: absolute plunger position, valve position, initialized, idle and connected;
* one write: the valve position (get and set, the setter reads the position back);
* actions: relative dispense/withdraw, absolute/relative plunger moves, homing, the raw motor settings (speed, start
  and stop velocity, predefined speed code, ramp code and resolution mode) and the safe-state stop.  The clone has no
  getter for the motor settings (``get_speed`` raises NotImplementedError, tricontinent_c3000.py:506-507), so they are
  extension actions that report the value they sent, not writable resource state;
* plunger travel and dispensed amount: no line of the clone states a bound for either count, so those inputs are
  ``Limit.operator_required`` and every call is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the travel
  of its syringe (``site-limits.example.json`` shows the overlay);
* the native stop sends the ``T`` command (tricontinent_c3000.py:222 and 494-497); the e-stop and the safe-state action
  both call it.

Every Fact cites a line of the clone at the pinned commit (fbf287c7866ad3ac1e1a3bc44845035b8ae4a7b9).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The upstream file of the native class, relative to the clone root.
MODULE = "PyLabware/devices/tricontinent_c3000.py"

#: The valve-position strings the upstream setter accepts: I/O and the IOBE positions, B and E (tricontinent_c3000.py:
#: 588-595), with the numbered I1..I6/O1..O6 forms from VALVE_POSITIONS (tricontinent_c3000.py:44-56).
VALVE_POSITIONS = ["I", "O", "I1", "I2", "I3", "I4", "I5", "I6",
                   "O1", "O2", "O3", "O4", "O5", "O6", "B", "E"]

#: Ramp codes 1 to 20 and speed codes 0 to 40 (the keys of RAMP_PLOPE_MODES and SPEED_MODES).
RAMP_CODES = [str(value) for value in range(1, 21)]
SPEED_CODES = [str(value) for value in range(0, 41)]


class C3000Pump(Driver):
    device_id = "c3000-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "PyLabware.devices.tricontinent_c3000:C3000SyringePump"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeC3000SyringePump"}
    vendor, model = "Tricontinent", "C3000"
    display_name = "Tricontinent C3000 syringe pump (PyLabware)"
    tags = ["syringe-pump", "pump", "valve", "serial", "dt-protocol"]
    facts = [
        Fact("C3000SyringePump is the PyLabware class for the Tricontinent C3000 syringe pump with integrated valve, "
             "based on the operation manual 8694-12 E", source="upstream_code", ref=f"{MODULE}:289-293"),
        Fact("The DT-protocol command prefix is '/' plus the switch address; the terminator is the autorun command "
             "PRG_RUN plus CRLF, the reply prefix is '/0', the reply terminator is ETX CRLF and arguments are not "
             "separated", source="upstream_code", ref=f"{MODULE}:321-333"),
        Fact("is_connected queries the firmware version and returns False only on a connection error",
             source="upstream_code", ref=f"{MODULE}:389-399"),
        Fact("is_initialized reads the initialized status and returns False on a connection error",
             source="upstream_code", ref=f"{MODULE}:449-458"),
        Fact("is_idle reads the status byte and returns False when bit 5 reports busy or an error is present",
             source="upstream_code", ref=f"{MODULE}:460-484"),
        Fact("The absolute-position query is the '?' command (GET_SYR_POS)", source="upstream_code",
             ref=f"{MODULE}:233-234"),
        Fact("get_plunger_position sends the absolute-position query and returns an integer", source="upstream_code",
             ref=f"{MODULE}:530-535"),
        Fact("The valve-position query is '?6' (GET_VALVE_POS) and its reply is upper-cased", source="upstream_code",
             ref=f"{MODULE}:249-250"),
        Fact("get_valve_position sends the valve-position query", source="upstream_code", ref=f"{MODULE}:605-610"),
        Fact("move_home is move_plunger_absolute(0)", source="upstream_code", ref=f"{MODULE}:516-517"),
        Fact("move_plunger_absolute sends the absolute move command and waits until the pump is idle",
             source="upstream_code", ref=f"{MODULE}:519-528"),
        Fact("move_plunger_relative converts its argument with int(), withdraws when it is positive and dispenses its "
             "absolute value otherwise", source="upstream_code", ref=f"{MODULE}:537-545"),
        Fact("dispense sends the relative dispense command (SYR_SPIT_REL)", source="upstream_code",
             ref=f"{MODULE}:547-557"),
        Fact("withdraw sends the relative aspiration command (SYR_SUCK_REL)", source="upstream_code",
             ref=f"{MODULE}:559-568"),
        Fact("The valve-position strings are built from I, O, B and E with the numbered I1..I6 and O1..O6 forms; "
             "VALVE_POSITIONS holds the bare digits and the empty IOBE argument", source="upstream_code",
             ref=f"{MODULE}:44-56"),
        Fact("set_valve_position picks the command from the first character (I, O, B or E) and sends the rest as "
             "the argument", source="upstream_code", ref=f"{MODULE}:588-603"),
        Fact("SET_MAX_VEL checks a maximum velocity of 1 to 48000 increments per second", source="upstream_code",
             ref=f"{MODULE}:269-270"),
        Fact("set_speed sends SET_MAX_VEL", source="upstream_code", ref=f"{MODULE}:499-504"),
        Fact("SET_START_VEL checks a starting velocity of 1 to 8000", source="upstream_code",
             ref=f"{MODULE}:267-268"),
        Fact("set_start_velocity sends SET_START_VEL", source="upstream_code", ref=f"{MODULE}:619-624"),
        Fact("SET_STOP_VEL checks a cut-off velocity of 1 to 21600", source="upstream_code",
             ref=f"{MODULE}:273-274"),
        Fact("set_stop_velocity sends SET_STOP_VEL", source="upstream_code", ref=f"{MODULE}:626-631"),
        Fact("SPEED_MODES is keyed by the speed codes 0 to 40", source="upstream_code", ref=f"{MODULE}:101-144"),
        Fact("SET_MAX_VEL_CODE checks its argument against the SPEED_MODES keys", source="upstream_code",
             ref=f"{MODULE}:271-272"),
        Fact("set_predefined_speed sends SET_MAX_VEL_CODE", source="upstream_code", ref=f"{MODULE}:509-514"),
        Fact("RAMP_PLOPE_MODES is keyed by the ramp codes 1 to 20", source="upstream_code", ref=f"{MODULE}:77-99"),
        Fact("SET_RAMP_PLOPE checks its argument against the RAMP_PLOPE_MODES keys", source="upstream_code",
             ref=f"{MODULE}:265-266"),
        Fact("set_ramp_slope sends SET_RAMP_PLOPE", source="upstream_code", ref=f"{MODULE}:612-617"),
        Fact("RESOLUTION_MODES is keyed by N0, N1 and N2", source="upstream_code", ref=f"{MODULE}:70-75"),
        Fact("SET_RES_MODE checks its argument against the RESOLUTION_MODES keys", source="upstream_code",
             ref=f"{MODULE}:277-278"),
        Fact("set_resolution_mode sends SET_RES_MODE", source="upstream_code", ref=f"{MODULE}:633-638"),
        Fact("The usage guide calls the relative amounts units and shows withdraw(200) leaving position 200 and "
             "dispense(200) returning it to 0", source="vendor_doc", ref="docs/usage.rst:78-90"),
        Fact("PRG_TERM is the terminate command 'T'", source="upstream_code", ref=f"{MODULE}:222"),
        Fact("stop sends PRG_TERM, which terminates command execution immediately", source="upstream_code",
             ref=f"{MODULE}:494-497"),
        Fact("get_speed raises NotImplementedError, so the configured speed cannot be read back",
             source="upstream_code", ref=f"{MODULE}:506-507"),
    ]
    safe_state = ("plunger motion stopped (the native stop sends T); the valve, the motor settings and the plunger "
                  "position are left unchanged")

    # -- reads --------------------------------------------------------------------------------------------------
    @read("plunger_position", type="integer", unit="1",
          description="Absolute plunger position in device increments")
    def plunger_position(self):
        return self.native.get_plunger_position()

    @read("valve_position", type="string",
          description="Distribution valve position: I, O, I1..I6, O1..O6, B or E")
    def valve_position(self):
        return self.native.get_valve_position()

    @read("initialized", type="boolean",
          description="True once the pump reports that its plunger and valve have been initialized")
    def initialized(self):
        return self.native.is_initialized()

    @read("idle", type="boolean", description="True while the pump reports that it is idle (not busy and no error)")
    def idle(self):
        return self.native.is_idle()

    @read("connected", type="boolean", description="True when the pump answers the firmware-version query")
    def connected(self):
        return self.native.is_connected()

    # -- the one write ------------------------------------------------------------------------------------------
    @write("valve_position", type="string",
           enum=VALVE_POSITIONS,
           description="Distribution valve position; the setter writes it and reads the position back")
    def set_valve_position(self, value):
        self.native.set_valve_position(value)
        return self.native.get_valve_position()

    # -- plunger and valve actions ------------------------------------------------------------------------------
    @action(name="x-cap.croningp.transfer.v1",
            description="Dispense or withdraw a number of plunger increments",
            input={
                "increments": Field(
                    "number", unit="1", description="Plunger increments to move",
                    limit=Limit.operator_required(
                        "no line of the clone states the plunger travel or the dispensed amount of this pump; the "
                        "site supplies the travel of its syringe in site-limits.json")),
                "direction": Field(
                    "string", enum=["dispense", "withdraw"],
                    description="dispense pushes the plunger in (native dispense), withdraw pulls it out (native "
                                "withdraw)"),
            },
            output={"plunger_position": Field("integer", unit="1",
                                               description="Absolute plunger position after the move")})
    def transfer(self, increments, direction):
        if direction == "dispense":
            self.native.dispense(increments)
        else:
            self.native.withdraw(increments)
        return {"plunger_position": self.native.get_plunger_position()}

    @action(name="x-cap.croningp.move_plunger.v1",
            description="Move the plunger to an absolute or a relative position",
            input={
                "position": Field(
                    "integer", unit="1", description="Absolute position, or the signed relative move",
                    limit=Limit.operator_required(
                        "no line of the clone states the plunger travel of this pump; the site supplies the travel "
                        "of its syringe in site-limits.json")),
                "mode": Field("string", enum=["absolute", "relative"],
                              description="absolute calls move_plunger_absolute, relative calls "
                                          "move_plunger_relative (positive withdraws, negative dispenses)"),
            },
            output={"plunger_position": Field("integer", unit="1",
                                               description="Absolute plunger position after the move")})
    def move_plunger(self, position, mode):
        if mode == "absolute":
            self.native.move_plunger_absolute(position)
        else:
            self.native.move_plunger_relative(position)
        return {"plunger_position": self.native.get_plunger_position()}

    @action(name="x-cap.croningp.move_home.v1",
            description="Home the plunger with the native move_home (an absolute move to position 0)",
            output={"plunger_position": Field("integer", unit="1",
                                               description="Absolute plunger position after homing")})
    def move_home(self):
        self.native.move_home()
        return {"plunger_position": self.native.get_plunger_position()}

    # -- motor-setting actions ----------------------------------------------------------------------------------
    @action(name="x-cap.croningp.set_speed.v1",
            description="Set the maximum plunger velocity in increments per second",
            input={"speed": Field(
                "integer", unit="1/s", description="Maximum velocity in increments per second",
                limit=Limit(min=1, max=48000, source="upstream_code", ref=f"{MODULE}:270"))},
            output={"speed": Field("integer", unit="1/s", description="The value sent to the pump")})
    def set_speed(self, speed):
        self.native.set_speed(speed)
        return {"speed": speed}

    @action(name="x-cap.croningp.set_start_velocity.v1",
            description="Set the starting velocity of the plunger ramp",
            input={"start_velocity": Field(
                "integer", unit="1/s", description="Starting velocity of the plunger ramp (the command check is 1 to 8000)",
                limit=Limit(min=1, max=8000, source="upstream_code", ref=f"{MODULE}:268"))},
            output={"start_velocity": Field("integer", unit="1/s", description="The value sent to the pump")})
    def set_start_velocity(self, start_velocity):
        self.native.set_start_velocity(start_velocity)
        return {"start_velocity": start_velocity}

    @action(name="x-cap.croningp.set_stop_velocity.v1",
            description="Set the cut-off velocity at the end of the plunger ramp",
            input={"stop_velocity": Field(
                "integer", unit="1/s", description="Cut-off velocity at the end of the plunger ramp (the command check is 1 to 21600)",
                limit=Limit(min=1, max=21600, source="upstream_code", ref=f"{MODULE}:274"))},
            output={"stop_velocity": Field("integer", unit="1/s", description="The value sent to the pump")})
    def set_stop_velocity(self, stop_velocity):
        self.native.set_stop_velocity(stop_velocity)
        return {"stop_velocity": stop_velocity}

    @action(name="x-cap.croningp.set_predefined_speed.v1",
            description="Select a predefined maximum-velocity code (SPEED_MODES)",
            input={"speed_code": Field(
                "string", enum=SPEED_CODES, description="SPEED_MODES key from 0 to 40")},
            output={"speed_code": Field("string", description="The code sent to the pump")})
    def set_predefined_speed(self, speed_code):
        self.native.set_predefined_speed(speed_code)
        return {"speed_code": speed_code}

    @action(name="x-cap.croningp.set_ramp_slope.v1",
            description="Select an acceleration/deceleration ramp code (RAMP_PLOPE_MODES)",
            input={"ramp_code": Field(
                "string", enum=RAMP_CODES, description="RAMP_PLOPE_MODES key from 1 to 20")},
            output={"ramp_code": Field("string", description="The code sent to the pump")})
    def set_ramp_slope(self, ramp_code):
        self.native.set_ramp_slope(ramp_code)
        return {"ramp_code": ramp_code}

    @action(name="x-cap.croningp.set_resolution_mode.v1",
            description="Select the plunger motor resolution mode N0, N1 or N2",
            input={"resolution_mode": Field(
                "string", enum=["N0", "N1", "N2"], description="RESOLUTION_MODES key")},
            output={"resolution_mode": Field("string", description="The mode sent to the pump")})
    def set_resolution_mode(self, resolution_mode):
        self.native.set_resolution_mode(resolution_mode)
        return {"resolution_mode": resolution_mode}

    # -- safety --------------------------------------------------------------------------------------------------
    @action(name="x-cap.croningp.stop_pump.v1", safe_state=True,
            description="Safe state: stop the current plunger program with the native stop (T); it takes no input",
            output={"stopped": Field("boolean", description="True once the native stop has been sent")})
    def stop_pump(self):
        self.native.stop()
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends the T command."""
        self.native.stop()
