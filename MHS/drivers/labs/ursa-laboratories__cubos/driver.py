"""OpenMHS driver for gh.ursa-laboratories/cubos: a CubOS GRBL gantry.

A direct Driver (decorated methods) over the upstream high-level gantry
``cubos.gantry.gantry:Gantry`` of the pinned clone.  That class wraps the
low-level ``Mill`` serial driver (gantry.py:38), opens the GRBL controller in
``connect`` (gantry.py:86-106), reports the current work coordinates of the
signed deck frame (gantry.py:40-46, 369-375), and moves the tool with
absolute, axis-by-axis G-code (gantry.py:209-223;
gantry_driver/driver.py:942-943).  The card named ``PythonObjectDriver``; a
direct Driver is used instead because each motion action combines a native
blocking call with a position read-back and a class output schema, which the
family's static result map cannot express (driver-authoring.md, "Choosing the
shape").

* reads: the current X/Y/Z work position, the controller status line and the
  health flag;
* actions: home all axes (``Gantry.home``, GRBL ``$H``), move to an absolute
  X/Y/Z work position (``Gantry.move_to``, ``cap.motion.cartesian_pose.v1``),
  stop motion (``Gantry.stop``, GRBL real-time feed hold, safe_state=True) and
  resume a feed-held controller (``Gantry.resume``, declared reenable=True);
* no write: the clone's speed and travel settings belong to the machine
  configuration, not to a value this package can bound.

The e-stop path is the upstream feed hold: ``Mill.stop`` writes the GRBL
real-time ``!`` byte, then queries ``?`` and rejects the stop unless the
controller reports Hold (gantry_driver/driver.py:452-459).  A hold is a pause,
not a power removal; the documented Resume can continue held motion, so the
recovery is the explicit re-enable action and never a reset hook
(docs/operator-ui/gantry.md:93).  The clone documents an independent physical
E-stop on the machine (README.md:30; docs/operator-ui/gantry.md:32).

Every Fact cites a line of the clone at the pinned commit
38ccd0e7109926ac54cc90b018ff674161f87031.  This package is model-authored and
unreviewed: it is checked on the fake backend only (README.md of the
package).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read


class CubosGantry(Driver):
    device_id = "cubos-gantry"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "cubos.gantry.gantry:Gantry"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGantry"}
    vendor, model = "Ursa Laboratories", "CubOS GRBL gantry"
    display_name = "CubOS gantry (cubos.gantry.gantry:Gantry)"
    tags = ["gantry", "cartesian", "motion", "grbl", "cubos"]
    facts = [
        Fact("Gantry is the high-level wrapper around the low-level Mill driver", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry.py:37-38"),
        Fact("The Gantry frame is signed: +X is operator-right, +Y is back and +Z is up; deck_origin puts WPos zero "
             "at the front-left-bottom deck corner", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry.py:40-46"),
        Fact("Gantry.connect opens the CNC mill through self._mill.connect and then validates the GRBL settings and "
             "checks the alarm state", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry.py:86-106"),
        Fact("Gantry.home homes the gantry with GRBL's standard homing command through Mill.home", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry.py:158-164"),
        Fact("Gantry.move_to takes absolute gantry coordinates x, y and z and an optional travel_z for the height "
             "during XY travel", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry.py:209-223"),
        Fact("Mill.move_to documents the direct move order as X, then Y, then Z, with no diagonal interpolation",
             source="upstream_code", ref="packages/core/src/cubos/gantry/gantry_driver/driver.py:942-943"),
        Fact("execute_command writes the command and calls _wait_until_idle when the command does not start with $",
             source="upstream_code", ref="packages/core/src/cubos/gantry/gantry_driver/driver.py:413-419"),
        Fact("_wait_until_idle blocks until the status line contains idle and raises on an error, an alarm or a "
             "timeout", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry_driver/driver.py:656-678"),
        Fact("Gantry.stop returns immediately in offline mode and otherwise calls Mill.stop", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry.py:336-342"),
        Fact("Mill.stop sends the real-time feed hold and verifies that the controller entered Hold; it raises when "
             "the status is not Hold", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry_driver/driver.py:452-459"),
        Fact("GRBL strips real-time characters out of the stream wherever they appear, and the write lock serialises "
             "only the write syscall, never a command/response cycle", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry_driver/driver.py:95-106"),
        Fact("Gantry.resume delegates to Mill.resume when not offline",
             source="upstream_code", ref="packages/core/src/cubos/gantry/gantry.py:358-364"),
        Fact("Mill.resume writes the real-time cycle-start byte ~ to the serial controller",
             source="upstream_code", ref="packages/core/src/cubos/gantry/gantry_driver/driver.py:466-469"),
        Fact("A HOLD pauses motion; Resume can continue the held motion, so the path must be checked before resuming",
             source="vendor_doc", ref="docs/operator-ui/gantry.md:93"),
        Fact("Gantry.get_coordinates returns the current gantry coordinates as a dict with x, y and z",
             source="upstream_code", ref="packages/core/src/cubos/gantry/gantry.py:369-375"),
        Fact("Gantry.get_status returns the current status string with normalized coordinates", source="upstream_code",
             ref="packages/core/src/cubos/gantry/gantry.py:325-331"),
        Fact("The operator UI reports position as current work coordinates; Idle means ready, Jog/Run means moving "
             "and ALARM means the controller is locked", source="vendor_doc",
             ref="docs/operator-ui/gantry.md:73-75"),
        Fact("The Working Volume is the allowed travel range of the configured machine; it cannot detect misplaced "
             "labware or loose objects", source="vendor_doc", ref="docs/operator-ui/gantry.md:22"),
        Fact("Working volume bounds are machine-specific and calibrated: use Calibration to measure the physical "
             "working volume", source="vendor_doc", ref="docs/gantry.md:155-169"),
        Fact("Homing and jogging move real hardware; before connecting, clear the deck, check the travel path and keep "
             "the E-stop within reach", source="vendor_doc", ref="docs/operator-ui/gantry.md:29-32"),
        Fact("CubOS can move real lab hardware; keep an E-stop reachable and start with minimal motion",
             source="vendor_doc", ref="README.md:29-31"),
        Fact("Always home after connecting; homing drives each axis to its end stops to establish a known reference",
             source="vendor_doc", ref="docs/operator-ui/gantry.md:49-54"),
        Fact("After a physical crash, hit the E-stop if the gantry is still moving, then re-home; never trust WPos "
             "after a crash without re-homing first", source="vendor_doc",
             ref="docs/troubleshooting.md:85-91"),
    ]
    safe_state = ("GRBL feed hold acknowledged by a controller status containing Hold; the held path remains queued "
                  "and an explicit resume can continue it; power is not removed")
    estop_physical_ref = "docs/operator-ui/gantry.md:32"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("position", type="object",
          properties={"x": Field("number", unit="mm", description="Current X-axis work position"),
                      "y": Field("number", unit="mm", description="Current Y-axis work position"),
                      "z": Field("number", unit="mm", description="Current Z-axis work position")},
          description="Current X/Y/Z work position in millimetres, read with Gantry.get_coordinates")
    def position(self):
        return self._read_position()

    @read("status", type="string", description="Controller status line as Gantry.get_status normalizes it")
    def status(self):
        return self.native.get_status()

    @read("healthy", type="boolean",
          description="True while the controller link is open and its status reports no alarm or error")
    def healthy(self):
        return bool(self.native.is_healthy())

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.ursa-laboratories.home_axes.v1",
            description="Home all axes with GRBL's standard homing command; the native home takes no speed or "
                        "axis selection",
            output={"homed": Field("boolean", description="True when the native home returned")})
    def home_axes(self):
        self._require_motion_ready(allow_alarm=True)
        self.native.home()
        return {"homed": True}

    @action(cap="cap.motion.cartesian_pose.v1",
            input={"position": Field("object",
                                     description="Target X/Y/Z work position in millimetres; home the gantry first")},
            limits={
                "position.x": Limit.operator_required(
                    "the clone stores the X travel in the calibrated working_volume of each machine configuration "
                    "and states no machine-independent bound; the site supplies the workspace envelope"),
                "position.y": Limit.operator_required(
                    "the clone stores the Y travel in the calibrated working_volume of each machine configuration "
                    "and states no machine-independent bound; the site supplies the workspace envelope"),
                "position.z": Limit.operator_required(
                    "the clone stores the Z travel in the calibrated working_volume of each machine configuration "
                    "and states no machine-independent bound; the site supplies the workspace envelope"),
            },
            description="Move the tool to an absolute X/Y/Z work position with Gantry.move_to; the native call "
                        "blocks until the controller is Idle, then the position is read back")
    def cartesian_pose(self, position):
        self._require_motion_ready()
        self.native.move_to(position["x"], position["y"], position["z"])
        return {"reached": True, "position": self._read_position()}

    @action(name="x-cap.ursa-laboratories.stop_motion.v1", safe_state=True,
            description="Stop all motion with the GRBL real-time feed hold (the native Gantry.stop, the safe "
                        "state); the native stop verifies that the controller reports Hold and takes no "
                        "deceleration input",
            output={"stopped": Field("boolean",
                                     description="True when the native stop verified the controller Hold state")})
    def stop_motion(self):
        self.native.stop()
        return {"stopped": True}

    @action(name="x-cap.ursa-laboratories.resume_motion.v1", reenable=True,
            description="Release a feed hold with the GRBL real-time cycle-start character (the native "
                        "Gantry.resume).  This is the declared recovery after an operator reset, never a reset "
                        "step; the held path must be checked first because a resume can continue held motion",
            output={"resumed": Field("boolean",
                                     description="True when the native resume wrote the cycle-start character")})
    def resume_motion(self):
        self.native.resume()
        return {"resumed": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def emergency_stop(self):
        """The native stop: the runtime latches first, then sends the GRBL real-time feed hold."""
        self.native.stop()

    def teardown(self):
        self.native.disconnect()

    # -- helpers -------------------------------------------------------------------------------------------------
    def _require_motion_ready(self, allow_alarm=False):
        status = self.native.get_status()
        if not isinstance(status, str):
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the controller returned no status string")
        state = status.strip().lstrip("<").split("|", 1)[0].split(":", 1)[0].lower()
        allowed = ("idle", "alarm") if allow_alarm else ("idle",)
        if state not in allowed:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               f"controller is not ready for motion ({status!r}); a feed hold needs explicit resume")
        self.check_cancelled()

    def _read_position(self):
        coords = self.native.get_coordinates()
        try:
            return {"x": float(coords["x"]), "y": float(coords["y"]), "z": float(coords["z"])}
        except (KeyError, TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"cannot read x/y/z from the gantry coordinates: {coords!r}") from exc
