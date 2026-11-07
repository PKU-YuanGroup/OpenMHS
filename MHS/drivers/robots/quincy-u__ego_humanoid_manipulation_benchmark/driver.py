"""OpenMHS driver for gh.quincy-u/ego_humanoid_manipulation_benchmark: the Humanoid-Base-v0 environment.

The benchmark is a family of Isaac Lab direct-RL environments registered with Gymnasium.  This package serves the
base member, ``Humanoid-Base-v0`` (``entry_point humanoid.tasks.base_env:BaseEnv``).  A ``GymnasiumDriver`` is
configuration only: ``env_id`` names the environment and the bridge derives the contract from its spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` with the action derived from the action space,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no path to a machine and no operator-required limit.

The action space is a ``Box`` of ``num_actions`` (50) elements.  The clone states the dimension and the clamp to
the robot's soft joint limits (base_env.py:120, :124, :211-214) but not the numeric joint limits: they belong to the
H1 asset data, which the README says is hosted on Hugging Face (README.md:23).  The driver therefore publishes no
numeric action bound; the fake's action space is unbounded and the runtime accepts a finite vector of that length.
Only ``scripts/random_agent.py:42`` samples actions in [-1, 1), a property of that agent, not a bound of the
environment, so it is recorded as a Fact and not used as a Limit.

The gate cannot run the upstream environment (Isaac Sim 4.2 and Isaac Lab 1.2.0 are external runtimes, README.md:17,
and package code never imports the clone), so ``backends["fake"]`` is this package's pure Python kinematic stand-in
(fake.py).  A backend name that ``backends`` does not list is served by ``gymnasium.make(env_id)``; that path needs
the upstream runtime and was not run here.  This package is model-authored and unreviewed, and it is checked on the
fake backend only.

Every fact cites a line of the clone at the pinned commit 4489a673153d40f0dcba84c9210c426edfc62812.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py"
REGISTER = "source/extensions/humanoid.tasks/humanoid/tasks/base_env/__init__.py"
TASKS = "source/extensions/humanoid.tasks/humanoid/tasks"


class HumanoidBase(GymnasiumDriver):
    device_id = "humanoid-base"
    env_id = "Humanoid-Base-v0"
    native = "humanoid.tasks.base_env:BaseEnv"
    backends = {"fake": ".fake:FakeHumanoidEnv"}
    display_name = "EgoVLA Humanoid-Base-v0 (Isaac Lab benchmark)"
    vendor, model = "quincy-u", "Humanoid-Base-v0"
    tags = ["humanoid", "manipulation", "isaac-lab", "isaac-sim", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("Humanoid-Base-v0 is registered with entry point humanoid.tasks.base_env:BaseEnv and BaseEnvCfg as its "
             "env_cfg_entry_point", source="upstream_code", ref=f"{REGISTER}:13-20"),
        Fact("BaseEnv subclasses DirectRLEnv, the Isaac Lab direct reinforcement-learning environment class",
             source="upstream_code", ref=f"{BASE}:134"),
        Fact("The default scene has four environments (num_envs=4) with 10.0 m spacing", source="upstream_code",
             ref=f"{BASE}:50"),
        Fact("The physics simulation runs with dt = 1/120 s and render_interval = 4", source="upstream_code",
             ref=f"{BASE}:31-34"),
        Fact("BaseEnvCfg sets decimation = 4", source="upstream_code", ref=f"{BASE}:118"),
        Fact("BaseEnv sets self.dt = cfg.sim.dt * cfg.decimation, so its control timestep follows from those two "
             "settings", source="upstream_code", ref=f"{BASE}:142"),
        Fact("BaseEnvCfg sets episode_length_s = 0.5", source="upstream_code", ref=f"{BASE}:117"),
        Fact("BaseEnvCfg sets action_scale = 1", source="upstream_code", ref=f"{BASE}:119"),
        Fact("BaseEnvCfg sets num_actions = 50 and action_space = num_actions", source="upstream_code",
             ref=f"{BASE}:120-124"),
        Fact("BaseEnvCfg sets num_observations = 99 and observation_space = num_observations", source="upstream_code",
             ref=f"{BASE}:121-123"),
        Fact("_apply_action multiplies the action by cfg.action_scale, clamps it to the robot's soft joint position "
             "limits and writes it as the joint position target", source="upstream_code", ref=f"{BASE}:211-214"),
        Fact("_get_dones compares the episode length buffer with max_episode_length and returns the same tensor as "
             "terminated and truncated", source="upstream_code", ref=f"{BASE}:217-219"),
        Fact("BaseEnv._get_rewards is empty, so the base environment defines no reward term", source="upstream_code",
             ref=f"{BASE}:297-298"),
        Fact("_get_observations returns a dictionary with rgb, fixed_rgb, fixed_d, left_hand_rgb, right_hand_rgb, "
             "qpos, qvel, action, left/right end-effector poses and targets, finger tip positions and hand contact "
             "forces", source="upstream_code", ref=f"{BASE}:278-295"),
        Fact("The left-eye and right-eye RGB images are concatenated along the width dimension (dim=2)",
             source="upstream_code", ref=f"{BASE}:257-259"),
        Fact("The left-eye and right-eye cameras are 360 x 640 and capture rgb and distance_to_image_plane",
             source="upstream_code", ref=f"{BASE}:63-82"),
        Fact("The main, left-hand and right-hand cameras are 720 x 1280 and capture rgb and distance_to_image_plane",
             source="upstream_code", ref=f"{BASE}:83-112"),
        Fact("The default robot is the H1 Inspire configuration (H1_INSPIRE_CFG) with separate left/right arm and "
             "hand configs", source="upstream_code", ref=f"{BASE}:52-56"),
        Fact("BaseEnvCfg enables object randomization with randomize = True, randomize_range = 1.0 and "
             "randomize_idx = -1", source="upstream_code", ref=f"{BASE}:130-132"),
        Fact("The random agent creates the environment with gym.make(task, cfg=env_cfg), resets it and drives it "
             "with env.step", source="upstream_code", ref="scripts/random_agent.py:38-43"),
        Fact("The random agent samples actions uniformly in [-1, 1) using env.action_space.shape",
             source="upstream_code", ref="scripts/random_agent.py:42"),
        Fact("The benchmark targets IsaacLab 1.2.0 and IsaacSim 4.2.0", source="vendor_doc", ref="README.md:17"),
        Fact("The asset data is hosted on Hugging Face, outside the clone", source="vendor_doc", ref="README.md:23"),
        Fact("The humanoid.tasks extension is installed editable with the Isaac Lab Python", source="vendor_doc",
             ref="README.md:36-39"),
        Fact("Humanoid-Close-Drawer-v0 is registered with entry point "
             "humanoid.tasks.close_drawer:CloseDrawerEnv", source="upstream_code",
             ref=f"{TASKS}/close_drawer/__init__.py:13-16"),
        Fact("CloseDrawerEnv subclasses BaseEnv", source="upstream_code",
             ref=f"{TASKS}/close_drawer/close_drawer.py:35"),
        Fact("Humanoid-Flip-Mug-v0 is registered with entry point humanoid.tasks.flip_mug:FlipMugEnv",
             source="upstream_code", ref=f"{TASKS}/flip_mug/__init__.py:13-16"),
        Fact("FlipMugEnv subclasses BaseEnv", source="upstream_code", ref=f"{TASKS}/flip_mug/flip_mug.py:48"),
        Fact("Humanoid-Insert-And-Unload-Cans-v0 is registered with entry point "
             "humanoid.tasks.insert_and_unload_cans:InsertAndUnloadCansEnv", source="upstream_code",
             ref=f"{TASKS}/insert_and_unload_cans/__init__.py:13-16"),
        Fact("InsertAndUnloadCansEnv subclasses BaseEnv", source="upstream_code",
             ref=f"{TASKS}/insert_and_unload_cans/insert_and_unload_cans.py:27"),
        Fact("Humanoid-Insert-Cans-v0 is registered with entry point humanoid.tasks.insert_cans:InsertCansEnv",
             source="upstream_code", ref=f"{TASKS}/insert_cans/__init__.py:13-16"),
        Fact("InsertCansEnv subclasses BaseEnv", source="upstream_code",
             ref=f"{TASKS}/insert_cans/insert_cans_env.py:27"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The level is F0 because the
    #: package's backend is a kinematic stand-in: it has no rigid-body dynamics and no contacts.  The timestep is
    #: the upstream control interval, sim dt 1/120 s at decimation 4 (base_env.py:32, :118, :142).
    fidelity = {
        "engine": "isaaclab:Humanoid-Base-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the fake's Python random generator, so one seed and action sequence repeat "
                     "the fake's trajectory; upstream Isaac Lab seeds torch and its own generators and randomizes "
                     "the object poses, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the package's fake is kinematic (F0): it writes the action vector to joint positions directly and "
            "models no rigid-body dynamics, contacts, friction, actuators, sensors, noise or camera rendering, so "
            "it cannot reproduce Isaac Lab/PhysX behaviour",
            "camera observations are placeholder 1 x 1 arrays: the upstream left-eye and right-eye cameras are "
            "360 x 640 rgb and are concatenated along the width (360 x 1280), and the main, left-hand and right-hand "
            "cameras are 720 x 1280 rgb plus distance_to_image_plane (base_env.py:63-112, :257-259)",
            "the fake returns the 16 observation keys of BaseEnv._get_observations with placeholder values; the "
            "upstream qpos/qvel lengths, end-effector poses, finger tips and contact forces come from the H1 assets "
            "and PhysX, which the clone does not contain",
            "only Humanoid-Base-v0 is served: the other registered task environments (Close-Drawer, Flip-Mug, "
            "Insert-Cans, Insert-And-Unload-Cans and the rest) are not bound, and their objects, rewards, success "
            "terms and randomization are not modelled",
            "the USD assets are hosted on Hugging Face and the clone has no Isaac Sim 4.2 or Isaac Lab 1.2.0 "
            "runtime (README.md:17, :23), so no upstream run was made and the fake was never compared with it",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "BaseEnv itself defines no reward (_get_rewards is empty) and reports the timeout as both terminated "
            "and truncated; the fake mirrors that and returns reward 0",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
