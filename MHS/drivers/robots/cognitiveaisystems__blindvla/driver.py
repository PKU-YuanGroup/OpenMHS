"""OpenMHS driver for gh.cognitiveaisystems/blindvla: the ManiSkill Empty-v1 scene (a Gymnasium family driver).

The card names five ManiSkill entry symbols; this package serves ``EmptyEnv`` (``Empty-v1``), the bare scene in which
the Panda robot is placed and no task reward is computed.  A GymnasiumDriver is configuration only: ``env_id`` names
the environment and the bridge derives the contract from the environment's spaces.  ``cap.world.step.v1`` takes
``{ticks, action}`` with the action ``{values}``: eight values in -1 .. 1, the normalised action that ManiSkill serves
for the Panda's default ``pd_joint_delta_pos`` controllers and scales to seven arm joint deltas and one gripper target.
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import ManiSkill (it needs SAPIEN, PyTorch, gymnasium and the ManiSkill asset store), so the ``fake``
backend is the package's own pure Python stand-in for ``EmptyEnv`` (fake.py).  A backend name that ``backends`` does
not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path also needs
``import mani_skill.envs`` first, and it was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
The fake backend is kinematic (F0): it advances the joint positions and never simulates SAPIEN/PhysX forces or
contacts, which the ``gaps`` say.  Every constant and rule below cites a line of the clone at the pinned commit
(06855fcb91d65c88ca351a2d45af0be860a91987), the step bounds too: ``action_space_ref`` cites the line of the clone's
vendored ManiSkill that writes the normalised space.  This package is model-authored and unreviewed: it is checked on
the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

EMPTY = "ManiSkill/mani_skill/envs/tasks/empty_env.py"
SAPIEN_ENV = "ManiSkill/mani_skill/envs/sapien_env.py"
BASE_AGENT = "ManiSkill/mani_skill/agents/base_agent.py"
PANDA = "ManiSkill/mani_skill/agents/robots/panda/panda.py"
CONTROLLERS = "ManiSkill/mani_skill/agents/controllers"
GYM_UTILS = "ManiSkill/mani_skill/utils/gym_utils.py"
TYPES = "ManiSkill/mani_skill/utils/structs/types.py"
REGISTRATION = "ManiSkill/mani_skill/utils/registration.py"


class BlindVLAEmpty(GymnasiumDriver):
    device_id = "blindvla-empty"
    env_id = "Empty-v1"
    native = "ManiSkill.mani_skill.envs.tasks.empty_env:EmptyEnv"
    backends = {"fake": ".fake:FakeEmptyEnv"}
    action_space_ref = f"{GYM_UTILS}:108-110"
    display_name = "BlindVLA ManiSkill Empty-v1 (Panda)"
    vendor, model = "Cognitive AI Systems", "ManiSkill Empty-v1"
    tags = ["blindvla", "maniskill", "empty", "panda", "gymnasium", "simulation"]
    facts = [
        Fact("Empty-v1 is registered with max_episode_steps=200000", source="upstream_code",
             ref=f"{EMPTY}:17"),
        Fact("EmptyEnv loads the Panda robot by default (robot_uids='panda')", source="upstream_code",
             ref=f"{EMPTY}:24"),
        Fact("EmptyEnv supports only the reward mode 'none'", source="upstream_code", ref=f"{EMPTY}:19"),
        Fact("With reward mode 'none' the environment returns a zero reward tensor", source="upstream_code",
             ref=f"{SAPIEN_ENV}:611-612"),
        Fact("EmptyEnv.evaluate returns an empty dictionary, so info carries no success or fail key",
             source="upstream_code", ref=f"{EMPTY}:47-48"),
        Fact("With no success or fail in info, step returns terminated as a zero boolean tensor",
             source="upstream_code", ref=f"{SAPIEN_ENV}:959-963"),
        Fact("BaseEnv's supported observation modes start with 'state'", source="upstream_code",
             ref=f"{SAPIEN_ENV}:117"),
        Fact("When no observation mode is given, BaseEnv takes the first supported mode", source="upstream_code",
             ref=f"{SAPIEN_ENV}:270-271"),
        Fact("A state observation flattens the agent and extra observation dictionaries into one array",
             source="upstream_code", ref=f"{SAPIEN_ENV}:502-504"),
        Fact("An agent's proprioceptive observation is its qpos and qvel", source="upstream_code",
             ref=f"{BASE_AGENT}:337"),
        Fact("Panda's arm controller lists seven joints and its gripper controller lists two joint names",
             source="upstream_code", ref=f"{PANDA}:53-65"),
        Fact("Panda's rest keyframe stores nine joint values", source="upstream_code", ref=f"{PANDA}:36-47"),
        Fact("Panda's first controller configuration is pd_joint_delta_pos", source="upstream_code",
             ref=f"{PANDA}:186-189"),
        Fact("When no control mode is given, an agent uses the first supported control mode", source="upstream_code",
             ref=f"{BASE_AGENT}:106-109"),
        Fact("An agent serves a control mode whose configuration is a dict with a CombinedController",
             source="upstream_code", ref=f"{BASE_AGENT}:258-266"),
        Fact("The pd_joint_delta_pos arm config sets lower=-0.1, upper=0.1 and use_delta=True and does not set "
             "normalize_action", source="upstream_code", ref=f"{PANDA}:90-98"),
        Fact("The mimic gripper config sets lower=-0.01 and upper=0.04 and does not set normalize_action",
             source="upstream_code", ref=f"{PANDA}:177-184"),
        Fact("PDJointPosControllerConfig defaults normalize_action to True", source="upstream_code",
             ref=f"{CONTROLLERS}/pd_joint_pos.py:121"),
        Fact("PDJointPosMimicControllerConfig subclasses PDJointPosControllerConfig and only sets its controller "
             "class", source="upstream_code", ref=f"{CONTROLLERS}/pd_joint_pos.py:134-135"),
        Fact("The mimic gripper controller reduces its two joints to one action dimension", source="upstream_code",
             ref=f"{CONTROLLERS}/pd_joint_pos.py:126-131"),
        Fact("A controller calls _clip_and_scale_action_space when its config sets normalize_action",
             source="upstream_code", ref=f"{CONTROLLERS}/base_controller.py:65-67"),
        Fact("_clip_and_scale_action_space replaces the single action space with normalize_action_space of the "
             "original one", source="upstream_code", ref=f"{CONTROLLERS}/base_controller.py:154-158"),
        Fact("normalize_action_space returns Box(-1, 1) with the shape and dtype of the space it is given",
             source="upstream_code", ref=f"{GYM_UTILS}:108-110"),
        Fact("clip_and_scale_action clips an action to [-1, 1] and scales it to 0.5 * (high + low) + "
             "0.5 * (high - low) * action", source="upstream_code", ref=f"{GYM_UTILS}:102-105"),
        Fact("The combined controller flattens the single action spaces of its controllers into one space",
             source="upstream_code", ref=f"{CONTROLLERS}/base_controller.py:281-285"),
        Fact("A controller exposes its single action space and batches it only when there is more than one "
             "environment", source="upstream_code", ref=f"{CONTROLLERS}/base_controller.py:68-72"),
        Fact("An agent's action spaces are those of its current controller", source="upstream_code",
             ref=f"{BASE_AGENT}:292-314"),
        Fact("BaseEnv takes its action space and single action space from its agent", source="upstream_code",
             ref=f"{SAPIEN_ENV}:316-319"),
        Fact("BaseEnv's default num_envs is 1", source="upstream_code", ref=f"{SAPIEN_ENV}:187"),
        Fact("The simulation frequency is 100 Hz and the control frequency is 20 Hz", source="upstream_code",
             ref=f"{TYPES}:80-83"),
        Fact("The MSTimeLimit wrapper truncates at the registered max_episode_steps", source="upstream_code",
             ref=f"{REGISTRATION}:249-254"),
        Fact("TimeLimitWrapper reports truncated when elapsed_steps is at least max_episode_steps",
             source="upstream_code", ref=f"{REGISTRATION}:160-163"),
    ]
    safe_state = ("the simulation stops advancing: an e-stop latches the runtime and no step or reset is accepted "
                  "until mhs.safety.reset clears the latch; the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:Empty-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 records the seed used by the next reset; the fake starts every "
                     "episode from the same zero joint state, so a seed does not change its trajectory. Upstream "
                     "ManiSkill seeds its main and episode RNG from the reset seed.",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is kinematic: one step adds the scaled joint deltas to qpos, sets the gripper target "
            "and clears qvel; SAPIEN PhysX rigid-body dynamics, contacts, friction, actuator forces, sensors and "
            "noise are not simulated (F0, no dynamics)",
            "no wall-clock pacing: realtime_factor 0, one step advances simulated time by timestep_ms (50 ms from "
            "the 20 Hz control frequency) only",
            "the observation is the 18-element qpos+qvel state of the Panda (nine joints twice) that Empty-v1 uses "
            "with its default state observation mode; no camera image, depth or point cloud is returned",
            "the action is ManiSkill's normalised one, eight values in -1..1 (ManiSkill/mani_skill/utils/"
            "gym_utils.py:108-110): the fake clips and scales each value as clip_and_scale_action does "
            "(gym_utils.py:102-105), to an arm joint delta in -0.1..0.1 or the gripper target in -0.01..0.04, and "
            "assigns the same target to both finger joints as the mimic controller broadcasts "
            "(pd_joint_pos.py:84-86); instantaneous qpos assignment remains a kinematic placeholder, and the "
            "external Panda asset joint limits and drive dynamics are not reproduced",
            "the fake was not compared with the upstream ManiSkill environment (SAPIEN and PyTorch are not "
            "installed where the gate runs); reset uses a zero joint state placeholder while upstream loads the "
            "Panda articulation pose",
            "the 200000-step Empty-v1 time limit is modelled by the fake, but no package test runs that long",
            "snapshot and restore are not offered: this package's fake exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
