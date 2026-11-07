"""OpenMHS MuJoCo world driver for the pocketxjl humanoid-control model.

The card's static scan selected the ROS family because the repository contains
ROS 1 controller packages, but the repository's own runtime is a MuJoCo
simulation: ``mujoco_sim/script/humanoid_sim.py`` imports MuJoCo, sets
``data.ctrl`` from ROS joint targets, calls ``mj_step`` and publishes joint
state, IMU and odometry.  The only model named by the card is the MJCF at
``humanoid-legged-description/mjcf/humanoid_legged.xml``; the card's role is
``sim-env`` and its candidate classes are ``cap.world.step/reset/seed.v1``.
The primary interface for that model is therefore world stepping, not a
rosbridge transport, so this package is a configuration-only ``MujocoDriver``
over the MJCF.  The switch from the card's ``RosDriver`` helper is recorded as
a DEVIATION FROM THE CARD in ``RESULT.json``.

The bridge serves the model's twelve motor actuators as ``cap.world.step.v1``
``{ticks, action: {ctrl: [12]}}``; each ctrl element is checked against the
model's ``actuator_ctrlrange`` before ``data.ctrl`` is written.  The state is
the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``,
``tick``, ``timestep_ms``, ``seed``).  ``cap.world.reset.v1`` calls
``mj_resetData`` + ``mj_forward``.

This package does not run the OCS2 gait/NMPC controller, the state estimator,
the ROS 1 nodes or the MuJoCo viewer.  Those are separate upstream components
and are listed as fidelity gaps; the driver supplies the low-level model world
that the upstream simulator itself steps.  The package is simulated (R0): it
has no hardware backend and no route to a physical humanoid.  It is
model-authored and unreviewed; only the package's stand-in MuJoCo module is
exercised by the fake gate.

Every Fact cites the pinned clone at
``3b5ffec98d29827730194b0dbf2f119fb7b265ca``.  No number in this package is a
device bound: the control envelope is derived at run time from the MJCF's own
``actuator_ctrlrange``.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory.  The clone is read
#: in place and is never copied into the package or imported.
MODEL = "humanoid-legged-description/mjcf/humanoid_legged.xml"
MODEL_PATH = "../../../../robots/pocketxjl/humanoid-control/" + MODEL

_PACKAGE_GAPS = [
    "the package does not run the upstream OCS2 gait/NMPC controller, WBC, state estimator, "
    "gait command publisher or ROS 1 nodes; it serves only the low-level model world",
    "the upstream simulator sets a non-default start pose (base z 1.225 and init_joint_pos); "
    "the bridge reset restores the MJCF defaults instead, and the model has no keyframe",
    "the model's arms, head and waist are visual meshes on the base body with no joints or "
    "actuators; only the twelve leg motor channels are controllable",
    "no viewer, camera, image, ROS graph or rosbridge endpoint is exposed; the package is not "
    "a substitute for the upstream ROS controller stack",
    "no physical humanoid is modelled or controlled; there is no hardware backend and no "
    "hardware run was performed",
]
_FAKE_GAPS = [
    "the fake backend is an analytic stand-in for the mujoco module, not a recording and not "
    "MuJoCo: it reads the same MJCF for the actuator count, ctrlrange and joint dimensions, but "
    "its step is a placeholder first-order motion of each leg joint toward its control value",
    "the fake loads no mesh, texture, material or inertia and resolves no contact, friction, "
    "tendon, equality or sensor quantity; the real MuJoCo step is not represented",
    "the fake's qpos/qvel integration and its initial free-joint quaternion are placeholder "
    "test data; no trajectory was compared with the real engine or the upstream simulator",
    "the bridge reset does not reproduce the upstream simulator's manual initial pose, and no "
    "seed controls MuJoCo's internal state or any random number generator",
] + _PACKAGE_GAPS
_REAL_GAPS = [
    "the official MuJoCo engine was not run where this package was checked, so its step, contact "
    "and actuator behaviour are not validated by this package's fake evidence",
] + _PACKAGE_GAPS


class HumanoidWorld(MujocoDriver):
    device_id = "pocketxjl-humanoid"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "pocketxjl humanoid legged MuJoCo model"
    vendor, model = "pocketxjl", "humanoid_legged_description"
    tags = ["ros", "ros1", "mujoco", "simulation", "humanoid", "biped", "world"]
    facts = [
        Fact("The README installs MuJoCo with pip3 and starts the simulation with roslaunch "
             "humanoid_controllers load_cheat_controller.launch.",
             source="vendor_doc", ref="README.md:36-53"),
        Fact("The README says the OCS2 controller is a separate monorepo build and must be compiled "
             "with catkin before the simulation is started.",
             source="vendor_doc", ref="README.md:7-28"),
        Fact("The MJCF names the model humanoid_legged_description.", source="upstream_code",
             ref=f"{MODEL}:1"),
        Fact("The model sets timestep 0.001 seconds, the PGS solver, gravity 0 0 -9.81 and twenty "
             "noslip iterations.", source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The base_link body carries a free joint, so the model has a floating base.",
             source="upstream_code", ref=f"{MODEL}:57-58"),
        Fact("The leg hinge joints have limited ranges: leg_l1 -0.2 to 1.5708 and leg_r1 -1.5708 to "
             "0.2; leg_l2, leg_l3, leg_r2 and leg_r3 -1.5708 to 1.5708; leg_l4 and leg_r4 0 to 2.356; "
             "leg_l5 and leg_r5 -0.8 to 0.8; and leg_l6 and leg_r6 -0.5236 to 0.5236.",
             source="upstream_code", ref=f"{MODEL}:85-144"),
        Fact("The actuator block declares twelve motor actuators with gear 1 and explicit ctrlrange "
             "bounds: +/-150 for leg_l1, leg_l2, leg_r1 and leg_r2; +/-200 for leg_l3, leg_l4, "
             "leg_r3 and leg_r4; and +/-90 for leg_l5, leg_l6, leg_r5 and leg_r6.",
             source="upstream_code", ref=f"{MODEL}:156-167"),
        Fact("The upstream MuJoCo loop computes data.ctrl from targetTorque, targetKp, targetPos, "
             "targetKd, targetVel and the last twelve qpos/qvel entries, then calls mj_step.",
             source="upstream_code", ref="mujoco_sim/script/humanoid_sim.py:110-112"),
        Fact("The upstream simulator sets sim_rate to 1000 and only steps when the wall-clock epoch "
             "has reached 1/sim_rate.",
             source="upstream_code", ref="mujoco_sim/script/humanoid_sim.py:23-113"),
        Fact("The upstream simulator publishes /jointsPosVel at 500 Hz from the last twelve qpos and "
             "qvel entries.", source="upstream_code", ref="mujoco_sim/script/humanoid_sim.py:116-124"),
        Fact("The upstream simulator initializes the base at [0, 0, 1.225] and the leg joints at the "
             "init_joint_pos values, then writes them into data.qpos.",
             source="upstream_code", ref="mujoco_sim/script/humanoid_sim.py:14-53"),
        Fact("The humanoid controller subscribes to /jointsPosVel and /imu and advertises /targetTorque, "
             "/targetPos, /targetVel, /targetKp and /targetKd.",
             source="upstream_code", ref="humanoid_controllers/src/humanoidController.cpp:63-69"),
        Fact("The cheat controller node subscribes to pauseFlag and calls controller.update at 500 Hz "
             "unless the flag is set.", source="upstream_code",
             ref="humanoid_controllers/src/CheatControllerNode.cpp:25-69"),
        Fact("MuJoCoBase publishes /pauseFlag, toggles pause_flag on SPACE and resets the data with "
             "mj_resetData on BACKSPACE.", source="upstream_code",
             ref="mujoco_sim/script/mujoco_base.py:15-51"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted "
                  "until mhs.safety.reset clears the latch, and the model state stays readable")
    #: The real MuJoCo engine contract, used by the implicit ``sim`` backend.
    #: The gate exercises the package's stand-in module, whose F0 contract is
    #: selected by ``fidelity_by_backend`` below.
    fidelity = {
        "engine": "mujoco:humanoid_legged_description",
        "fidelity_level": "F1",
        "determinism": {"kind": "none", "seed_control": "none"},
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": _REAL_GAPS,
    }
    #: The fake backend is not MuJoCo and is not a recording: F0, no physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {"kind": "none", "seed_control": "none"},
            "timestep_ms": 1.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": _FAKE_GAPS,
        },
    }
