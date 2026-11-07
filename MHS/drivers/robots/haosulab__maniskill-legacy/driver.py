"""OpenMHS driver for gh.haosulab/maniskill-legacy: the OpenCabinetDoor-v0 environment (a Gymnasium family driver).

ManiSkill legacy is a set of simulated manipulation environments built on the OpenAI Gym interface
(``README.md:65``); ``OpenCabinetDoor-v0`` is registered through ``gym.register`` with entry point
``mani_skill.env.open_cabinet_door_drawer:OpenCabinetDoorEnv`` (``mani_skill/env/__init__.py:11-14``).  The driver is a
``GymnasiumDriver`` family member: configuration only, and the bridge derives the contract from the environment's
spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the Box action ``{values}`` (the legacy environment
clips and scales it from [-1, 1], ``mani_skill/env/base_env.py:95`` and :538-542), ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

The device is a simulator (mode ``simulated``, risk R0, the catalogue floor of ``cap.world.*``): it has no hardware
backend and no path to a physical machine, so there is no e-stop to wire and no operator-required limit.  The
``fake`` backend is the package's own analytic stand-in (``fake.py``); the upstream engine (SAPIEN/Vulkan, the
PartNet Mobility assets, ``install.gpu`` true) was not importable where the gate runs and package code never imports
the clone.  A backend name that ``backends`` does not list (``sim``) would be served by ``gym.make(env_id)`` after the
upstream package installed it; that path was not run here.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002): an analytic drawer, not the
upstream rigid-body simulation.  Every constant and rule cites a line of the clone at the pinned commit
58964d08b4c7d2e14c5e6e287dbb9430d900f54d.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE_ENV = "mani_skill/env/base_env.py"
DOOR_ENV = "mani_skill/env/open_cabinet_door_drawer.py"
MISC = "mani_skill/utils/misc.py"
DOOR_CONFIG = "mani_skill/assets/config_files/open_cabinet_door.yml"
ARM_CONFIG = "mani_skill/assets/config_files/robots/mobile_a2_single_arm.yml"


class OpenCabinetDoor(GymnasiumDriver):
    device_id = "maniskill_open_cabinet_door"
    env_id = "OpenCabinetDoor-v0"
    native = "mani_skill.env.open_cabinet_door_drawer:OpenCabinetDoorEnv"
    backends = {"fake": ".fake:FakeOpenCabinetDoorEnv"}
    action_space_ref = f"{BASE_ENV}:95"
    display_name = "ManiSkill legacy OpenCabinetDoor-v0 (simulated)"
    vendor, model = "Haosulab", "ManiSkill legacy OpenCabinetDoor-v0"
    tags = ["maniskill", "manipulation", "cabinet-door", "simulation", "gym", "gymnasium"]
    facts = [
        Fact("ManiSkill environments are built on the OpenAI Gym interface", source="vendor_doc",
             ref="README.md:65"),
        Fact("The basic example constructs an environment with gym.make('OpenCabinetDoor-v0')", source="vendor_doc",
             ref="README.md:135"),
        Fact("OpenCabinetDoor-v0 is registered through gym.register with entry point "
             "mani_skill.env.open_cabinet_door_drawer:OpenCabinetDoorEnv", source="upstream_code",
             ref="mani_skill/env/__init__.py:11-14"),
        Fact("The action space is Box(low=-1, high=1, shape=agent.action_range().shape)", source="upstream_code",
             ref=f"{BASE_ENV}:95"),
        Fact("The mobile_a2_single_arm robot config has 13 controllable joints", source="upstream_code",
             ref=f"{ARM_CONFIG}:18-30"),
        Fact("Each step clips the action to [-1, 1] and scales it to the agent's action range", source="upstream_code",
             ref=f"{BASE_ENV}:538-542"),
        Fact("step advances frame_skip control steps of the agent and the scene and returns obs, reward, done, info",
             source="upstream_code", ref=f"{BASE_ENV}:544-571"),
        Fact("One environment step covers frame_skip / control_frequency seconds", source="upstream_code",
             ref=f"{BASE_ENV}:97"),
        Fact("The BaseEnv constructor's default frame_skip is 5 and its default max_episode_steps is 200",
             source="upstream_code", ref=f"{BASE_ENV}:69-70"),
        Fact("The mobile_a2_single_arm robot config sets control_frequency to 100", source="upstream_code",
             ref=f"{ARM_CONFIG}:4"),
        Fact("In state mode get_obs returns get_state(with_controller_state=False)", source="upstream_code",
             ref=f"{BASE_ENV}:636-640"),
        Fact("get_state concatenates the actor states, the padded articulation states, the task info and the agent "
             "state", source="upstream_code", ref=f"{BASE_ENV}:471-479"),
        Fact("get_pad_articulation_state returns the 13 pose/velocity values then 2 * max_dof internal values",
             source="upstream_code", ref=f"{MISC}:51-57"),
        Fact("OpenCabinetEnvBase.configure_env sets cabinet_max_dof to 8", source="upstream_code",
             ref=f"{DOOR_ENV}:35-36"),
        Fact("The target indicator is an 8-element zero vector with a 1 at the target joint's active index",
             source="upstream_code", ref=f"{DOOR_ENV}:158-159"),
        Fact("The state-mode observation space is a Box whose bounds are -inf and inf", source="upstream_code",
             ref=f"{BASE_ENV}:423-427"),
        Fact("target_qpos = lmin + (lmax - lmin) * custom['open_extent']", source="upstream_code",
             ref=f"{DOOR_ENV}:51-53"),
        Fact("The open_cabinet_door config sets custom.open_extent to 0.9", source="upstream_code",
             ref=f"{DOOR_CONFIG}:48-49"),
        Fact("The success flag open_enough is true when the target joint's qpos is at least target_qpos",
             source="upstream_code", ref=f"{DOOR_ENV}:234-240"),
        Fact("seed sets the main seed and a numpy RandomState from it", source="upstream_code",
             ref=f"{BASE_ENV}:183-185"),
        Fact("reset(level) seeds the level RNG from level and, when level is None, draws a 32-bit level from the main "
             "RNG", source="upstream_code", ref=f"{BASE_ENV}:138-142"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:mani_skill_open_cabinet_door_v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) (or cap.world.seed.v1 before a reset) fixes the fake's initial opening and the "
                     "analytic transition is deterministic, so one seed repeats a trajectory; upstream reset(level) "
                     "seeds numpy's RandomState from the level, and the fake uses Python's random.Random, so a seed "
                     "does not select the same episode in the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic kinematic model: no rigid-body dynamics, contacts, friction, joints or actuators; the drawer "
            "opens by a fixed fraction per step, so no force, contact or actuator fidelity is claimed (F0)",
            "the 75-value observation has the shape of the state-mode vector (cabinet pose/state, 8-element target "
            "indicator, 38-value agent state), but only the cabinet root quaternion, the target joint qpos and the "
            "target indicator carry modelled values; the agent state and velocities are placeholder zeros",
            "the dense reward is an analytic distance to the target opening, not the upstream compute_dense_reward",
            "state observations only: no rendering, point cloud or RGB-D observation, and no cameras",
            "the episode ends on success or after a fixed 200-step cap held in the fake; the upstream cap is the "
            "max_episode_steps constructor argument",
            "the fake and upstream do not share a random stream: a seed gives different episodes in the two",
            "the sim backend (gym.make('OpenCabinetDoor-v0')) was not run; it needs SAPIEN, a GPU and the PartNet "
            "Mobility assets",
        ],
    }
