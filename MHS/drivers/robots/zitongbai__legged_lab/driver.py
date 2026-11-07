"""OpenMHS driver for gh.zitongbai/legged_lab: the Unitree G1 AMP locomotion task (a Gymnasium family driver).

The clone registers ``LeggedLab-Isaac-AMP-G1-v0`` with ``gymnasium.register``, and the entry point is
``legged_lab.envs:ManagerBasedAmpEnv`` (tasks/locomotion/amp/config/g1/__init__.py:7-15).  This driver is the
family-config member of that environment: ``GymnasiumDriver`` derives ``cap.world.step.v1`` (``{ticks, action}``)
from the environment's action space, ``cap.world.reset.v1`` from ``{seed, options}`` and ``cap.world.seed.v1`` from
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The environment is a vectorised Isaac Lab task: ``ManagerBasedAmpEnv`` subclasses ``ManagerBasedAnimationEnv``
(manager_based_amp_env.py:21), which subclasses Isaac Lab's ``ManagerBasedRLEnv`` (manager_based_animation_env.py:6
and :13) and calls ``self._configure_gym_env_spaces()`` after building the managers (manager_based_amp_env.py:100).
The action space therefore comes from the configured action term and the observation space from the observation
groups; both are built by Isaac Lab, outside the clone.  The configured action is a joint-position target for every
G1 joint with scale 0.25 and ``use_default_offset=True`` (amp_env_cfg.py:92), and the policy group concatenates six
terms with a five-step history (amp_env_cfg.py:113-129).

The gate cannot install or import Isaac Sim 5.1.0, Isaac Lab 2.3.2, the forked rsl_rl, Git LFS motion data, torch or
a GPU (README.md:3-4, :64, :83-89 and :98-107), so the ``fake`` backend is this package's own pure Python kinematic
stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream installation and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule in the facts and the fidelity gaps cites a line of the clone at the pinned commit
69b7f73d912a9d5695a60b5bed41d0785c8b302e.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

G1_INIT = "source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/__init__.py"
G1_CFG = "source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/g1_amp_env_cfg.py"
AMP_CFG = "source/legged_lab/legged_lab/tasks/locomotion/amp/amp_env_cfg.py"
AMP_ENV = "source/legged_lab/legged_lab/envs/manager_based_amp_env.py"
ANIM_ENV = "source/legged_lab/legged_lab/envs/manager_based_animation_env.py"
OBS = "source/legged_lab/legged_lab/tasks/locomotion/amp/mdp/observations.py"
ASSET = "source/legged_lab/legged_lab/assets/unitree.py"
EXTENSION = "source/legged_lab/config/extension.toml"


class LeggedLabAmpG1(GymnasiumDriver):
    device_id = "legged-lab-amp-g1"
    env_id = "LeggedLab-Isaac-AMP-G1-v0"
    native = "legged_lab.envs:ManagerBasedAmpEnv"
    backends = {"fake": ".fake:FakeLeggedLabAmpEnv"}
    mode = "simulated"
    risk = "R0"
    display_name = "Unitree G1 AMP locomotion in Isaac Lab (legged_lab)"
    vendor, model = "zitongbai", "legged_lab"
    tags = ["unitree", "g1", "humanoid", "locomotion", "amp", "motion-imitation", "isaac-sim", "isaac-lab",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The repository is an extension for legged-robot reinforcement learning based on Isaac Lab",
             source="vendor_doc", ref="README.md:29"),
        Fact("The README badge lists Isaac Sim 5.1.0 and Isaac Lab 2.3.2", source="vendor_doc",
             ref="README.md:3-4"),
        Fact("Isaac Lab v2.3.2 must be installed before this package", source="vendor_doc", ref="README.md:64"),
        Fact("Git LFS is required, and git lfs install followed by git lfs pull downloads the USD models and motion "
             "data", source="vendor_doc", ref="README.md:83-89"),
        Fact("The package is installed with python -m pip install -e source/legged_lab", source="vendor_doc",
             ref="README.md:95"),
        Fact("Training uses a customized rsl_rl cloned from the feature/amp branch", source="vendor_doc",
             ref="README.md:98-107"),
        Fact("The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as "
             "dependencies", source="upstream_code", ref=f"{EXTENSION}:17-22"),
        Fact("LeggedLab-Isaac-AMP-G1-v0 is registered with gymnasium.register and its entry point is "
             "legged_lab.envs:ManagerBasedAmpEnv", source="upstream_code", ref=f"{G1_INIT}:7-15"),
        Fact("LeggedLab-Isaac-AMP-G1-Play-v0 is registered with the same entry point and the play configuration",
             source="upstream_code", ref=f"{G1_INIT}:17-25"),
        Fact("ManagerBasedAmpEnv subclasses ManagerBasedAnimationEnv", source="upstream_code", ref=f"{AMP_ENV}:21"),
        Fact("ManagerBasedAnimationEnv subclasses Isaac Lab's ManagerBasedRLEnv, imported from isaaclab.envs",
             source="upstream_code", ref=f"{ANIM_ENV}:6"),
        Fact("ManagerBasedAmpEnv.load_managers builds the managers and then calls self._configure_gym_env_spaces()",
             source="upstream_code", ref=f"{AMP_ENV}:75-100"),
        Fact("ManagerBasedAmpEnv.step takes an action of shape (num_envs, action_dim) and returns observations, "
             "rewards, terminated, truncated and extras", source="upstream_code", ref=f"{AMP_ENV}:105-208"),
        Fact("The action term is a JointPositionAction over every joint (joint_names ['.*']) with scale 0.25 and "
             "use_default_offset=True", source="upstream_code", ref=f"{AMP_CFG}:92"),
        Fact("The policy observation group concatenates base_ang_vel, root_local_rot_tan_norm, velocity_commands, "
             "joint_pos, joint_vel and actions, with history_length 5, corruption enabled and terms concatenated",
             source="upstream_code", ref=f"{AMP_CFG}:113-129"),
        Fact("root_local_rot_tan_norm returns the tangent and normal vectors of the local rotation matrix, six "
             "values in total", source="upstream_code", ref=f"{OBS}:25-29"),
        Fact("The decimation is 4, the episode length is 20.0 s and the simulation timestep is 0.005 s",
             source="upstream_code", ref=f"{AMP_CFG}:394-397"),
        Fact("The termination terms are a time-out, an illegal contact, a base height below 0.2 m and a bad "
             "orientation above 60 degrees", source="upstream_code", ref=f"{AMP_CFG}:313-323"),
        Fact("G1AmpEnvCfg disables the base_contact termination", source="upstream_code", ref=f"{G1_CFG}:223"),
        Fact("G1AmpEnvCfg replaces the scene robot with UNITREE_G1_29DOF_CFG", source="upstream_code",
             ref=f"{G1_CFG}:117"),
        Fact("The G1 asset lists 29 joint_sdk_names, from left_hip_pitch_joint to right_wrist_yaw_joint",
             source="upstream_code", ref=f"{ASSET}:167-197"),
        Fact("The G1 initial joint positions set the hip pitch to -0.1, the knee to 0.3, the ankle pitch to -0.2, "
             "the shoulder pitch to 0.3, the shoulder roll to +-0.25, the elbow to 0.97 and the wrist roll to "
             "+-0.15", source="upstream_code", ref=f"{ASSET}:94-105"),
        Fact("The G1 AMP command ranges are -0.5 to 3.0 for lin_vel_x, -0.5 to 0.5 for lin_vel_y, -1.0 to 1.0 for "
             "ang_vel_z and -pi to pi for heading", source="upstream_code", ref=f"{G1_CFG}:209-212"),
        Fact("The G1 AMP reset event samples the reference animation with a height offset of 0.1",
             source="upstream_code", ref=f"{G1_CFG}:200"),
        Fact("The animation term enables random_initialize and random_fetch, so a reset draws a random reference "
             "motion", source="upstream_code", ref=f"{AMP_CFG}:359-361"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The gate serves the package's
    #: pure-Python fake, not Isaac Sim, so the claim is kinematic (F0) and makes no determinism claim about the
    #: upstream simulator.
    fidelity = {
        "engine": "gymnasium:LeggedLab-Isaac-AMP-G1-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random from reset(seed), so one seed repeats the fake's own "
                     "trajectory; Isaac Lab draws from numpy/torch generators and its seeding was not observed, so "
                     "the same seed is not claimed to reproduce an Isaac Sim trajectory",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in (F0): no rigid-body dynamics, contacts, friction, actuators, sensors, "
            "terrain, motion data or rendering; the joint positions are a direct mapping of the scaled action and "
            "were never compared with an Isaac Sim run",
            "the action space is published as an unbounded 29-value Box because the clone configures a "
            "joint-position action over every joint and states no numeric action bound (amp_env_cfg.py:92); the "
            "29-value joint count comes from the G1 asset's joint_sdk_names list (unitree.py:167-197), and the "
            "real total_action_dim and the Isaac Lab Box bounds were not observed",
            "the fake publishes only the 29 joint positions in a single observation group named policy, while the "
            "configured policy group concatenates base_ang_vel, root_local_rot_tan_norm, velocity_commands, "
            "joint_pos, joint_vel and actions with a five-step history (amp_env_cfg.py:113-129); the real "
            "flattened width is computed by Isaac Lab outside the clone and was not observed",
            "only the 20.0 s time-out is modelled; the base_height below 0.2 m and bad_orientation above 60 degree "
            "terminations (amp_env_cfg.py:313-323) need physics and are not modelled, and base_contact is disabled "
            "for G1 (g1_amp_env_cfg.py:223)",
            "the reward is a constant placeholder, not the sum of the configured reward terms, because those terms "
            "are external Isaac Lab MDP functions",
            "the fake applies the action as a joint-position offset with scale 0.25 on top of the asset's "
            "configured default positions (amp_env_cfg.py:92, unitree.py:94-105); the joint order is assumed to "
            "follow joint_sdk_names and actuator dynamics and effort limits are not modelled",
            "the upstream reset event reset_from_ref samples a reference motion (g1_amp_env_cfg.py:200, "
            "amp_env_cfg.py:359-361); the fake instead draws small joint offsets from Python's random.Random, so "
            "a seed does not reproduce an Isaac Sim episode",
            "the sim backend (gymnasium.make('LeggedLab-Isaac-AMP-G1-v0')) was not run: it needs Isaac Sim 5.1.0, "
            "Isaac Lab 2.3.2, Git LFS assets, the forked rsl_rl and a GPU (README.md:3-4, :64, :83-89, :98-107)",
            "the fake returns Python floats and lists rather than torch tensors on a GPU and has no wall-clock "
            "pacing: realtime_factor 0 and one tick advances simulated time by 20 ms only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair in the "
            "clone",
        ],
    }
