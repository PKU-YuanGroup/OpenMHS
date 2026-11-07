"""OpenMHS driver for gh.luccachiang/gsworld: the Gymnasium environment RealFr3-v1 (a Gymnasium family driver).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action derived
from the environment's action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no machine e-stop path and no
operator-required limit.

The card's entry symbol ``gsworld.mani_skill.envs.tasks.real_fr3_env:RealFr3`` is a ManiSkill ``BaseEnv`` subclass
that registers the environment ``RealFr3-v1`` and builds an empty scene for showcasing a robot.  The deployment
selects the ``fr3_umi`` agent whose controller configurations are in the clone; the action space itself is assembled
by the external ManiSkill package and is not declared in the clone.  The fake therefore publishes a placeholder
action Box of eight normalised values, and its fidelity gaps say that the real action dimension and normalisation
must be checked on a machine with ManiSkill installed.

The gate cannot install or import the upstream stack (ManiSkill 3.0.0b15, SAPIEN, PhysX and torch), so the ``fake``
backend is this package's pure-Python kinematic stand-in (fake.py).  A backend name that ``backends`` does not list
(``sim``) would be served by ``gymnasium.make(env_id, **env_kwargs)`` (``GymnasiumDriver.open_native``); that path was
not run here and is not claimed.

Every constant and rule cites a line of the clone at the pinned commit 532950475cc80a97c7050fd94858a1a8841dbf2c.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

REAL_FR3 = "gsworld/mani_skill/envs/tasks/real_fr3_env.py"
FR3_UMI = "gsworld/mani_skill/agents/robots/panda/fr3_umi.py"
CONSTANTS = "gsworld/constants.py"
WRAPPER = "gsworld/mani_skill/utils/wrappers/gs_world_wrapper.py"
MOTION_EXAMPLE = "gsworld/mani_skill/examples/motionplanning/franka/run_with_gs.py"


class RealFr3(GymnasiumDriver):
    device_id = "gsworld-real-fr3"
    env_id = "RealFr3-v1"
    #: Deployment choice: the Franka FR3 UMI agent and its delta joint controller (facts.md).  The external ManiSkill
    #: package assembles the actual action space from these configurations; the fake's value is a stand-in.
    env_kwargs = {
        "robot_uids": "fr3_umi",
        "control_mode": "pd_joint_delta_pos",
        "sim_config": {"sim_freq": 100, "control_freq": 20},
    }
    native = "gsworld.mani_skill.envs.tasks.real_fr3_env:RealFr3"
    backends = {"fake": ".fake:FakeRealFr3"}
    display_name = "GSWorld RealFr3-v1 (empty scene, FR3 UMI)"
    vendor, model = "luccachiang", "GSWorld RealFr3-v1"
    tags = ["gsworld", "mani-skill", "sapien", "fr3", "fr3-umi", "robot-arm", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("RealFr3-v1 is registered with max_episode_steps=200000", source="upstream_code",
             ref=f"{REAL_FR3}:22"),
        Fact("RealFr3 subclasses BaseEnv and is described as a dummy environment for showcasing robots in an empty "
             "scene", source="upstream_code", ref=f"{REAL_FR3}:23-27"),
        Fact("RealFr3 supports the reward modes none, dense and sparse, in that order", source="upstream_code",
             ref=f"{REAL_FR3}:24"),
        Fact("The RealFr3 constructor's default robot_uids is panda and it passes robot_uids to BaseEnv",
             source="upstream_code", ref=f"{REAL_FR3}:29-30"),
        Fact("Fr3Umi is registered as the agent uid fr3_umi", source="upstream_code", ref=f"{FR3_UMI}:15-17"),
        Fact("Fr3Umi names seven FR3 arm joints and two FR3 finger joints", source="upstream_code",
             ref=f"{FR3_UMI}:41-53"),
        Fact("The Fr3Umi arm pd_joint_delta_pos controller bounds every arm joint delta to -0.1 to 0.1 and applies it "
             "as a delta", source="upstream_code", ref=f"{FR3_UMI}:78-86"),
        Fact("The Fr3Umi gripper position controller bounds the gripper command to -0.01 to 0.04",
             source="upstream_code", ref=f"{FR3_UMI}:114-121"),
        Fact("The Fr3Umi controller map binds pd_joint_delta_pos to the arm delta controller and the gripper position "
             "controller", source="upstream_code", ref=f"{FR3_UMI}:123-126"),
        Fact("fr3_umi_task_init_qpos is a nine-value FR3 UMI start configuration", source="upstream_code",
             ref=f"{CONSTANTS}:63-73"),
        Fact("RealFr3._load_scene builds a ground and sets collision group bit 30", source="upstream_code",
             ref=f"{REAL_FR3}:112-114"),
        Fact("RealFr3._initialize_episode does nothing (pass)", source="upstream_code", ref=f"{REAL_FR3}:116-117"),
        Fact("RealFr3.evaluate returns an empty dict and _get_obs_extra returns an empty dict, so the task adds no "
             "reward term and no extra observation", source="upstream_code", ref=f"{REAL_FR3}:119-123"),
        Fact("RealFr3 configures wrist_cam and right_cam at 640x480 with near 0.01 and far 100",
             source="upstream_code", ref=f"{REAL_FR3}:47-50"),
        Fact("RealFr3 configures a 640x480 render camera with near 0.01 and far 100", source="upstream_code",
             ref=f"{REAL_FR3}:65-67"),
        Fact("The GSWorld wrapper configures sim_freq=100 and control_freq=20 for its moving-robot environment",
             source="upstream_code", ref=f"{WRAPPER}:89"),
        Fact("The Franka motion-planning example defaults to sim_freq 100 and control_freq 20", source="upstream_code",
             ref=f"{MOTION_EXAMPLE}:60-61"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch; the last world state stays readable")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic, so F0; the 50 ms
    #: control step is the configured 20 Hz control period (sim_freq 100, control_freq 20).
    fidelity = {
        "engine": "gymnasium:RealFr3-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial joint noise and its dynamics are "
                     "deterministic, so this package repeats a trajectory for one seed; upstream draws from "
                     "torch/numpy generators, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics, contacts, friction, actuators or constraints: the fake integrates the arm "
            "joint deltas directly and sets the gripper target kinematically (F0)",
            "the real action space is assembled by the external ManiSkill package from the Fr3Umi controller "
            "configurations; the clone states the physical delta bounds (-0.1 to 0.1 for the arm and -0.01 to 0.04 "
            "for the gripper) but not the normalisation or the exact action dimension, so the fake's Box(-1, 1) "
            "with eight values is a placeholder, not a verified upstream action space",
            "the real state observation is the agent qpos and qvel plus any controller state assembled by the "
            "external ManiSkill BaseAgent; the fake returns the 18-value qpos/qvel part only, so a controller "
            "state field is not covered",
            "the two 640x480 wrist and right cameras and the render camera are not modelled: the gymnasium bridge "
            "serves the scalar world state only, and the fake returns no rgb, depth or segmentation array",
            "the fake starts from fr3_umi_task_init_qpos plus placeholder noise; the real agent's reset state and "
            "keyframe selection are performed by the external ManiSkill BaseAgent and are not reproduced",
            "reset options are accepted and ignored by the fake; the upstream environment consumes them (for "
            "example reconfigure), which is not modelled",
            "the fake draws its reset noise with Python's random.Random while upstream uses torch/numpy "
            "generators, so one seed does not reproduce an upstream trajectory",
            "no wall-clock pacing: realtime_factor 0 and ticks advance simulated time by the configured 50 ms "
            "control step only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
        ],
    }
