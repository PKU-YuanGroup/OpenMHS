"""OpenMHS driver for gh.indystrycc/spdrbot: the SPDR Bot Isaac Lab direct task (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values`` shaped by the environment's action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend and no e-stop path
to a machine.

The upstream is a vectorized Isaac Lab ``DirectRLEnv`` (``spdrbot3_env.py:20``, 200 environments in the default
config at ``spdrbot3_env_cfg.py:92``).  It needs Isaac Sim 4.5, Isaac Lab, ``isaaclab_assets`` and a GPU
(``spdrbot3_direct_project/README.md:15-26``, ``setup.py:38-42``), and it imports ``SPDRBOT_CFG`` from
``isaaclab_assets.robots.spdrbot`` (``spdrbot3_env_cfg.py:19``), a module that is not part of this clone.  The
acceptance gate cannot install or run that stack and package code never imports the clone, so ``backends`` names
only the package's analytic one-environment stand-in (``fake.py``).

The registered task passes ``env_cfg_entry_point`` as a keyword (``tasks/direct/spdrbot3/__init__.py:16-24``),
while ``Spdrbot3Env.__init__`` requires a ``cfg`` argument (``spdrbot3_env.py:23``): a bare
``gymnasium.make(env_id)`` does not construct this environment without the caller's configuration.  The implicit
``sim`` path was not run and is not declared here.  Every claim below cites the clone at commit
70084cd435e9871b3db69280cce49a4fb2246664.  This package is model-authored and unreviewed: it is checked on the
fake backend only, and no hardware, Isaac Sim or sim-backend run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3"
ENV = f"{BASE}/spdrbot3_env.py"
REGISTER = f"{BASE}/__init__.py"
CFG = f"{BASE}/spdrbot3_env_cfg.py"
PROJECT_README = "spdrbot3_direct_project/README.md"
SETUP = "spdrbot3_direct_project/source/spdrbot3/setup.py"
EXTENSION = "spdrbot3_direct_project/source/spdrbot3/config/extension.toml"
ROOT_CFG = "spdrbot.py"
README = "README.md"


class Spdrbot3Direct(GymnasiumDriver):
    device_id = "spdrbot3-direct"
    env_id = "Template-Spdrbot3-Direct-v0"
    native = "spdrbot3.tasks.direct.spdrbot3.spdrbot3_env:Spdrbot3Env"
    backends = {"fake": ".fake:FakeSpdrbot3Env"}
    #: The clone states only the action dimension (``action_space = 12``, spdrbot3_env_cfg.py:54).  The external
    #: DirectRLEnv builds the Box bounds, so no numeric bound is sourced from this clone and no action-space
    #: reference is claimed; the bridge derives the fake's unbounded Box without a source.
    display_name = "SPDR Bot quadruped direct task (Isaac Lab)"
    vendor, model = "indystrycc", "Template-Spdrbot3-Direct-v0"
    tags = ["spdrbot", "quadruped", "isaac-lab", "isaac-sim", "physx", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The package registers the Gymnasium task Template-Spdrbot3-Direct-v0 with entry point "
             "spdrbot3_env:Spdrbot3Env and the configuration spdrbot3_env_cfg:Spdrbot3EnvCfg",
             source="upstream_code", ref=f"{REGISTER}:16-24"),
        Fact("Spdrbot3Env is a concrete DirectRLEnv subclass: it implements the scene setup, action application, "
             "observations, rewards, dones and reset methods", source="upstream_code", ref=f"{ENV}:20-177"),
        Fact("The environment config declares action_scale = 1, action_space = 12, observation_space = 48 and "
             "state_space = 0", source="upstream_code", ref=f"{CFG}:53-56"),
        Fact("The environment config sets episode_length_s = 20.0 and decimation = 4",
             source="upstream_code", ref=f"{CFG}:51-52"),
        Fact("The simulation config uses a timestep of 1/200 s and render_interval = 1",
             source="upstream_code", ref=f"{CFG}:59-61"),
        Fact("Each action is multiplied by action_scale and added to the robot's default joint positions, then "
             "written with set_joint_position_target", source="upstream_code", ref=f"{ENV}:72-77"),
        Fact("The policy observation concatenates root linear velocity, root angular velocity, projected "
             "gravity, the commands, joint positions minus defaults, joint velocities and the actions",
             source="upstream_code", ref=f"{ENV}:79-98"),
        Fact("The reward is the sum of eight terms: linear velocity tracking, yaw-rate tracking, z velocity, xy "
             "angular velocity, joint torques, joint acceleration, action rate and flat orientation",
             source="upstream_code", ref=f"{ENV}:122-135"),
        Fact("The eight reward scales are 5.0, 0.5, -2.0, -0.05, -1e-5, -1e-7, -0.01 and -5.0",
             source="upstream_code", ref=f"{CFG}:101-108"),
        Fact("An episode times out when episode_length_buf >= max_episode_length - 1, and is marked died when the "
             "maximum contact-force norm over the history on a selected die body exceeds 1.0",
             source="upstream_code", ref=f"{ENV}:138-145"),
        Fact("The die body ids are arm_a_1_1, arm_a_2_1, arm_a_3_1 and arm_a_4_1",
             source="upstream_code", ref=f"{ENV}:37"),
        Fact("A full reset resets the robot and the environment buffer, clears the actions, samples the three "
             "commands uniformly from -1.0 to 1.0, and writes the default root pose, root velocity and joint state",
             source="upstream_code", ref=f"{ENV}:147-166"),
        Fact("The scene configures 200 environments with an environment spacing of 2.0",
             source="upstream_code", ref=f"{CFG}:92"),
        Fact("The contact sensor uses a history length of 5 and an update period of 0.005 s",
             source="upstream_code", ref=f"{CFG}:84-89"),
        Fact("The environment config imports SPDRBOT_CFG from isaaclab_assets.robots.spdrbot",
             source="upstream_code", ref=f"{CFG}:19"),
        Fact("The root spdrbot.py defines SPDRBOT_CFG with the USD asset path C:/spdrbot3/spdrbot3/spdr.usd",
             source="upstream_code", ref=f"{ROOT_CFG}:11-13"),
        Fact("The root SPDRBOT_CFG lists twelve Revolute joints 110 to 121 with default positions 0.0 or 0.5 and "
             "one implicit actuator group with effort_limit 5.0, velocity_limit 1, stiffness 40.0 and damping 1.0",
             source="upstream_code", ref=f"{ROOT_CFG}:34-84"),
        Fact("The README describes SPDR Bot as a four-legged robot designed for simulation in NVIDIA Isaac Sim and "
             "lists the URDF, USD assets and a sample control script", source="vendor_doc", ref=f"{README}:5"),
        Fact("The direct-project README says to install Isaac Lab first and then install this project in editable "
             "mode from source/spdrbot3", source="vendor_doc", ref=f"{PROJECT_README}:15-26"),
        Fact("The setup script declares license MIT and python_requires >=3.10",
             source="upstream_code", ref=f"{SETUP}:35-37"),
        Fact("The setup script's classifiers name Isaac Sim 4.5.0", source="upstream_code", ref=f"{SETUP}:38-42"),
        Fact("The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as "
             "dependencies", source="upstream_code", ref=f"{EXTENSION}:17-22"),
        Fact("The environment file header declares SPDX-License-Identifier BSD-3-Clause",
             source="upstream_code", ref=f"{ENV}:1-5"),
        Fact("The URDF description's LICENSE says MIT License and credits Toshinori Kitamura (2018)",
             source="vendor_doc", ref="spyderbot_minimal URDF/SpdrBot_description/LICENSE:1-3"),
        Fact("The README says the project is open for personal and educational use and suggests attribution for "
             "published work",
             source="vendor_doc", ref=f"{README}:46-48"),
    ]
    safe_state = ("the fake simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable; no stop "
                  "is sent to Isaac Sim and this package declares only the fake backend")
    #: The contract of the upstream simulator, used by the implicit ``sim`` path.  The gate exercises the
    #: package's analytic stand-in, whose F0 contract is selected by ``fidelity_by_backend`` below.  The bridge
    #: derives the engine, the determinism kind and the lockstep clock; the members below are this package's.
    fidelity = {
        "engine": "isaaclab:Template-Spdrbot3-Direct-v0 on Isaac Sim/PhysX",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "DirectRLEnv.reset(seed) seeds the upstream environment.  That path was not run, and the "
                     "fake uses Python's random.Random, so one seed does not reproduce the upstream trajectory.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream environment needs Isaac Sim 4.5, Isaac Lab, isaaclab_assets and a GPU "
            "(spdrbot3_direct_project/README.md:15-26, setup.py:38-42); it was not installed or run and no "
            "trajectory was compared with it",
            "the environment is vectorized: the default config declares 200 environments "
            "(spdrbot3_env_cfg.py:92) and step takes a (num_envs, action_dim) tensor; the SDK Gymnasium bridge "
            "drives one environment per device",
            "SPDRBOT_CFG is imported from isaaclab_assets.robots.spdrbot (spdrbot3_env_cfg.py:19), a module that "
            "is not in this clone; the root spdrbot.py defines a same-named object but is not importable at that "
            "module path, so a live deployment must supply the asset configuration",
            "the gym registration passes env_cfg_entry_point while Spdrbot3Env.__init__ requires cfg "
            "(tasks/direct/spdrbot3/__init__.py:16-24, spdrbot3_env.py:23): gymnasium.make(env_id) does not "
            "construct the environment without the caller's configuration",
            "the upstream observation_space is the external DirectRLEnv's batched policy Box while "
            "_get_observations returns a {'policy': ...} dict (spdrbot3_env.py:79-98); the fake declares the "
            "structure it actually returns",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:Spdrbot3Env fake backend (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "reset(seed) selects Python's random.Random for the three command samples; the fake is "
                         "reproducible for a seed.  The upstream uses the Isaac Lab torch RNG and its simulation "
                         "state, so one seed does not give the same trajectory on the two.",
            },
            "timestep_ms": 20.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": False,
            "gaps": [
                "analytic F0 model: the twelve joints follow the commanded position directly; there are no "
                "rigid-body dynamics, contacts, friction, actuators, sensors, noise or terrain",
                "the fake presents one environment and keeps the batched shapes of num_envs = 1; the upstream "
                "configures 200 environments (spdrbot3_env_cfg.py:92), and multi-environment control is not exposed",
                "the fake's action space is a placeholder unbounded 12-value Box: the clone states only "
                "action_space = 12 (spdrbot3_env_cfg.py:54), while the external DirectRLEnv defines the real "
                "bounds; accepting an arbitrary finite value in the fake establishes no upstream action bound",
                "the policy observation is a 48-value placeholder vector with the upstream layout: root "
                "velocities, projected gravity, joint defaults, joint velocities and the reward inputs are "
                "placeholders, and no trajectory was compared with the upstream simulator",
                "the upstream observation_space is the external DirectRLEnv's batched policy Box while "
                "_get_observations returns a {'policy': ...} dict (spdrbot3_env.py:79-98); the fake declares a Dict "
                "space so the announced space and the returned observation agree, which is an adaptation",
                "the upstream reward formula is evaluated on the fake's placeholder zero root velocities, torques "
                "and accelerations; the values are not the simulator's reward",
                "terminated is always false: the contact-force death check (spdrbot3_env.py:138-145) needs the "
                "contact sensor the fake does not model",
                "the fake starts every episode at episode_length_buf 0 and chooses a timeout of 999 steps, from "
                "episode_length_s 20.0 / (dt 1/200 * decimation 4) and the >= max_episode_length - 1 comparison "
                "(spdrbot3_env_cfg.py:51-60, spdrbot3_env.py:139); the external base's max_episode_length "
                "calculation is outside this clone and was not verified, and the upstream randomizes the "
                "buffer on a full reset (spdrbot3_env.py:152-154)",
                "the fake returns Python lists with scalar reward and termination flags instead of torch "
                "tensors; the external DirectRLEnv step lifecycle and autoreset behavior were not verified",
                "the sim backend (gymnasium.make of the registered id with Isaac Lab) was not run and the task is "
                "not declared as a sim backend; the implicit path needs the external stack and the caller's cfg",
                "snapshot and restore are not offered: the fake exposes no get_state or set_state",
                "licence declarations differ across the clone: setup.py:35 says MIT, the environment header "
                "says BSD-3-Clause, the URDF description has an MIT LICENSE, and README.md:46-48 describes "
                "personal and educational use; the card requires an owner publication decision",
            ],
        },
    }
