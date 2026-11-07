"""OpenMHS driver for the simulated Franka Hand of gh.barisyazici/libfranka-sim.

The upstream repository simulates a Franka Research 3 arm and its Franka Hand.
This package covers the hand: a direct Driver over
``franka_sim.gripper.physics:FrankaHandPhysics``, the physics-backed gripper
backend.  The arm FCI protocol and the mobile-duo scene are separate upstream
subsystems and are not bound here.

The hand is a two-finger gripper with a 0-0.08 m stroke (docs/robot-state.md
:202).  ``get_state`` reports the summed finger width in metres, the maximum
width, the grasp flag and a stub temperature (physics.py:222-231).  ``homing``
and ``move`` drive the fingers open or to a width, ``grasp`` closes them until
they stall and applies the epsilon band, and ``stop`` reopens them.  The
simulator documents the important divergences from the real hand: the
commanded force is not a limit and is not read (docs/robot-state.md:203,
:251-259), the commanded speed is ignored (docs/robot-state.md:201), and
``stop()`` reopens instead of halting in place (docs/robot-state.md:271-276).

Only ``cap.manipulation.grasp.v1`` and ``cap.manipulation.release.v1`` fit the
``robot.gripper`` resource kind.  Homing, a width move and the safe-state stop
have no catalogue class for that kind, so they are extension ids.

This package is model-authored and unreviewed.  It has no hardware backend:
the upstream is a simulator and every served mode is ``simulated``.  The gate
runs the fake backend; nothing here ran on a real Franka Hand.  The pinned
commit is d893e17dc77a338a92a1673a8e616c8b251cc5a9.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: Upstream physics-hand tests call grasp with a 5 mm inner and outer band
#: (tests/test_gripper_physics.py:124).  The backend applies the band the
#: catalogue class documents around the requested width; this is a grasp
#: tolerance, not a device safety limit.
GRASP_EPSILON_INNER_M = 0.005
GRASP_EPSILON_OUTER_M = 0.005
#: The simulator ignores the commanded speed (docs/robot-state.md:201,
#: physics.py:189-190), so the driver sends the neutral value.
GRASP_SPEED_MPS = 0.0
MOVE_SPEED_MPS = 0.0
#: The simulator does not read force and applies no force limit
#: (docs/robot-state.md:203, :251-259); the signature still needs a number.
GRASP_FORCE_N = 0.0
#: One metre in millimetres, for the width_mm output of a capability action.
MM_PER_M = 1000.0


def _stroke_limit():
    """The Franka Hand stroke: 0 to 0.08 m, which is 0 to 80 mm (docs/robot-state.md:202)."""
    return Limit(min=0, max=80, unit="mm", source="vendor_doc", ref="docs/robot-state.md:202",
                 reason="the simulator reports max_width as 0.08 m, matching the real Franka Hand's 8 cm stroke")


class FrankaHand(Driver):
    device_id = "franka_hand"
    device_kind = "robot.gripper"
    mode = "simulated"
    risk = "R2"
    native = "franka_sim.gripper.physics:FrankaHandPhysics"
    backends = {"fake": ".fake:FakeFrankaHandPhysics"}
    vendor, model = "Franka", "Franka Hand (simulated)"
    display_name = "Franka Hand (libfranka-sim)"
    tags = ["franka", "gripper", "franka hand", "grasp", "manipulation", "simulation"]
    facts = [
        Fact("The simulator reports max_width as a constant 0.08 m, matching the real Franka Hand's 8 cm stroke",
             source="vendor_doc", ref="docs/robot-state.md:202"),
        Fact("A grasp succeeds only when the stall distance d satisfies width - epsilon_inner < d < width + epsilon_outer",
             source="vendor_doc", ref="docs/robot-state.md:203"),
        Fact("Neither gripper backend reads a real grip force, and the commanded force is not applied as a limit",
             source="vendor_doc", ref="docs/robot-state.md:203"),
        Fact("A grasp drives the fingers fully closed and saturates the physics servo at FINGER_FORCE_LIMIT (100 N) "
             "whatever force the client asked for; force limiting is not implemented",
             source="vendor_doc", ref="docs/robot-state.md:251-259"),
        Fact("stop() drives the fingers fully open and reuses the homing path; the real Franka Hand halts in place, "
             "so a client that stops mid-grasp sees the object released in the simulator",
             source="vendor_doc", ref="docs/robot-state.md:271-276"),
        Fact("The kinematic backend ignores the commanded speed entirely", source="vendor_doc",
             ref="docs/robot-state.md:201"),
        Fact("The physics move accepts speed for protocol compatibility but does not use it to pace the motion",
             source="upstream_code", ref="franka_sim/gripper/physics.py:159-160"),
        Fact("The physics grasp accepts speed and force for protocol compatibility but does not use them",
             source="upstream_code", ref="franka_sim/gripper/physics.py:189-190"),
        Fact("The reported temperature is a stub, constant 30 Cel", source="vendor_doc",
             ref="docs/robot-state.md:204"),
        Fact("The shipped scene contains no graspable body, so by default every grasp closes on nothing and answers false",
             source="vendor_doc", ref="docs/robot-state.md:209-211"),
        Fact("homing drives the fingers fully open, blocks until they settle, clears the grasp and stuck state and "
             "always reports success", source="upstream_code", ref="franka_sim/gripper/physics.py:145-154"),
        Fact("move validates the width, drives the fingers and blocks until they settle or the timeout elapses, then "
             "sets is_stuck if they did not settle", source="upstream_code",
             ref="franka_sim/gripper/physics.py:156-168"),
        Fact("get_state returns the summed width, maximum width, grasp flag and temperature from a lock-free snapshot",
             source="upstream_code", ref="franka_sim/gripper/physics.py:222-231"),
        Fact("A width outside 0..max_width raises ValueError, which the gripper server turns into kFail",
             source="upstream_code", ref="franka_sim/gripper/backend.py:37-38"),
        Fact("The upstream physics-hand tests call grasp with epsilon_inner 0.005 m and epsilon_outer 0.005 m",
             source="upstream_code", ref="tests/test_gripper_physics.py:124"),
        Fact("The gripper command methods block until the fingers settle or the settle timeout elapses",
             source="vendor_doc", ref="docs/robot-state.md:280-285"),
    ]
    safe_state = ("gripper motion stopped with the fingers driven fully open and the grasp and stuck flags cleared "
                  "(the simulator's stop()); this releases a held object because the simulator reopens instead of "
                  "halting in place")
    #: The served backend is the package fake, not the upstream physics engine.  Its commands are instantaneous and
    #: it has no scene, no object contact and no blocking settle, so it claims only F0.
    fidelity = {
        "engine": "in-memory fake of franka_sim.gripper.physics:FrankaHandPhysics",
        "fidelity_level": "F0",
        "determinism": {"kind": "exact", "seed_control": "none",
                        "notes": "the fake has no randomness; no seed is needed"},
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "no physics engine, no finger servo and no contact: width changes instantly and the epsilon band is "
            "applied to an in-memory stall width",
            "the upstream physics backend infers a grasp from the finger DOFs and blocks until they settle; the fake "
            "does neither",
            "commanded speed and force are accepted for signature compatibility and ignored, as the upstream "
            "documents for its own backends",
            "there is no arm, scene, object body or mobile base in the fake; only the Franka Hand is served",
        ],
    }

    # -- reads --------------------------------------------------------------------------------------------------
    @read("width_mm", unit="mm", native_unit="m", description="Summed distance between the two fingers")
    def get_width_mm(self):
        return float(self.native.get_state().width)

    @read("max_width_mm", unit="mm", native_unit="m", description="Maximum finger stroke of the hand")
    def get_max_width_mm(self):
        return float(self.native.get_state().max_width)

    @read("is_grasped", type="boolean", description="True when the last grasp found the object inside the epsilon band")
    def get_is_grasped(self):
        return bool(self.native.get_state().is_grasped)

    @read("is_stuck", type="boolean", description="True when the fingers did not settle within the last move timeout")
    def get_is_stuck(self):
        return bool(self.native.is_stuck)

    @read("temperature_c", unit="Cel", description="Reported hand temperature (a constant stub in the simulator)")
    def get_temperature_c(self):
        return self.native.get_state().temperature

    # -- catalogue capabilities -----------------------------------------------------------------------------------
    @action(cap="cap.manipulation.grasp.v1",
            description="Close the fingers on an object and report the achieved width; a miss completes with grasped false",
            input={"width": Field(unit="mm", native_unit="m",
                                  description="Target grasp width between the fingers",
                                  limit=_stroke_limit())})
    def grasp(self, width):
        grasped = self.native.grasp(width, GRASP_EPSILON_INNER_M, GRASP_EPSILON_OUTER_M, GRASP_SPEED_MPS,
                                    GRASP_FORCE_N)
        return {"grasped": bool(grasped), "width_mm": float(self.native.get_state().width) * MM_PER_M}

    @action(cap="cap.manipulation.release.v1",
            description="Open the fingers to a width and report the achieved width",
            input={"open_width": Field(unit="mm", native_unit="m",
                                       description="Target finger opening",
                                       limit=_stroke_limit())})
    def release(self, open_width):
        if not self.native.move(open_width, MOVE_SPEED_MPS):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the simulator refused to move the fingers")
        return {"released": True, "width_mm": float(self.native.get_state().width) * MM_PER_M}

    # -- extension capabilities (no catalogue class binds robot.gripper) ------------------------------------------
    @action(name="x-cap.barisyazici.hand_home.v1",
            description="Drive the fingers fully open and clear the grasp and stuck state",
            output={"homed": Field("boolean", description="True when homing completed"),
                    "width_mm": Field("number", unit="mm", description="Width after homing")})
    def hand_home(self):
        if not self.native.homing():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the simulator refused to home the hand")
        return {"homed": True, "width_mm": float(self.native.get_state().width) * MM_PER_M}

    @action(name="x-cap.barisyazici.hand_move.v1",
            description="Drive the fingers to a width and wait until they settle",
            input={"width": Field("number", unit="mm", native_unit="m",
                                  description="Target finger width",
                                  limit=_stroke_limit())},
            output={"moved": Field("boolean", description="True when the move completed"),
                    "width_mm": Field("number", unit="mm", description="Width after the move")})
    def hand_move(self, width):
        if not self.native.move(width, MOVE_SPEED_MPS):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the simulator refused to move the fingers")
        return {"moved": True, "width_mm": float(self.native.get_state().width) * MM_PER_M}

    @action(name="x-cap.barisyazici.hand_stop.v1", safe_state=True,
            description="Stop the hand by driving the fingers fully open, the simulator's safe state",
            output={"stopped": Field("boolean", description="True when the stop completed"),
                    "width_mm": Field("number", unit="mm", description="Width after the stop")})
    def hand_stop(self):
        if not self.native.stop():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the simulator refused to stop the hand")
        return {"stopped": True, "width_mm": float(self.native.get_state().width) * MM_PER_M}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="stop")
    def stop(self):
        """The native stop: the runtime latches first, then the fingers are driven fully open."""
        self.native.stop()
