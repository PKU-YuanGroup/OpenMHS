"""OpenMHS driver for gh.jerrypeng0201/nebula: the SceneManipulation-v1 environment (Gymnasium family driver).

A :class:`GymnasiumDriver` is configuration only: ``env_id`` names the environment and the bridge derives the contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` bounded per
element by the flattened Fetch controller action space, normalized to -1..1 on each of its 13 values;
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no stop path to a machine and no operator-required limit.

``env_kwargs`` pins the deployment to one environment, the default Fetch robot and the first Fetch controller config,
``pd_joint_delta_pos``, so the derived action bounds describe the configuration this package serves.  The upstream code
is read-only; the gate parses it and never imports it.

The gate cannot import the upstream environment (it needs SAPIEN, torch, ReplicaCAD assets and a renderer), so the
``fake`` backend is the package's own pure Python stand-in (fake.py).  A backend name that ``backends`` does not list
(``sim``) is served by ``gymnasium.make("SceneManipulation-v1", robot_uids="fetch",
control_mode="pd_joint_delta_pos")`` through :class:`GymnasiumDriver.open_native`; that path was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit 2d16ad04e9825b4a6212847ba847e5ae910feed4.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE_ENV = "nebula/core/simulation/scenes/base_env.py"
ENGINE = "nebula/core/simulation/engine.py"
FETCH = "nebula/core/embodiment/robots/fetch/fetch.py"
MANIPULATOR = "nebula/core/embodiment/manipulator.py"
TYPES = "nebula/utils/structs/types.py"
JOINT_POS = "nebula/core/embodiment/actuators/joint_position_control.py"
JOINT_VEL = "nebula/core/embodiment/actuators/joint_velocity_control.py"
BASE_ACTUATOR = "nebula/core/embodiment/actuators/base_actuator.py"
BASE_VEL = "nebula/core/embodiment/actuators/base_velocity_control.py"
EMBEDDING_UTILS = "nebula/core/embodiment/utils.py"
GYM_UTILS = "nebula/utils/gym_utils.py"


class SceneManipulation(GymnasiumDriver):
    device_id = "nebula-scene-manipulation"
    env_id = "SceneManipulation-v1"
    native = "nebula.core.simulation.scenes.base_env:SceneManipulationEnv"
    backends = {"fake": ".fake:FakeSceneManipulationEnv"}
    env_kwargs = {"robot_uids": "fetch", "control_mode": "pd_joint_delta_pos", "num_envs": 1}
    display_name = "NEBULA SceneManipulation-v1 (Fetch manipulation scene)"
    vendor, model = "JerryPeng0201", "NEBULA SceneManipulation-v1"
    tags = ["gymnasium", "manipulation", "fetch", "sapien", "reinforcement-learning", "simulation", "scene"]
    facts = [
        Fact("SceneManipulation-v1 is registered with max_episode_steps=200", source="upstream_code",
             ref=f"{BASE_ENV}:19"),
        Fact("The environment supports the panda and fetch robots and creates a fetch agent by default",
             source="upstream_code", ref=f"{BASE_ENV}:40-46"),
        Fact("The environment is for explorations and visualization and has no success/failure metrics or rewards",
             source="upstream_code", ref=f"{BASE_ENV}:21-23"),
        Fact("evaluate() returns an empty dict, compute_dense_reward() returns 0, and the normalized dense reward "
             "divides that 0 by 1", source="upstream_code", ref=f"{BASE_ENV}:142-151"),
        Fact("reset accepts seed and options, including reconfigure and build or init config indices",
             source="upstream_code", ref=f"{BASE_ENV}:85-105"),
        Fact("The default scene builder is ReplicaCAD", source="upstream_code", ref=f"{BASE_ENV}:47"),
        Fact("The first supported observation mode is state", source="upstream_code", ref=f"{ENGINE}:127"),
        Fact("A None obs_mode selects the first supported observation mode, state", source="upstream_code",
             ref=f"{ENGINE}:280-281"),
        Fact("A state observation is the dict {agent, extra}; get_obs flattens it to one tensor",
             source="upstream_code", ref=f"{ENGINE}:529-544"),
        Fact("The agent's proprioception is its qpos and qvel, plus controller state only when the controller "
             "returns one", source="upstream_code", ref=f"{MANIPULATOR}:333-341"),
        Fact("Fetch has 7 arm, 2 gripper, 3 body and 3 base joints", source="upstream_code",
             ref=f"{FETCH}:78-114"),
        Fact("A None control_mode selects the first supported control mode, the first controller config key",
             source="upstream_code", ref=f"{MANIPULATOR}:105-111"),
        Fact("The first Fetch controller config key is pd_joint_delta_pos with arm, gripper, body and base "
             "controllers", source="upstream_code", ref=f"{FETCH}:258-264"),
        Fact("The Fetch arm delta controller is configured with raw joint bounds -0.1 to 0.1 for the 7 arm joints",
             source="upstream_code", ref=f"{FETCH}:132-140"),
        Fact("The Fetch gripper is a mimic controller with one mimic entry mapping r_gripper_finger_joint to "
             "l_gripper_finger_joint and raw bounds -0.01 to 0.05", source="upstream_code",
             ref=f"{FETCH}:213-221"),
        Fact("A mimic controller deduplicates its control joints and reads the joint limits at those indices, so "
             "this gripper has one action dimension", source="upstream_code", ref=f"{JOINT_POS}:193-205"),
        Fact("The Fetch body delta controller is configured with raw joint bounds -0.1 to 0.1 for the 3 body "
             "joints", source="upstream_code", ref=f"{FETCH}:226-234"),
        Fact("The Fetch base forward velocity controller is configured with lower [-1, -3.14] and upper "
             "[1, 3.14]", source="upstream_code", ref=f"{FETCH}:250-256"),
        Fact("The base forward velocity controller broadcasts its configured bounds to two action elements, "
             "forward velocity and rotation velocity", source="upstream_code", ref=f"{BASE_VEL}:42-46"),
        Fact("The joint position controller config defaults normalize_action to True", source="upstream_code",
             ref=f"{JOINT_POS}:113-126"),
        Fact("The joint velocity controller config defaults normalize_action to True", source="upstream_code",
             ref=f"{JOINT_VEL}:46-54"),
        Fact("When a controller config enables normalize_action, ActuatorController.__init__ calls "
             "_clip_and_scale_action_space", source="upstream_code", ref=f"{BASE_ACTUATOR}:67-72"),
        Fact("_clip_and_scale_action_space replaces the configured Box with normalize_action_space(...) and keeps "
             "the raw low and high bounds for clipping and scaling", source="upstream_code",
             ref=f"{BASE_ACTUATOR}:159-169"),
        Fact("normalize_action_space returns Box(-1, 1) with the original shape", source="upstream_code",
             ref=f"{GYM_UTILS}:108-110"),
        Fact("The combined controller flattens the named Box spaces into one Box with per-element low and high "
             "bounds", source="upstream_code", ref=f"{EMBEDDING_UTILS}:28-56"),
        Fact("The simulation runs at 100 Hz and the control loop at 20 Hz, so every control step contains five "
             "simulation steps", source="upstream_code", ref=f"{TYPES}:80-83"),
        Fact("A seeded reset sets the main RNG and the episode RNG to the seed; an unseeded reset samples the "
             "episode seed from the main RNG", source="upstream_code", ref=f"{ENGINE}:884-887"),
        Fact("step returns (observation, reward, terminated, truncated, info); without success or fail in info, "
             "terminated is a zero tensor", source="upstream_code", ref=f"{ENGINE}:1036-1053"),
        Fact("A floating-point observation is converted to a Box with bounds -inf to inf", source="upstream_code",
             ref=f"{GYM_UTILS}:145-154"),
        Fact("The observation space is the single observation space batched over num_envs", source="upstream_code",
             ref=f"{ENGINE}:365-373"),
    ]
    safe_state = ("no step or reset advances the simulated world after an e-stop until mhs.safety.reset clears the "
                  "runtime latch; the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "sapien:SceneManipulation-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the episode RNG, and one implementation repeats a "
                     "trajectory for the same seed and actions; this package's fake draws its initial joint "
                     "offsets with Python's random.Random, upstream uses numpy random states, so one seed gives "
                     "different trajectories on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body PhysX dynamics of a Fetch robot in a ReplicaCAD scene: contacts, friction, actuator "
            "forces, sensors and noise are the engine's, not this package's; no rendering or camera observation "
            "is served by the fake",
            "the deployed model is the default fetch configuration with the pd_joint_delta_pos controller; other "
            "robots (panda) and other control modes have different action spaces and are not served here",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (50 ms = five "
            "20 Hz control steps) only",
            "the fake backend is a kinematic stand-in, not a physics engine: it applies the 13 action values to "
            "the first 13 qpos entries and reports qvel from the last action, with no contacts, controller "
            "dynamics or asset loading; it was never compared with the upstream environment",
            "the fake returns the unbatched 30-value state observation (15 qpos + 15 qvel); the upstream "
            "observation_space batches it to (1, 30) and the fake does not expose get_state/set_state, so no "
            "snapshot is offered on the fake (the upstream BaseEnv does define get_state/set_state)",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
