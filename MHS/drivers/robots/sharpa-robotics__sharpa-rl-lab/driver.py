"""OpenMHS driver for gh.sharpa-robotics/sharpa-rl-lab: the SharpaWave in-hand rotation environment.

The card's entry symbol is the concrete Gymnasium task registered as ``Isaac-Inhand-Rotate-Sharpa-Wave-v0`` at the
pinned commit: ``rl_isaaclab.tasks.inhand_rotate.sharpa_wave_env:SharpaWaveInhandRotateEnv``.  It is an Isaac Lab
``DirectRLEnv`` (``sharpa_wave_env.py:19-28``): the physics, the scene and the 16,384 parallel environments come from
Isaac Sim/Isaac Lab, which the repository installs separately (``README.md:9-13``).  This is therefore a
``GymnasiumDriver`` configuration only: the bridge serves ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment object.

The gate runs on the package's fake backend (``fake.py``): an analytic, purely kinematic stand-in that reproduces the
configured 22-D action, 192-value policy observation, reward terms, reset and truncation with one environment.  The
implicit ``sim`` fallback only calls ``gymnasium.make``; it does not provide the required ``cfg``, launch the Isaac
application or adapt the batched Torch interface. No usable live factory is declared or validated here.
The ``fidelity`` contract below describes the fake model actually deployed on this backend, level F0; its ``gaps``
name every omission, including the real simulator's batch size and the two auxiliary observation buffers.

The device is simulated (R0): no hardware backend, no native stop and no operator-required limit.  All constants and
facts cite the clone at 95ccda3d948801bb5da4cb7ffea766e03067a63b.  This package is model-authored and unreviewed
(``driver.lock.json`` ``authored_by`` is a model, ``reviewed_by`` is null).
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py"
CFG = "rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py"
REGISTRATION = "rl_isaaclab/tasks/inhand_rotate/__init__.py"


class SharpaWaveInhandRotate(GymnasiumDriver):
    device_id = "sharpa-wave-inhand-rotate"
    env_id = "Isaac-Inhand-Rotate-Sharpa-Wave-v0"
    native = "rl_isaaclab.tasks.inhand_rotate.sharpa_wave_env:SharpaWaveInhandRotateEnv"
    backends = {"fake": ".fake:FakeSharpaWaveInhandRotateEnv"}
    # No action_space_ref: the action space is built by the external DirectRLEnv base.  The fake publishes an
    # unbounded Box and applies the upstream saturation to +-clip_actions itself (sharpa_wave_env.py:178).
    display_name = "SharpaWave in-hand rotation (Isaac Lab)"
    vendor, model = "sharpa-robotics", "SharpaWave"
    tags = ["sharpa-wave", "in-hand-rotation", "dexterous-manipulation", "isaaclab", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("The environment id Isaac-Inhand-Rotate-Sharpa-Wave-v0 is registered with entry point "
             "rl_isaaclab.tasks.inhand_rotate.sharpa_wave_env:SharpaWaveInhandRotateEnv and config "
             "SharpaWaveEnvCfg", source="upstream_code", ref=f"{REGISTRATION}:9-17"),
        Fact("The environment class subclasses DirectRLEnv imported from isaaclab.envs", source="upstream_code",
             ref=f"{ENV}:19-28"),
        Fact("The task config sets episode_length_s 20.0, action_space 22 and observation_space 192",
             source="upstream_code", ref=f"{CFG}:41-43"),
        Fact("The control loop decimates 12 physics steps of dt 1/240 s per control step, 0.05 s",
             source="upstream_code", ref=f"{CFG}:49-56"),
        Fact("The config sets clip_actions to 1.0 and action_scale to 1/24", source="upstream_code",
             ref=f"{CFG}:51-52"),
        Fact("_pre_physics_step saturates actions to plus or minus cfg.clip_actions, adds cfg.action_scale times "
             "the action to prev_targets and saturates targets to the hand joint limits",
             source="upstream_code", ref=f"{ENV}:177-185"),
        Fact("The environment uses torque control", source="upstream_code", ref=f"{CFG}:53"),
        Fact("The hand joint limits are read from the articulation and multiplied by cfg.dof_limits_scale",
             source="upstream_code", ref=f"{ENV}:86-89"),
        Fact("The config sets dof_limits_scale to 0.9", source="upstream_code", ref=f"{CFG}:292"),
        Fact("The grasp cache filename combines cfg.grasp_cache_path, the two scale endpoints and the scale count",
             source="upstream_code", ref=f"{ENV}:112-115"),
        Fact("The configured grasp_cache_path is cache/sharpa_grasp_linspace", source="upstream_code",
             ref=f"{CFG}:278"),
        Fact("A reset raises RuntimeError('No saved grasping states found') when no grasp cache is loaded",
             source="upstream_code", ref=f"{ENV}:292-300"),
        Fact("The policy observation is the last three frames of a 64-value history: 22 scaled joint positions, "
             "22 joint targets, 5 contact values and 15 contact positions per frame", source="upstream_code",
             ref=f"{ENV}:421-445"),
        Fact("The config sets angvel_clip_min to -0.5, angvel_clip_max to 0.5 and rotate_reward_scale to 2.5",
             source="upstream_code", ref=f"{CFG}:269-271"),
        Fact("The total reward adds the six terms rotate_reward, object_linvel_penalty, pos_diff_penalty, "
             "torque_penalty, work_penalty and object_pos_diff, each multiplied by its configured scale",
             source="upstream_code", ref=f"{ENV}:487-493"),
        Fact("The five remaining reward scales are -0.3, -0.4, -0.1, -0.5 and 0.003", source="upstream_code",
             ref=f"{CFG}:272-276"),
        Fact("The episode truncates when episode_length_buf reaches max_episode_length - 1 and terminates when the "
             "object height leaves the reset band", source="upstream_code", ref=f"{ENV}:250-266"),
        Fact("The reset height band is 0.59906 to 0.63906 m", source="upstream_code", ref=f"{CFG}:263-264"),
        Fact("The configured scene has 16384 environments", source="upstream_code", ref=f"{CFG}:259"),
        Fact("Tactile contact observations are enabled and contact positions are disabled by default",
             source="upstream_code", ref=f"{CFG}:282-284"),
        Fact("The repository tells the user to install IsaacLab from its official guide before this package",
             source="vendor_doc", ref="README.md:9-13"),
        Fact("SharpaWaveEnvCfg subclasses DirectRLEnvCfg and is decorated with configclass",
             source="upstream_code", ref=f"{CFG}:38-39"),
        Fact("The hardware deploy environment imports SharpaWaveManager, ControlMode, ControlSource and "
             "SharpaWaveConfig from sharpa", source="upstream_code",
             ref="rl_isaaclab/tasks/inhand_rotate/sharpa_wave_deploy_env.py:18-23"),
        Fact("The hardware deploy step converts its current targets and calls hand.set_joint_position(command)",
             source="upstream_code", ref="rl_isaaclab/tasks/inhand_rotate/sharpa_wave_deploy_env.py:227-228"),
    ]
    safe_state = ("the lockstep fake is frozen once in-flight work settles; the runtime latch refuses step, reset "
                  "and seed until mhs.safety.reset clears it, and the last observation stays readable; no native "
                  "Isaac stop or stop of SharpaWaveInhandRotateDeployEnv hardware is claimed")
    #: The fidelity contract of the deployed fake (F0, kinematic/analytic).  The real simulator's contract is
    #: different (Isaac Lab rigid-body physics); it was not run and is not claimed here.
    fidelity = {
        "engine": "analytic:sharpa-wave-inhand-rotate-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) re-seeds the fake's Python random generator, and the kinematic update and reward "
                     "are deterministic, so one seed and action sequence repeats; the upstream environment draws "
                     "from torch generators and the saved grasp cache, so the two are not expected to agree",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the action space is published unbounded because the Isaac Lab base outside the clone builds it; the "
            "fake clips every action component to the upstream clip_actions 1.0 inside step "
            "(sharpa_wave_env_cfg.py:51, sharpa_wave_env.py:178), so no action-value limit is derived",
            "no dynamics: the fake is a kinematic/analytic model with no forces, contacts, friction, actuator, "
            "sensor or noise model; joint positions follow a first-order lag and the object's yaw is a proxy",
            "one environment instead of the configured 16384 (sharpa_wave_env_cfg.py:259); the action and "
            "observation spaces and returned arrays are unbatched; the policy observation is 192 values, not "
            "16384 x 192, and the fake returns scalar rewards and done flags instead of Torch batches",
            "the fake omits the upstream priv_info (8 values) and proprio_hist (30 x 64 = 1920 values) buffers and "
            "returns only the policy observation",
            "the tactile channels of the policy observation are held at zero (5 contact values and 15 contact "
            "positions) because the fake has no contact sensors",
            "reset joint positions are placeholder draws, not samples from cache/sharpa_grasp_linspace_*.npy; the "
            "upstream reset requires that cache (sharpa_wave_env.py:292-300)",
            "the fake accepts and ignores reset options; the upstream public reset is inherited from "
            "DirectRLEnv outside this clone, while the in-clone _reset_idx hook selects environment ids; no "
            "equivalence of public reset options is established",
            "the joint limits and PD gains are placeholder internal constants; upstream reads them from the USD "
            "articulation and randomizes the gains (sharpa_wave_env.py:86-95, sharpa_wave_env_cfg.py:296-300)",
            "the reward uses the upstream formula and scales but its terms come from the proxy state, so its "
            "values are not comparable with upstream training runs",
            "the fake was never compared with the upstream environment: Isaac Lab, Isaac Sim and a GPU are "
            "required (README.md:9-13 and sharpa_wave_env_cfg.py:259), and this package never imports the clone",
            "no live factory is declared: gym.make alone does not supply the mandatory cfg argument "
            "(sharpa_wave_env.py:31); upstream train.py:31-32 launches AppLauncher and :89 supplies cfg; live use "
            "also needs a batched Torch adapter, application lifecycle isolation and the grasp cache",
            "upstream construction can exit on an invalid scale/environment count (sharpa_wave_env.py:105-108) "
            "and the gravity curriculum prints to stdout (:265); neither behavior runs in the fake",
            "the fake models its own episode counter against max_episode_length - 1; external Isaac Lab "
            "automatic resets and lifecycle are not reproduced",
            "SharpaWaveInhandRotateDeployEnv is a separate real-hand environment using the external sharpa SDK "
            "and hand.set_joint_position (sharpa_wave_deploy_env.py:18-23,227-228); it is outside this R0 package",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "no wall-clock pacing: lockstep, realtime_factor 0, only commands advance the fake's time",
        ],
    }
