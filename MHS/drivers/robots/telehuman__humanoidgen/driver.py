"""OpenMHS driver for gh.telehuman/humanoidgen: the ``blocks_stack_easy`` ManiSkill task (Gymnasium family).

A GymnasiumDriver is configuration only.  ``env_id`` names the registered task, the bridge derives
``cap.world.step.v1`` (``{ticks, action}``), ``cap.world.reset.v1`` (``{seed, options}``) and
``cap.world.seed.v1`` (``{seed}``) from the environment's spaces, and the driver adds the facts and the fidelity
contract.  The environment is simulated (R0): there is no hardware backend and no operator-required bound.

The concrete task class is ``BlocksStackEasyEnv`` (blocks_stack_easy.py:4); the card also names its base
``TableSetting`` (table_scene.py:392), which declares ``reset`` and ``step``.  The card's first entry symbol is used
as ``native`` because the concrete class reaches ``TableSetting`` through ``from ...task_env import *``, a star
import that the gate's AST reader cannot follow; the fake implements the ``TableSetting`` surface (gate G7).

The gate cannot import SAPIEN, ManiSkill, torch or the clone, so the ``fake`` backend is this package's pure Python
stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) would be served by
``gymnasium.make(env_id)``; that path needs the ManiSkill stack and the repository's external assets
(README.md:90, requirements.txt:1) and was not run here.  This package is model-authored and unreviewed; it is
checked on the fake backend only and no hardware or simulator run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

TABLE = "humanoidgen/envs/example/table_scene.py"
BLOCKS = "humanoidgen/envs/example/blocks_stack_easy.py"
ROBOT = "humanoidgen/agents/robots/unitree_h1_2/h1_2_upper_body.py"
RUN = "humanoidgen/process/run_scene.py"
CONFIG = "humanoidgen/config/config_run_scene.yml"


class HumanoidGenBlocksStack(GymnasiumDriver):
    device_id = "humanoidgen_blocks_stack_easy"
    env_id = "blocks_stack_easy"
    native = "humanoidgen.envs.example.table_scene:TableSetting"
    backends = {"fake": ".fake:FakeBlocksStackEasyEnv"}
    display_name = "HumanoidGen blocks_stack_easy (ManiSkill table task)"
    vendor, model = "TeleHuman", "HumanoidGen blocks_stack_easy"
    tags = ["humanoidgen", "blocks-stack", "manipulation", "table", "maniskill", "sapien", "simulation",
            "gymnasium"]
    facts = [
        Fact("ManiSkill is the simulation platform named by the repository", source="vendor_doc",
             ref="README.md:211"),
        Fact("The table_scene module imports BaseEnv from mani_skill.envs.sapien_env", source="upstream_code",
             ref=f"{TABLE}:17"),
        Fact("TableEnv subclasses ManiSkill's BaseEnv", source="upstream_code", ref=f"{TABLE}:83"),
        Fact("TableSetting subclasses TableEnv", source="upstream_code", ref=f"{TABLE}:392"),
        Fact("BlocksStackEasyEnv subclasses TableSetting", source="upstream_code", ref=f"{BLOCKS}:4"),
        Fact("blocks_stack_easy is registered with max_episode_steps=200", source="upstream_code",
             ref=f"{BLOCKS}:3"),
        Fact("The task adds two cube objects, one per object id", source="upstream_code",
             ref=f"{BLOCKS}:9-10"),
        Fact("The success test compares cube 0 with [-0.3, 0, 0.02] and cube 1 with [-0.3, 0, 0.06] using "
             "eps [0.03, 0.03, 0.01]", source="upstream_code", ref=f"{BLOCKS}:44-52"),
        Fact("TableSetting.reset takes seed and options and returns the (observation, info) tuple of "
             "BaseEnv.reset", source="upstream_code", ref=f"{TABLE}:249-251"),
        Fact("TableSetting.step records the action and forwards it to BaseEnv.step", source="upstream_code",
             ref=f"{TABLE}:909-922"),
        Fact("The run configuration selects env_id blocks_stack_easy, control_mode pd_joint_pos, num_envs 1, "
             "env_seed 0 and random_scene true", source="vendor_doc", ref=f"{CONFIG}:2-30"),
        Fact("The H1_2 upper body has 14 arm joints and the inspire hand has 24 finger joints",
             source="upstream_code", ref=f"{ROBOT}:106-195"),
        Fact("The arm and finger controllers are PDJointPosControllerConfig with lower=None, upper=None and "
             "normalize_action=False, combined in the pd_joint_pos controller",
             source="upstream_code", ref=f"{ROBOT}:213-245"),
        Fact("The table environment's simulation config sets control_freq=100", source="upstream_code",
             ref=f"{TABLE}:266"),
        Fact("The run loop creates the environment with gym.make(env_id)", source="upstream_code",
             ref=f"{RUN}:54"),
        Fact("The run loop reads the robot's first 38 joint positions and passes them to env.step",
             source="upstream_code", ref=f"{RUN}:61-63"),
        Fact("TableSetting.evaluate returns an empty dict", source="upstream_code", ref=f"{TABLE}:1398-1399"),
        Fact("compute_dense_reward returns 1 and compute_normalized_dense_reward returns that value divided "
             "by 10", source="upstream_code", ref=f"{TABLE}:1408-1414"),
        Fact("The default sensor configuration adds a base_camera at 512 by 512 pixels", source="upstream_code",
             ref=f"{TABLE}:278"),
        Fact("The H1_2 URDF is loaded from the assets directory of the clone", source="upstream_code",
             ref=f"{ROBOT}:27"),
        Fact("The repository asks the user to download assets.zip and table_assets.zip into the assets "
             "directories", source="vendor_doc", ref="README.md:90"),
        Fact("The pinned ManiSkill dependency is mani_skill==3.0.0b21", source="vendor_doc",
             ref="requirements.txt:1"),
        Fact("The codebase is under CC BY-NC 4.0", source="vendor_doc", ref="README.md:206"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the bridge accepts neither step nor reset "
                  "until mhs.safety.reset clears the latch, and the last observation stays readable")
    #: The contract of the model this package deploys (spec 05-fidelity FID-002): the analytic fake, not the SAPIEN
    #: scene the upstream class would build.
    fidelity = {
        "engine": "analytic:humanoidgen blocks_stack_easy fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds its initial joint-position jitter from reset(seed) or cap.world.seed.v1 and "
                     "its transitions are deterministic; upstream scene randomization uses get_random_pose and "
                     "ManiSkill's random generator, so the two streams are not the same",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body simulation: SAPIEN integration, contacts, friction, gravity, the H1_2 robot, the "
            "table scene and the two cubes are not modelled; the fake stores and echoes the 38 commanded joint "
            "positions",
            "observation surrogate: the fake returns 38 joint positions, while the environment's state "
            "observation (obs_mode null) and the 512 by 512 base_camera image are not reproduced "
            "(table_scene.py:278)",
            "success and termination: TableSetting.evaluate returns an empty dict (table_scene.py:1398-1399); "
            "the fake models only the registered 200-step episode limit and does not evaluate the cube "
            "placement success test",
            "reward: the fake returns 0.0; compute_normalized_dense_reward returns 0.1 under the "
            "normalized_dense reward mode (table_scene.py:1408-1414), while the run configuration leaves "
            "reward_mode null",
            "action envelope: the upstream controllers take joint limits from the robot model in the external "
            "assets, so the package declares no sourced bound; the fake's 38-element Box is unbounded and no "
            "Limit is declared",
            "seeding is partial: the fake draws its initial jitter with Python random.Random, not with the "
            "ManiSkill random generator or get_random_pose",
            "no assets, GPU, SAPIEN or ManiSkill are installed here, so the sim backend (gymnasium.make of the "
            "registered env_id) was not run",
            "no rendering and no snapshot or restore: the fake exposes no get_state/set_state pair",
        ],
    }
