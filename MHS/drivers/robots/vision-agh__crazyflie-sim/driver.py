"""OpenMHS driver for gh.vision-agh/crazyflie-sim: the ROS 2 Gazebo world step/pause utility.

The pinned clone is an educational CrazyFlie simulation workspace.  Its ROS 2 package
``evs_gz_utils`` contains two utilities: a Gazebo pose-to-Odometry node and a world-stepping example.  This
package serves the environment-step interface of the second utility: one ``ControlWorld`` call on the service
the upstream node builds from its ``world_name`` parameter, plus the pause request the constructor uses to put
the world in stepping mode.

The card names ``RosDriver``, but that helper requires a fixed endpoint literal in the cited source.  The
upstream node builds ``/world/<world_name>/control`` and ``/evs/<model_name>/state`` at run time from ROS
parameters (``gz_step_example.py:26`` and ``model_state_gazebo.py:43``), so there is no resolved endpoint literal
for G7 to cite.  This package therefore uses a direct ``Driver`` over the pinned Python class
``GzStepExample`` and records the deviation in RESULT.json.  The fake is an analytic stand-in, not a recording;
it opens no ROS graph and no Gazebo world.  No live ROS or hardware run exists for this package.

The pause path is the upstream constructor's: ``step_simulation(steps=0)`` under the comment "Ensure the
simulation is paused" (``gz_step_example.py:32-34``), and ``step_simulation`` always sets
``world_control.pause = True`` (line 39).  It is not acknowledged: ``step_simulation`` spins without a timeout
(line 45), logs and returns None whether or not the ControlWorld call was answered, and never reads the
response's ``success`` field (lines 46-49).  Since the model review of 2026-11-05 the e-stop still sends that
pause request but reports ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held, and the pause action no
longer claims a safe state (the author's fake raised on a failed call, which the upstream method never does).
External ROS controllers and CrazyFlie cflib clients are not stopped by a pause either; the README states that
no ROS is needed to control the CrazyFlie inside CrazySim (line 76).

The ``evs_gz_utils`` directory is a git submodule.  The pinned parent commit records it as a gitlink at
``b8893f58d1eb62b9ca43e63c413264dbd01ca0dd``; the source files are not in the parent commit's tree.  Since the
SDK's submodule reading (MHS/changes/SUBMODULES-AND-FACTORY-ENVIRONMENTS.md, 2026-11-05), gates G4 and G7 read
them at that gitlink commit from the submodule's own object store (.git/modules/evs_gz_utils), and only while the
submodule's checkout is at that commit.  The package stays blocked on its stop alone (G6).
"""

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop, read

STEP_NODE = "evs_gz_utils/evs_gz_utils/gz_step_example.py"
STEP_LAUNCH = "evs_gz_utils/launch/gz_step.launch.py"
STATE_NODE = "evs_gz_utils/evs_gz_utils/model_state_gazebo.py"
STATE_LAUNCH = "evs_gz_utils/launch/model_state.launch.py"

STEP_CAP = "cap.world.step.v1"
PAUSE_CAP = "x-cap.vision-agh.pause.v1"


class CrazyflieSimWorld(Driver):
    """Direct driver for the pinned ``GzStepExample`` ControlWorld step/pause interface."""

    device_id = "crazyflie-sim-world"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "evs_gz_utils.gz_step_example:GzStepExample"
    backends = {"fake": ".fake:FakeGzStep"}
    vendor = "vision-agh"
    model = "evs_gz_utils Gazebo ControlWorld step utility"
    display_name = "CrazyFlie simulation Gazebo world step/pause (evs_gz_utils)"
    tags = ["ros2", "gazebo", "simulation", "crazyflie", "world", "step", "pause", "evs-gz-utils"]
    facts = [
        Fact("The parent repository declares evs_gz_utils as a git submodule at path evs_gz_utils.",
             source="upstream_code", ref=".gitmodules:1-3"),
        Fact("GzStepExample imports the ControlWorld service type from ros_gz_interfaces.srv.",
             source="upstream_code", ref=f"{STEP_NODE}:8"),
        Fact("GzStepExample declares a world_name ROS parameter and reads its string value from the parameter "
             "server.", source="upstream_code", ref=f"{STEP_NODE}:19-23"),
        Fact("GzStepExample builds the service name as /world/<world_name>/control and creates a ControlWorld "
             "client for it.", source="upstream_code", ref=f"{STEP_NODE}:26-27"),
        Fact("The stepping launch file bridges the parameterized world control service with type "
             "ros_gz_interfaces/srv/ControlWorld.", source="upstream_code", ref=f"{STEP_LAUNCH}:28-37"),
        Fact("step_simulation sets world_control.pause to True on every request; it sets world_control.step "
             "to True for one step and world_control.multi_step to the requested count otherwise.",
             source="upstream_code", ref=f"{STEP_NODE}:36-44"),
        Fact("The constructor calls step_simulation with steps set to zero under the comment 'Ensure the "
             "simulation is paused'.", source="upstream_code", ref=f"{STEP_NODE}:32-34"),
        Fact("The service call spins without a timeout until the future completes and logs success when a result "
             "exists; it logs an error when the result is None, does not inspect any response field and returns "
             "None in both cases.",
             source="upstream_code", ref=f"{STEP_NODE}:44-49"),
        Fact("The model_state node creates an Odometry publisher on /evs/<model_name>/state and subscribes "
             "through a Gazebo node to /world/<world_name>/pose/info.", source="upstream_code",
             ref=f"{STATE_NODE}:41-51"),
        Fact("The model_state node writes the Gazebo position and orientation into the Odometry pose and derives "
             "linear and angular velocity from consecutive samples.", source="upstream_code",
             ref=f"{STATE_NODE}:55-117"),
        Fact("The model_state launch file bridges /clock as rosgraph_msgs/msg/Clock and sets use_sim_time.",
             source="upstream_code", ref=f"{STATE_LAUNCH}:16-24"),
        Fact("The README identifies CrazySim 1.2x at commit 8ad9bb8 as the external simulation component.",
             source="vendor_doc", ref="README.md:7"),
        Fact("The README states that no ROS is needed to control the CrazyFlie inside CrazySim.",
             source="vendor_doc", ref="README.md:76"),
    ]
    safe_state = (
        "No acknowledged safe state: the e-stop sends the constructor's ControlWorld pause request through "
        "step_simulation, which returns None whether or not the call was answered and never reads "
        "response.success, then reports SAFE_STATE_UNREACHED with the latch held; a pause that reaches Gazebo "
        "leaves the world paused until something resumes it, unconfirmed, and external ROS controllers and cflib "
        "clients are not stopped."
    )
    #: The deployed fake is an analytic stand-in.  The clone's external simulator is not part of this package and
    #: was not run; the clone states no world timestep, so a step unit has no source-backed millisecond value.
    fidelity = {
        "engine": "ros2:evs_gz_utils/gz_step_example + Gazebo ControlWorld service (analytic fake)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the fake records the requested step count deterministically, but the deployed Gazebo "
                     "world, its physics and its RNG are external and the clone states no seed or state-hash "
                     "contract; no replay claim is made",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic stand-in, not a recording: it does not replay captured ROS traffic and it "
            "opens no ROS graph, Gazebo world, ros_gz bridge or rclpy node",
            "the upstream simulator is CrazySim/Gazebo, external to this clone (README.md:7); the clone contains "
            "only the ROS utility nodes, and no upstream simulator run was made",
            "the clone states no Gazebo world max_step_size, so one ControlWorld step unit is not converted to "
            "simulated milliseconds; timestep_ms is 0 and ticks are service step units",
            "the pinned example does not inspect the ControlWorld response and returns None for an answered and "
            "an unanswered call alike; a completed step is not proof that the world advanced, and the fake only "
            "sets local request flags",
            "the pause request is not acknowledged, so the e-stop reports SAFE_STATE_UNREACHED with the latch "
            "held; a pause that reaches Gazebo stops the world from stepping but not external ROS controllers, "
            "queued callbacks or CrazyFlie cflib clients, and it is not a sensed quiescence read-back",
            "constructing GzStepExample needs a prior global rclpy.init(), waits without a timeout until "
            "/world/<world_name>/control appears (gz_step_example.py:28-29) and logs through the ROS logger; every "
            "step_simulation call spins without a timeout",
            "the model_state Odometry observation on /evs/<model_name>/state is not served by this package; only "
            "the ControlWorld step and pause calls are bound",
            "the cflib UDP control path in connection_example.py is not served; the README says no ROS is needed "
            "to control the CrazyFlie inside CrazySim (README.md:76)",
            "only the fake backend is declared: the live path needs rclpy, ros_gz_interfaces and a running Gazebo "
            "world with the bridged service, none of which is installed or attached here",
        ],
    }

    # ------------------------------------------------------------------ state
    def setup(self) -> None:
        """Start the local step counter."""
        self._tick = 0

    def _tick_value(self) -> int:
        return int(getattr(self, "_tick", 0))

    @read("tick", type="integer", unit="1",
          description="ControlWorld step units requested since this backend was created")
    def get_tick(self) -> int:
        return self._tick_value()

    # ---------------------------------------------------------------- actions
    @action(cap=STEP_CAP,
            description="Advance the Gazebo world by ControlWorld step requests",
            input={"ticks": Field("integer", unit="1",
                                  description="ControlWorld step units to advance; the upstream example sets "
                                              "world_control.step for one and world_control.multi_step "
                                              "otherwise")})
    def step(self, ticks: int = 1) -> dict:
        self.check_cancelled()
        self.native.step_simulation(int(ticks))
        self.check_cancelled()
        self._tick = self._tick_value() + int(ticks)
        observation = {"stepped": int(ticks), "pause_requested": True}
        return {
            "observation": observation,
            "tick": self._tick,
            "state_hash": canonical.digest({"observation": observation, "tick": self._tick}),
        }

    @action(name=PAUSE_CAP,
            description="Request a pause of the simulated Gazebo world with the pinned step_simulation zero-step "
                        "path; the method reports no result, so the receipt does not show that the world paused",
            output={"pause_requested": Field("boolean",
                                             description="True after step_simulation(0) returned; it returns None "
                                                         "whether or not the ControlWorld call was answered")})
    def pause(self) -> dict:
        self.native.step_simulation(0)
        return {"pause_requested": True}

    # ------------------------------------------------------------------ stop
    @estop(native="step_simulation")
    def stop(self) -> None:
        """Send the constructor's zero-step pause request, then refuse to certify it.

        step_simulation returns None whether or not the ControlWorld call was answered and never reads the
        response's success field (gz_step_example.py:44-49), so nothing acknowledges the pause: the e-stop reports
        SAFE_STATE_UNREACHED and the latch stays held (model review, 2026-11-05).
        """
        self.native.step_simulation(0)
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the ControlWorld pause request was sent through step_simulation, which reports no result and never "
            "reads the response's success field; the pause is not acknowledged",
        )
