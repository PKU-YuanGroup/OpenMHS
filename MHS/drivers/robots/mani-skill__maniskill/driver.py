"""OpenMHS driver for gh.mani-skill/maniskill: the TriFingerRotateCubeLevel0-v1 environment.

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives
``cap.world.step.v1`` (``{ticks, action}`` with an action derived from the environment's action space),
``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from it.  The task card's entry
symbol ``mani_skill.envs.tasks.rotate_cube:RotateCubeEnvLevel0`` is the upstream class; the default controller is
``pd_joint_delta_pos`` (the first controller config), whose nine joint deltas are normalised to the action space
[-1, 1].

The device is simulated (R0): there is no hardware backend, no machine e-stop path and no operator-required limit.
The gate cannot install or import the upstream package (it needs SAPIEN, PhysX, torch and a GPU-capable stack), so the
``fake`` backend is this package's pure-Python kinematic stand-in (fake.py).  A backend name that ``backends`` does not
list (``sim``) would be served by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs the
upstream package and was not run here (facts.md).

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  The fake is
kinematic, so it declares F0 and says in its gaps that it has no rigid-body dynamics, contacts or actuators and that it
was never run against the upstream SAPIEN simulation.  Every fact cites a line of the clone at the pinned commit
62ff3a5896b4d5b4cf0ac4c8d79afe600c9404a3.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ROTATE_CUBE = "mani_skill/envs/tasks/rotate_cube.py"
TRIFINGER = "mani_skill/agents/robots/trifingerpro/trifingerpro.py"
PD_JOINT_POS = "mani_skill/agents/controllers/pd_joint_pos.py"
BASE_AGENT = "mani_skill/agents/base_agent.py"
GYM_UTILS = "mani_skill/utils/gym_utils.py"
SAPIEN_ENV = "mani_skill/envs/sapien_env.py"
SIM_TYPES = "mani_skill/utils/structs/types.py"


class TriFingerRotateCube(GymnasiumDriver):
    device_id = "trifinger-rotate-cube"
    env_id = "TriFingerRotateCubeLevel0-v1"
    native = "mani_skill.envs.tasks.rotate_cube:RotateCubeEnvLevel0"
    backends = {"fake": ".fake:FakeRotateCubeEnv"}
    action_space_ref = f"{GYM_UTILS}:110-112"
    display_name = "ManiSkill TriFingerRotateCubeLevel0-v1 (simulated)"
    vendor, model = "ManiSkill", "TriFingerRotateCubeLevel0-v1"
    tags = ["mani-skill", "trifinger", "rotate-cube", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("TriFingerRotateCubeLevel0-v1 is registered with max_episode_steps=250", source="upstream_code",
             ref=f"{ROTATE_CUBE}:351"),
        Fact("The task's default robot is \"trifingerpro\"", source="upstream_code", ref=f"{ROTATE_CUBE}:57"),
        Fact("TriFingerPro's active joint list names the nine finger joints: base-to-upper, upper-to-middle and "
             "middle-to-lower for each of the 0, 120 and 240 degree fingers", source="upstream_code",
             ref=f"{TRIFINGER}:42-56"),
        Fact("The controller configs list pd_joint_delta_pos first", source="upstream_code",
             ref=f"{TRIFINGER}:144-145"),
        Fact("A control_mode of None selects the first supported control mode", source="upstream_code",
             ref=f"{BASE_AGENT}:106-109"),
        Fact("The pd_joint_delta_pos controller bounds each joint delta to -0.1 to 0.1 and applies it as a delta",
             source="upstream_code", ref=f"{TRIFINGER}:103-110"),
        Fact("PDJointPosControllerConfig normalises the action space by default", source="upstream_code",
             ref=f"{PD_JOINT_POS}:131"),
        Fact("A normalised action space is Box(-1, 1) with the shape of the controller's joint action space",
             source="upstream_code", ref=f"{GYM_UTILS}:110-112"),
        Fact("The environment's action space is the agent controller's action space and the single action space is "
             "its unbatched form", source="upstream_code", ref=f"{BASE_AGENT}:298-320"),
        Fact("The task's size parameter is 0.065 m and its goal_radius is 0.02 m", source="upstream_code",
             ref=f"{ROTATE_CUBE}:39-44"),
        Fact("Success requires the object-to-goal position distance below 0.02 m and the quaternion difference below "
             "0.1 rad", source="upstream_code", ref=f"{ROTATE_CUBE}:224-230"),
        Fact("The dense reward is clamped to -15 to 15 and set to 15 on success", source="upstream_code",
             ref=f"{ROTATE_CUBE}:340-341"),
        Fact("The normalised dense reward is dense/(2*15)+0.5, so it lies in 0 to 1", source="upstream_code",
             ref=f"{ROTATE_CUBE}:344-347"),
        Fact("The supported reward modes are normalized_dense, dense, sparse and none, in that order",
             source="upstream_code", ref=f"{SAPIEN_ENV}:128"),
        Fact("A reward_mode of None selects the first supported reward mode", source="upstream_code",
             ref=f"{SAPIEN_ENV}:298-300"),
        Fact("The simulation runs at sim_freq 100 Hz and control_freq 20 Hz; every control step contains "
             "sim_freq/control_freq simulation steps", source="upstream_code", ref=f"{SIM_TYPES}:83-86"),
        Fact("The control timestep is 1/control_freq and the simulation timestep is 1/sim_freq", source="upstream_code",
             ref=f"{SAPIEN_ENV}:474-482"),
        Fact("The supported observation modes start with state", source="upstream_code", ref=f"{SAPIEN_ENV}:124"),
        Fact("An obs_mode of None selects the first supported observation mode", source="upstream_code",
             ref=f"{SAPIEN_ENV}:284-286"),
        Fact("A state observation is the agent's proprioception plus the task's extra observations",
             source="upstream_code", ref=f"{SAPIEN_ENV}:547-552"),
        Fact("The default proprioception is the robot's qpos and qvel, plus a controller state when it is non-empty",
             source="upstream_code", ref=f"{BASE_AGENT}:339-347"),
        Fact("The RotateCube task adds goal_pos, goal_q, obj_p and obj_q to the extra observation", source="upstream_code",
             ref=f"{ROTATE_CUBE}:253-263"),
        Fact("A state observation is flattened with flatten_state_dict before it is returned", source="upstream_code",
             ref=f"{SAPIEN_ENV}:536-539"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the last world state stays readable")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The fake is a kinematic stand-in, not
    #: SAPIEN; the bridge derives the engine's timestep as 0 (ManiSkill has no ``dt`` attribute), so the 50 ms
    #: control step of sim 100 Hz / control 20 Hz is written out from the cited lines.
    fidelity = {
        "engine": "gymnasium:TriFingerRotateCubeLevel0-v1 (custom kinematic stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial joints and the goal sample and the fake's "
                     "dynamics are deterministic, so this package repeats a trajectory for one seed; upstream draws "
                     "from torch/numpy generators, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics, contacts, friction, actuators or constraints: the fake moves the nine finger "
            "joints and the cube by a direct kinematic update (F0)",
            "the fake observation is a flat 32-value vector laid out like the default state observation (9 qpos, "
            "9 qvel, 3 goal_pos, 4 goal_q, 3 obj_p, 4 obj_q), but every value comes from the kinematic stand-in, not "
            "from SAPIEN/PhysX",
            "the fake samples initial joints and the goal with Python's random.Random while upstream uses "
            "torch/numpy generators, so one seed does not reproduce an upstream trajectory",
            "rendering, cameras, sensor data and visual observation modes are not modelled; the fake serves the "
            "default state observation only",
            "no wall-clock pacing: realtime_factor 0 and ticks advance simulated time by the 50 ms control step only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
        ],
    }
