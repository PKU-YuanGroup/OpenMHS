"""OpenMHS driver for gh.festo-se/festo-dev-applied-motion: a Festo FPosBAPI gantry.

A direct Driver (decorated methods) over the upstream client
``applied_motion.backends.fposbapi_client:FPosBAPIClient``.  That client is
the shared TCP endpoint of the CECC-X PLC running the FPosBAPI CoDeSys
server; the axes and the higher-level ``Gantry`` wrapper are built on it.
The card named ``PythonObjectDriver``; a direct Driver is used instead
because the motion action combines a native call with a read-back position
and a class output schema, which the family's static result map cannot
express (driver-authoring.md, "Choosing the shape").

* reads: the current X/Y/Z position from ``ROB_POS``, PLC parameter 103
  (the global speed), ``SYS_STATUS``, ``IS_ERROR``, ``FPB_ERROR`` and
  ``READ_ERR``;
* one write: PLC parameter 103.  No text file of the clone states the speed
  range of the gantry, so the limit is ``Limit.operator_required``: every
  write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the
  range of its machine (``site-limits.example.json`` shows the overlay);
* actions: home all axes (``HOME``), move to an absolute X/Y/Z position
  (``MOVE_LOC``) and halt motion (``HALT``).  The halt is also the native
  stop (``@estop``) and the safe-state action.

The gantry commands real mechanical motion (README.md:13), so the declared
risk is R2 even though the card's floor is R1.  The clone documents no
independent hardware e-stop; the safe-state action satisfies SAFE-045, and
the driver does not claim a safety-rated stop.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, reset, write

#: PLC parameter 103 is the global speed used by the next motion command.
GLOBAL_SPEED_PARAM = 103


class FestoGantry(Driver):
    device_id = "festo-gantry"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "applied_motion.backends.fposbapi_client:FPosBAPIClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeFPosBAPIClient"}
    vendor, model = "Festo", "CECC-X PLC with the FPosBAPI CoDeSys server"
    display_name = "Festo FPosBAPI gantry (FPosBAPIClient)"
    tags = ["gantry", "cartesian", "motion", "fposbapi", "cecc-x", "plc"]
    facts = [
        Fact("The FPosBAPI server on the CECC-X PLC listens on TCP port 1234 and speaks a line-oriented ASCII "
             "protocol; a successful response ends with 0, NULL, SUCCESS",
             source="upstream_code", ref="src/applied_motion/backends/fposbapi_client.py:4-14"),
        Fact("MOVE_LOC is a coordinated 3-axis move to explicit X, Y and Z target coordinates in mm (a1, a2, a3)",
             source="upstream_code", ref="src/applied_motion/backends/fposbapi_client.py:482-487"),
        Fact("HOME homes all axes through one PLC command", source="upstream_code",
             ref="src/applied_motion/backends/fposbapi_client.py:439-440"),
        Fact("HALT halts the current motion", source="upstream_code",
             ref="src/applied_motion/backends/fposbapi_client.py:512-513"),
        Fact("ROB_POS reports the current position as x_mm, y_mm and z_mm", source="upstream_code",
             ref="src/applied_motion/backends/fposbapi_axis.py:151-154"),
        Fact("Velocity is written to PLC parameter 103 (global speed) in mm/s", source="upstream_code",
             ref="src/applied_motion/backends/fposbapi_axis.py:78-86"),
        Fact("SYS_STATUS returns the system status string of the PLC", source="upstream_code",
             ref="src/applied_motion/backends/fposbapi_client.py:738-746"),
        Fact("IS_ERROR reports whether the gantry is in an error state", source="upstream_code",
             ref="src/applied_motion/backends/fposbapi_client.py:763-771"),
        Fact("FPB_ERROR and READ_ERR report the fieldbus error state and the current error description",
             source="upstream_code", ref="src/applied_motion/backends/fposbapi_client.py:788-820"),
        Fact("RESET_ERR resets the active controller error", source="upstream_code",
             ref="src/applied_motion/backends/fposbapi_client.py:542-543"),
        Fact("Always home the gantry before commanding absolute moves", source="vendor_doc",
             ref="docs/examples/fposbapi.md:92"),
        Fact("The library can command real mechanical motion: commission and test the hardware first, keep the "
             "machine clear, and verify that every target position and velocity is safe", source="vendor_doc",
             ref="README.md:13"),
    ]
    safe_state = "motion halted by the PLC HALT command; the drives stay enabled"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("position", type="object",
          properties={"x": Field("number", unit="mm", description="Current X-axis position"),
                      "y": Field("number", unit="mm", description="Current Y-axis position"),
                      "z": Field("number", unit="mm", description="Current Z-axis position")},
          description="Current X/Y/Z position in millimetres, read with ROB_POS")
    def position(self):
        return self._read_position()

    @read("global_speed", unit="mm/s", description="PLC parameter 103: the global speed used by the next move")
    def global_speed(self):
        values = self.native.get_par(GLOBAL_SPEED_PARAM)
        if not values:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"GET_PAR {GLOBAL_SPEED_PARAM} returned no value")
        return values[0]

    @read("sys_status", type="string", description="System status reported by SYS_STATUS")
    def sys_status(self):
        return self.native.sys_status()

    @read("error_active", type="boolean", description="True when the PLC reports an active error (IS_ERROR)")
    def error_active(self):
        return self.native.is_error()

    @read("error_text", type="string", description="Current error description from READ_ERR")
    def error_text(self):
        return self.native.read_err()

    @read("fieldbus_error", type="string", description="Fieldbus error state from FPB_ERROR")
    def fieldbus_error(self):
        return self.native.fpb_error()

    # -- the one write -------------------------------------------------------------------------------------------
    @write("global_speed", unit="mm/s",
           description="PLC parameter 103: the global speed used by the next move",
           limit=Limit.operator_required(
               "no text file of the clone states the speed range of the configured gantry; the drives, the "
               "mechanics and the process set it, so the site supplies the bound"))
    def set_global_speed(self, value):
        self.native.set_par(GLOBAL_SPEED_PARAM, float(value))
        return self.global_speed()

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.festo-se.home_axes.v1",
            description="Home all axes with one PLC HOME command; the PLC homes X, Y and Z together",
            output={"homed": Field("boolean", description="True when the PLC reports that HOME completed")})
    def home(self):
        self.native.home()
        return {"homed": True}

    @action(cap="cap.motion.cartesian_pose.v1",
            input={"position": Field("object",
                                     description="Target X/Y/Z position in millimetres; home the gantry first")},
            limits={
                "position.x": Limit.operator_required(
                    "no text file of the clone states the X travel of the configured gantry; the site supplies "
                    "the workspace envelope"),
                "position.y": Limit.operator_required(
                    "no text file of the clone states the Y travel of the configured gantry; the site supplies "
                    "the workspace envelope"),
                "position.z": Limit.operator_required(
                    "no text file of the clone states the Z travel of the configured gantry; the site supplies "
                    "the workspace envelope"),
            },
            description="Move the gantry to an absolute X/Y/Z position with MOVE_LOC; the PLC reports SUCCESS "
                        "when the move completes. Home the gantry first (docs/examples/fposbapi.md:92)")
    def cartesian_pose(self, position):
        self.native.move_loc(position["x"], position["y"], position["z"])
        return {"reached": True, "position": self._read_position()}

    @action(name="x-cap.festo-se.halt_motion.v1", safe_state=True,
            description="Halt the current motion with the PLC HALT command (the safe state); it takes no input",
            output={"stopped": Field("boolean",
                                     description="True when the PLC reports that HALT completed")})
    def stop(self):
        self.native.halt()
        return {"stopped": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def emergency_stop(self):
        """The native stop: the runtime latches first, then sends HALT."""
        self.native.halt()

    @reset
    def clear_error(self):
        """Clear the controller error latch after an operator reset is accepted."""
        self.native.reset_err()

    def teardown(self):
        self.native.close()

    # -- helpers -------------------------------------------------------------------------------------------------
    def _read_position(self):
        """Read x, y and z in mm from ROB_POS, with the field layout of FPosBAxis.get_current_axis_position."""
        lines = self.native.send_command("ROB_POS")
        try:
            fields = [part.strip() for part in lines[-1].split(",")]
            return {"x": float(fields[2]), "y": float(fields[3]), "z": float(fields[4])}
        except (IndexError, TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"cannot parse the ROB_POS response: {lines!r}") from exc
