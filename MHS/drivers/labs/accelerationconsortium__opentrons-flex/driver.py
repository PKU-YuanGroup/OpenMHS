"""OpenMHS driver for gh.accelerationconsortium/opentrons-flex: the Opentrons Flex (OT-3) motion controller.

A direct Driver (decorated methods) over the upstream class
``unitelabs.opentrons_flex.io.flex_motion:FlexMotionController``.  That class
wraps the Opentrons ``OT3API`` and is asynchronous: every motion, light and
halt member is a coroutine function, and ``move_to`` takes an ``OT3Mount`` plus
an ``opentrons.types.Point`` in deck coordinates.  ``native.py`` is the hardware
factory; it wraps the controller with a thin adapter that converts the driver's
plain ``left`` and ``[x, y, z]`` values to those upstream types.  The fake
backend implements the same adapter contract so that the gate can exercise the
driver without the uninstalled Opentrons stack.

DEVIATION FROM THE CARD: the card's helper is ``PythonObjectDriver``.  A direct
Driver is used instead because the primary interface is an async hardware
controller with typed mount/Point arguments and a class output schema; the
family's static method/result tables cannot express that (driver-authoring.md,
"Choosing the shape").  The card's own ``decision`` is ``direct-driver``.

* reads: the OT3 simulator flag, the status-bar and deck lights, and the cached
  machine status (E-stop state, door state, error flag);
* writes: the status-bar and deck lights;
* actions: home every axis (``x-cap.accelerationconsortium.home_all.v1``, also the
  declared re-enable), move one mount to an absolute deck position
  (``cap.motion.cartesian_pose.v1``) and halt all motion
  (``x-cap.accelerationconsortium.halt_motion.v1``, also the declared safe state);
* the native stop is ``FlexMotionController.stop`` (flex_motion.py:291-305), the
  call behind the connector's own SiLA EmergencyStop (motion_control.py:440-461):
  it cancels the registered in-flight operation and awaits the OT3API ``halt()``
  without taking the operation lock.  Nothing senses motor standstill afterwards;
  what ``OT3API.halt()`` does on the CAN bus is Opentrons code outside the clone.
  The independent hardware E-stop is the Flex E-stop the clone's operator
  checklist tells the operator to keep reachable.

Recovery (SAFE-042, CORE-086): after a halt the connector refuses every actuation
except a full home (recovery_state.py:24-54, flex_motion.py:239-249, 496-499).
The full home is therefore the declared re-enable (``reenable=True``): the latch
refuses it, a safety reset never runs it (there is no ``@reset`` hook), and it is
the first command after a reset that may move the robot.

Only a small, safety-relevant part of the connector is bound: the mount for
``cartesian_pose`` is the LEFT pipette mount because the catalogue class has no
mount field.  Pipetting, nozzle configuration, gripper, modules, calibration
and the upstream simulator are not covered; see facts.md and RESULT.json.

Every Fact cites a line of the clone at the pinned commit
2639016ee9f234949aaf596c2ab2b93694eb0e0b.  This package is model-authored and
unreviewed: it is checked on the fake backend only (RESULT.json).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The OT3 mount this binding moves.  cap.motion.cartesian_pose.v1 has no mount
#: field; the deployment adapter accepts "left", "right" and "gripper".
PIPETTE_MOUNT = "left"

#: The upstream error a refused move raises when the robot is recovery-gated after a halt
#: (flex_motion.py:496-499) or when OT3API reports an unknown position (_errors.py:386-389).
#: The driver matches it by class name: the Opentrons stack is not importable at gate time.
NOT_HOMED_ERROR = "NotHomedError"


class OpentronsFlex(Driver):
    device_id = "flex"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "unitelabs.opentrons_flex.io.flex_motion:FlexMotionController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOpentronsFlex"}
    vendor, model = "Opentrons", "Flex (OT-3)"
    display_name = "Opentrons Flex motion controller (FlexMotionController)"
    tags = ["opentrons", "flex", "ot-3", "gantry", "robot-arm", "motion", "asyncio"]
    facts = [
        Fact("FlexMotionController is a thin wrapper of OT3API: it reuses the OT3API implementation (CAN, "
             "calibration), provides a surface for motion, pipette and lights, and serialises hardware access "
             "through a lock shared with HardwareProxy",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:99-110"),
        Fact("stop() is documented to halt all motion without waiting for the operation lock: it marks the "
             "recovery state halted, runs the OT3API halt() as a task and awaits it to completion; a "
             "cancellation that arrives meanwhile is re-raised only after the halt finished",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:291-305"),
        Fact("mark_halted() increments the operation generation, requires a full robot home and cancels every "
             "active robot operation task other than the current one",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/recovery_state.py:47-54"),
        Fact("operation_ready is false while a full re-home is required, and the operator guidance then begins "
             "with 'Fully re-home all robot axes'",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/recovery_state.py:24-45"),
        Fact("_assert_operation_ready raises NotHomedError ('The robot is recovery-gated. ... before retrying.') "
             "when the recovery state is not operation-ready",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:496-499"),
        Fact("A cancelled actuation registered by _active_operation marks the robot halted and awaits an OT3API "
             "halt() before its hardware lock is released; a failure of that halt is logged, not raised",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:208-234"),
        Fact("home(axes=None) homes all axes; the operation-ready check runs only for a partial home (axes "
             "given), and a full home that no halt interrupted marks the robot fully homed",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:239-249"),
        Fact("move_to(mount, point, speed=None) checks the recovery gate, validates the target, moves the mount "
             "to the absolute deck point and returns the gantry position read back after the move",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:255-269"),
        Fact("The absolute-target validation rejects deck targets outside the transformed Flex machine-axis "
             "bounds of the OT3API backend",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:512-534"),
        Fact("translate_motion_errors turns the OT3API PositionUnknownError and PositionEstimationInvalidError "
             "into NotHomedError and OutOfBoundsMove into MovementOutOfBoundsError",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/_errors.py:370-395"),
        Fact("NotHomedError is documented as a move refused because the robot's position is unknown: home the "
             "robot before requesting a move",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/_errors.py:177-184"),
        Fact("The connector's SiLA EmergencyStop runs FlexMotionController.stop() and states that a re-home is "
             "required before resuming",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/features/motion_control.py:440-461"),
        Fact("The connector's SiLA Home homes every axis and is documented as required after an emergency stop "
             "before further motion",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/features/motion_control.py:163-182"),
        Fact("The parity matrix names MotionControlFeature.EmergencyStop as the single pre-emptive, robot-wide "
             "halt path", source="vendor_doc", ref="docs/parity_matrix.json:124"),
        Fact("set_lights(button=None, rails=None) sets the status-bar and/or deck lights under the operation "
             "lock; get_lights() returns the light state through the lock's observation view",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:714-722"),
        Fact("The lock's observation view acquires the underlying lock with acquire() unless that lock offers "
             "acquire_observation, waiting at most the lock's timeout_s",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/hardware_proxy.py:65-89"),
        Fact("machine_status() reads the cached E-stop state, the door state and the derived error flag without "
             "CAN I/O or the operation lock", source="upstream_code",
             ref="src/unitelabs/opentrons_flex/io/flex_motion.py:181-194"),
        Fact("is_simulating reports whether the underlying OT3API is a simulator backend",
             source="upstream_code", ref="src/unitelabs/opentrons_flex/io/flex_motion.py:174-177"),
        Fact("build() makes a standalone controller with its own OT3API and lock: simulate=True builds the OT3API "
             "hardware simulator, simulate=False the real CAN hardware controller", source="upstream_code",
             ref="src/unitelabs/opentrons_flex/io/flex_motion.py:130-153"),
        Fact("disconnect() releases the hardware resources of a standalone controller by calling the OT3API "
             "clean_up() under the operation lock", source="upstream_code",
             ref="src/unitelabs/opentrons_flex/io/flex_motion.py:726-729"),
        Fact("The README says one shared OT3API serialises the SiLA and HTTP servers so their CAN commands cannot "
             "interleave, and avoids the 'hardware already initialised' error two separate processes would hit",
             source="vendor_doc", ref="README.md:16-20"),
        Fact("The README says the standard opentrons-robot-server service is disabled on deployment and the "
             "sila2-connector service owns the hardware", source="vendor_doc", ref="README.md:32-33"),
        Fact("Motion is exposed per mount (LEFT, RIGHT, GRIPPER) in deck coordinates (x, y, z mm), matching the "
             "Flex hardware API", source="vendor_doc", ref="README.md:39-40"),
        Fact("The operator preparation checklist says to close the door, disengage the E-stop, clear all travel "
             "corridors and keep the E-stop reachable", source="vendor_doc",
             ref="docs/flex_system_acceptance.md:56-58"),
    ]
    safe_state = ("FlexMotionController.stop() has cancelled the registered in-flight operation and awaited the "
                  "OT3API halt(), and the connector refuses every actuation except a full home (the declared "
                  "re-enable) until one completes; nothing senses motor standstill, and whether the motors stay "
                  "energised or hold position after the halt is not stated in the clone (OT3API is outside it)")
    estop_physical_ref = "docs/flex_system_acceptance.md:58"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("simulating", type="boolean",
          description="True when the backend drives the Opentrons OT3 simulator instead of real CAN hardware")
    def simulating(self):
        return bool(self.native.is_simulating)

    @read("lights_button", type="boolean", description="True while the status-bar light is on")
    async def lights_button(self):
        return bool((await self.native.get_lights()).get("button", False))

    @read("lights_rails", type="boolean", description="True while the deck rail lights are on")
    async def lights_rails(self):
        return bool((await self.native.get_lights()).get("rails", False))

    @read("machine_status", type="object",
          properties={
              "estop": Field("string", description="Cached E-stop state: DISENGAGED, PHYSICALLY_ENGAGED, "
                                                    "LOGICALLY_ENGAGED or NOT_PRESENT"),
              "door_open": Field("boolean", description="True while the robot door is reported open"),
              "is_error_state": Field("boolean", description="True when the cached E-stop state is an error state"),
          },
          description="Cached machine safety status: E-stop state, door state and the derived error flag")
    def machine_status(self):
        state = self.native.machine_status()
        return {
            "estop": str(state.estop),
            "door_open": bool(state.door_open),
            "is_error_state": bool(state.is_error_state),
        }

    # -- writes --------------------------------------------------------------------------------------------------
    @write("lights_button", type="boolean", description="Switch the status-bar light on or off")
    async def set_lights_button(self, value):
        await self.native.set_lights(button=bool(value))
        return bool((await self.native.get_lights()).get("button", False))

    @write("lights_rails", type="boolean", description="Switch the deck rail lights on or off")
    async def set_lights_rails(self, value):
        await self.native.set_lights(rails=bool(value))
        return bool((await self.native.get_lights()).get("rails", False))

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.accelerationconsortium.home_all.v1", reenable=True,
            description="Home every Flex axis with FlexMotionController.home(); the declared re-enable: after a "
                        "halt or an e-stop the connector refuses every other actuation until this full home "
                        "completes. The latch refuses it and a safety reset never runs it.",
            input={},
            output={"homed": Field("boolean", description="True when the full home command returned")})
    async def home(self):
        """The new start command after a reset (SAFE-042, CORE-086): a full home, flex_motion.py:239-249."""
        await self.native.home()
        return {"homed": True}

    @action(cap="cap.motion.cartesian_pose.v1",
            input={"position": Field("object", description="Absolute deck position in millimetres",
                                     properties={
                                         "x": Field("number", unit="mm", required=True,
                                                    description="Deck X coordinate in millimetres"),
                                         "y": Field("number", unit="mm", required=True,
                                                    description="Deck Y coordinate in millimetres"),
                                         "z": Field("number", unit="mm", required=True,
                                                    description="Deck Z coordinate in millimetres"),
                                     })},
            limits={
                "position.x": Limit.operator_required(
                    "no text file of the clone states the deck X travel of the configured Flex; the site supplies "
                    "the workspace envelope"),
                "position.y": Limit.operator_required(
                    "no text file of the clone states the deck Y travel of the configured Flex; the site supplies "
                    "the workspace envelope"),
                "position.z": Limit.operator_required(
                    "no text file of the clone states the deck Z travel of the configured Flex; the site supplies "
                    "the workspace envelope"),
            },
            description="Move the LEFT pipette mount to an absolute deck X/Y/Z position in millimetres with "
                        "FlexMotionController.move_to(); the class has no mount field, so the binding is the LEFT "
                        "mount (native.py accepts left, right and gripper). Refused PRECONDITION_UNMET while the "
                        "robot needs a full home (after a halt).")
    async def cartesian_pose(self, position):
        try:
            point = (float(position["x"]), float(position["y"]), float(position["z"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"position needs numeric x, y and z: {exc}") from exc
        try:
            result = await self.native.move_to(PIPETTE_MOUNT, list(point))
        except Exception as exc:
            if type(exc).__name__ == NOT_HOMED_ERROR:
                # The upstream refused the move before any motion (flex_motion.py:260, 496-499; _errors.py:386-389).
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "the Flex refused the move: it needs a full home first (after a halt, or while "
                                   "its position is unknown); send x-cap.accelerationconsortium.home_all.v1") from exc
            raise
        return {
            "reached": True,
            "position": {"x": float(result.x), "y": float(result.y), "z": float(result.z)},
        }

    @action(name="x-cap.accelerationconsortium.halt_motion.v1", safe_state=True,
            description="Halt all motion with FlexMotionController.stop() (the OT3API halt path); it takes no "
                        "input, is the declared safe state, and leaves the robot needing a full home",
            input={},
            output={"stopped": Field("boolean", description="True when the native halt call returned")})
    async def stop(self):
        await self.native.stop()
        return {"stopped": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="stop")
    async def emergency_stop(self):
        """The native stop: the runtime latches first, then runs the OT3API halt path (flex_motion.py:291-305)."""
        await self.native.stop()

    # No @reset: a safety reset releases the latch and re-arms nothing (SAFE-042).  The full home above is the
    # declared re-enable and is sent as its own command after the reset.

    # -- lifecycle -----------------------------------------------------------------------------------------------
    async def teardown(self):
        """Release the hardware resources as the connector's own exit path does (flex_motion.py:726-729)."""
        await self.native.disconnect()
