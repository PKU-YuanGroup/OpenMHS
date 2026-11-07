"""OpenMHS driver for gh.botianhao/humanoid_control: the humanoid MJCF served through MujocoDriver.

The card classified this repository as a ROS family and named ``RosDriver``.  Recon found no ROS service or action
for stepping, resetting or stopping the world: the only ROS 2 surface of the simulator is a set of Float32MultiArray
target subscriptions and joint/odometry/IMU publications in ``humanoid_mujoco_sim``.  The actual environment is a
MuJoCo model, the card's ``models[0]``, stepped by ``mj.mj_step`` inside that node.  This package therefore serves the
pinned model through ``MujocoDriver`` (cap.world.step.v1 and cap.world.reset.v1) and records DEVIATION FROM THE CARD
in RESULT.json; a ROS transport driver cannot express the world step or reset that the card's hints request.

The driver is configuration only.  The model file is read from the read-only upstream clone at the pinned commit; it
is never copied into this package and never imported.  MuJoCo is not installed where the gate runs, so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  A backend name that ``backends`` does
not list would import the real ``mujoco`` module and load the same file; that path is not run here.

Every Fact cites a line of the clone at commit cfb27eb205d6ee21a801abe273ffc0a53d3be0f2.  This package is
model-authored and unreviewed: ``driver.lock.json`` keeps ``reviewed_by`` null, and no hardware or real MuJoCo run is
claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "humanoid_legged_description/mjcf/humanoid_legged_control_.xml"
SIM = "humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py"
BASE = "humanoid_mujoco_sim/humanoid_mujoco_sim/mujoco_base.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/.
MODEL_PATH = "../../../../robots/botianhao/humanoid_control/" + MODEL


#: Gaps of every backend of this package against the upstream simulator.
_SHARED_GAPS = [
    "the upstream HumanoidSim overrides the model start state (qpos 0 0 0.82, a scipy quaternion and twelve init joint "
    "angles) and computes data.ctrl from targetTorque/targetPos/targetVel with its own Kp/Kd vectors; this driver "
    "calls mj_resetData, which restores the model defaults and does not apply the home keyframe, and takes the "
    "control vector from the caller",
    "the upstream loop is wall-clock paced (about 1/60 s of simulated time per outer iteration, engine steps at "
    "1/1000 s) and needs a GLFW window; this driver is lockstep with no wall-clock pacing and no GUI",
    "the ROS 2 target and state topics, the /pauseFlag publication and the controller nodes are not used: the "
    "driver serves only the MuJoCo world step and reset, and no ROS graph was contacted",
    "no physical humanoid is modelled and nothing was validated against the humanoid hardware",
]
#: Gaps of the fake backend only (the package's stand-in for the mujoco library).
_FAKE_GAPS = [
    "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the free base, the "
    "twelve hinge joints, the twelve motor actuators, their explicit ctrlranges and the 0.001 s option step, then "
    "gives each actuated hinge a placeholder velocity proportional to its control value and holds the free base "
    "where the model puts it; it computes no inertia, torque, gravity, contact, friction, constraint, damping or "
    "actuator dynamics and produces no MuJoCo trajectory",
    "the stand-in loads no STL mesh or texture and resolves no collision or contact; the floor, obstacle boxes, "
    "joint ranges and armature attributes of the model are not applied",
]


class HumanoidControl(MujocoDriver):
    device_id = "humanoid_control"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    display_name = "Botianhao humanoid MuJoCo model"
    vendor, model = "botianhao", "humanoid-legged-description"
    tags = ["botianhao", "humanoid", "legged", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The MJCF root element declares the model humanoid-legged-description and uses radians.",
             source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The model option sets timestep 0.001 s, 50 iterations, the PGS solver, gravity 0 0 -9.81 and "
             "noslip_iterations 20.", source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The base_link body carries a freejoint.",
             source="upstream_code", ref=f"{MODEL}:70-71"),
        Fact("The left leg is a chain of six hinge joints from leg_l1_joint to leg_l6_joint, and the right leg is a "
             "chain of six hinge joints from leg_r1_joint to leg_r6_joint; each joint declares its own range and "
             "actuatorfrcrange.", source="upstream_code", ref=f"{MODEL}:103-164"),
        Fact("The actuator section declares twelve motor actuators, one per leg hinge, each with ctrllimited true and "
             "a ctrlrange of -150 to 150, -200 to 200 or -90 to 90 depending on the joint.",
             source="upstream_code", ref=f"{MODEL}:179-192"),
        Fact("The model provides a keyframe named home whose qpos is 0 0 1.5, the identity quaternion and twelve "
             "zero joint angles.", source="upstream_code", ref=f"{MODEL}:233-239"),
        Fact("mujoco_base.MuJoCoBase.__init__ loads the XML path with mujoco.MjModel.from_xml_path and creates an "
             "MjData.", source="upstream_code", ref=f"{BASE}:6-19"),
        Fact("The module function main of humanoid_sim initialises rclpy, resolves the installed "
             "humanoid_legged_description share path to mjcf/humanoid_legged_control_.xml and constructs "
             "HumanoidSim with it.", source="upstream_code", ref=f"{SIM}:279-286"),
        Fact("init_base_pos is 0 0 0.82 and init_joint_pos is twelve joint values, both defined at module scope.",
             source="upstream_code", ref=f"{SIM}:17-18"),
        Fact("After super().__init__ loads the model, HumanoidSim.__init__ sets qpos[:3] to init_base_pos, qpos[3:7] "
             "to a scipy quaternion of init_base_eular_zyx and the last twelve qpos values to init_joint_pos.",
             source="upstream_code", ref=f"{SIM}:22-60"),
        Fact("HumanoidSim computes data.ctrl as targetTorque plus Kp and Kd errors against targetPos, targetVel and "
             "the last twelve qpos/qvel values, then calls mj.mj_step.", source="upstream_code", ref=f"{SIM}:127-131"),
        Fact("HumanoidSim's node publishes /jointsPosVel, /ground_truth/state, /imu, /realTorque and /pauseFlag and "
             "subscribes to /targetTorque, /targetPos, /targetVel, /targetKp and /targetKd.",
             source="upstream_code", ref=f"{SIM}:45-55"),
        Fact("HumanoidSim sets simend to 1000.0 s and sim_rate to 1000.0 Hz.", source="upstream_code",
             ref=f"{SIM}:28-29"),
        Fact("The simulation loop runs until the GLFW window close flag; each outer pass runs inner iterations while "
             "no more than 1/60 s of simulated time has passed since the pass began and the pause flag is clear, "
             "and calls mj_step only when the wall clock has advanced by 1 / sim_rate.",
             source="upstream_code", ref=f"{SIM}:118-132"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The real MuJoCo engine contract, for the implicit backend that imports mujoco.  The gate exercises the
    #: package's stand-in module, whose F0 contract is selected by ``fidelity_by_backend`` below (model review,
    #: 2026-11-04: the fake was published with this F1 contract before).
    fidelity = {
        "engine": "mujoco:humanoid_legged_control_",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The bridge accepts a seed in cap.world.reset.v1 but a MuJoCo reset restores the model defaults "
                     "and does not use it; no RNG or exact-continuation claim is made.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": _SHARED_GAPS + [
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
        ],
    }
    #: The fake backend is the package's stand-in mujoco module, not MuJoCo and not a recording: F0, no physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in is deterministic but its placeholder motion is not the engine's physics; a reset "
                         "seed is accepted and unused.",
            },
            "timestep_ms": 1.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": _FAKE_GAPS + _SHARED_GAPS,
        },
    }
