"""OpenMHS driver for gh.fan-ziqi/robot_lab: the Unitree G1 AMP dance environment (a Gymnasium family driver).

The card's entry symbol is ``robot_lab.tasks.direct.g1_amp.g1_amp_env:G1AmpEnv``, a concrete Isaac Lab
``DirectRLEnv`` implementation (not a template).  It is registered as ``RobotLab-Isaac-G1-AMP-Dance-Direct-v0``.
``cap.world.step.v1`` takes ``{ticks, action}`` with a 29-value action, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend and no physical e-stop path.

The upstream environment cannot be opened where the gate runs: it imports Isaac Lab and Isaac Sim, needs torch,
the motion asset and a GPU (README.md:59-73; config/extension.toml:17-22).  The ``fake`` backend is therefore the
package's own pure Python contract stand-in (fake.py), not a recording and not the upstream simulator.  A backend
name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream installation and was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The fake
models the step/reset contract, the 105-value policy observation layout, the timeout predicate on a 600-step
nominal episode counter and the
action-L2 reward term; it does not integrate the G1 rigid-body dynamics.  Every fact cites a line of the clone at
the pinned commit 500399ed75f510aeaff28705a8ce736c514dbec3.  This package is model-authored and unreviewed: it is
checked on the fake backend only and its evidence is ``contract_checked``.
"""

from mhs.driver import Fact, GymnasiumDriver

G1 = "source/robot_lab/robot_lab/tasks/direct/g1_amp"
ENV = f"{G1}/g1_amp_env.py"
CFG = f"{G1}/g1_amp_env_cfg.py"
INIT = f"{G1}/__init__.py"


class G1AmpDance(GymnasiumDriver):
    device_id = "g1-amp-dance"
    env_id = "RobotLab-Isaac-G1-AMP-Dance-Direct-v0"
    native = "robot_lab.tasks.direct.g1_amp.g1_amp_env:G1AmpEnv"
    backends = {"fake": ".fake:FakeG1AmpEnv"}
    display_name = "robot_lab Unitree G1 AMP dance (Isaac Lab simulation)"
    vendor, model = "fan-ziqi", "Unitree G1"
    mode, risk = "simulated", "R0"
    tags = ["humanoid", "unitree-g1", "amp", "motion-imitation", "isaac-lab", "isaac-sim",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("RobotLab-Isaac-G1-AMP-Dance-Direct-v0 is registered with entry point "
             "robot_lab.tasks.direct.g1_amp.g1_amp_env:G1AmpEnv and env_cfg_entry_point "
             "robot_lab.tasks.direct.g1_amp.g1_amp_env_cfg:G1AmpDanceEnvCfg", source="upstream_code",
             ref=f"{INIT}:21-29"),
        Fact("G1AmpEnv extends DirectRLEnv", source="upstream_code", ref=f"{ENV}:28"),
        Fact("G1AmpEnv defines the DirectRLEnv hooks _pre_physics_step, _apply_action, _get_observations, "
             "_get_rewards, _get_dones and _reset_idx", source="upstream_code", ref=f"{ENV}:99-253"),
        Fact("The action offset and scale are the midpoint and the width of the soft joint-position limits",
             source="upstream_code", ref=f"{ENV}:35-38"),
        Fact("Each action is written as a joint-position target: action_offset + action_scale * actions",
             source="upstream_code", ref=f"{ENV}:102-104"),
        Fact("The config declares observation_space = 71 + 3 * (8 + 5) - 6 + 1 and action_space = 29",
             source="upstream_code", ref=f"{CFG}:53-54"),
        Fact("The episode length is 10.0 s, decimation is 1 and the simulation timestep is 1/60 s",
             source="upstream_code", ref=f"{CFG}:48-50"),
        Fact("The policy observation is the dict {'policy': obs}", source="upstream_code", ref=f"{ENV}:134"),
        Fact("compute_obs concatenates joint positions, joint velocities, root height, the root quaternion tangent "
             "and normal, the key-body positions relative to the root and the episode progress",
             source="upstream_code", ref=f"{ENV}:369-382"),
        Fact("The 13 key bodies are the shoulder yaw, elbow, rubber hand, ankle roll, torso, hip yaw and knee links",
             source="upstream_code", ref=f"{ENV}:45-59"),
        Fact("The AMP observation history has num_amp_observations = 3 and amp_observation_space = "
             "71 + 3 * (8 + 5) - 6 + 1", source="upstream_code", ref=f"{CFG}:56-57"),
        Fact("The reward combines joint-position, joint-velocity, root-position and root-orientation imitation terms "
             "with the basic reward terms termination, action L2, joint-position limits, joint-acceleration L2 and "
             "joint-velocity L2", source="upstream_code", ref=f"{ENV}:159-204"),
        Fact("The basic action L2 reward is rew_action_l2 times the sum of squared actions", source="upstream_code",
             ref=f"{ENV}:400"),
        Fact("rew_action_l2 is -0.1", source="upstream_code", ref=f"{CFG}:33"),
        Fact("The episode truncates when episode_length_buf >= max_episode_length - 1", source="upstream_code",
             ref=f"{ENV}:242"),
        Fact("With early_termination enabled, the episode terminates when the reference body's world z is below "
             "termination_height", source="upstream_code", ref=f"{ENV}:243-247"),
        Fact("early_termination is True and termination_height is 0.5", source="upstream_code", ref=f"{CFG}:59-60"),
        Fact("The motion file is g1_dance1_subject2_30.npz, the reference body is the pelvis and the reset strategy "
             "is random-start", source="upstream_code", ref=f"{CFG}:62-64"),
        Fact("The config documents random-start as sampling motion at time zero", source="upstream_code",
             ref=f"{CFG}:64-71"),
        Fact("The reset writes the root pose, root velocity and joint state to the simulation", source="upstream_code",
             ref=f"{ENV}:263-265"),
        Fact("The scene is configured with num_envs=4096 and env spacing 4.0", source="upstream_code",
             ref=f"{CFG}:83"),
        Fact("SimulationCfg sets dt=dt, render_interval=decimation and physx=PhysxCfg", source="upstream_code",
             ref=f"{CFG}:73-80"),
        Fact("The robot is UNITREE_G1_29DOF_CFG at prim path /World/envs/env_.*/Robot", source="upstream_code",
             ref=f"{CFG}:86"),
        Fact("The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as "
             "dependencies", source="upstream_code", ref="source/robot_lab/config/extension.toml:17-22"),
        Fact("The setup requires psutil, colorama, xacrodoc, numpy, pandas, pinocchio and cusrl[all]; it names no "
             "serial, VISA, USB, socket or ROS client", source="upstream_code", ref="source/robot_lab/setup.py:16-28"),
        Fact("The README says running a policy in Gazebo or on a real robot is deferred to the separate rl_sar "
             "project", source="upstream_code", ref="README.md:44-45"),
        Fact("The README installs Isaac Lab first and then the extension with "
             "python -m pip install -e source/robot_lab", source="upstream_code", ref="README.md:59-73"),
        Fact("The environment source carries Apache-2.0 and BSD-3-Clause copyright notices",
             source="upstream_code", ref=f"{ENV}:1-11"),
    ]
    safe_state = ("on the fake backend the software latch refuses step, reset and seed until mhs.safety.reset; "
                  "the cached world state stays readable and releasing the latch does not advance it; "
                  "no native stop of Isaac Sim is established")
    #: The fidelity contract of the fake backend as deployed.  The fake is a contract stand-in, not a physics
    #: model, so the level is F0 and the gaps say what is not modelled.  The timestep is the config's dt (1/60 s)
    #: with decimation 1; realtime_factor 0 means ticks advance simulated time only.
    fidelity = {
        "engine": "isaaclab:RobotLab-Isaac-G1-AMP-Dance-Direct-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake resets from Python's random.Random(seed), so one seed repeats its initial state; "
                     "upstream reset samples the motion file and the Isaac Lab simulator's own random stream, "
                     "which the fake does not model",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure Python contract stand-in, not Isaac Lab/Isaac Sim: it has no rigid-body dynamics, "
            "PhysX contacts, actuators, sensors, terrain or domain randomisation; joint motion, root height and "
            "key-body offsets are placeholders",
            "the fake publishes only the 105-value policy observation group; the AMP observation history "
            "(num_amp_observations=3, 315 values) in extras['amp_obs'] and the reward log in extras['log'] are not "
            "returned",
            "the upstream reward combines four imitation terms with a basic reward; the fake models only the action "
            "L2 term (-0.1 * sum(action^2)) and returns 0.0 for zero actions",
            "the upstream reset loads g1_dance1_subject2_30.npz and writes the motion sample to the Isaac Lab "
            "simulator; the fake resets to a seeded placeholder pose without the motion file",
            "the fake's action Box (-1..1, 29 values) is a placeholder: the clone's g1_amp_env_cfg.py:54 states "
            "only action_space = 29 and the exact Box bounds are provided by Isaac Lab outside the clone, so the "
            "derived action limits carry no source",
            "the upstream environment is vectorized (num_envs=4096 in the config); the fake models one environment",
            "gymnasium, torch, Isaac Lab and Isaac Sim are not installed where the gate runs; the sim backend "
            "fallback (gymnasium.make(env_id)) was not run; only fake is declared. Live construction needs "
            "AppLauncher, registration imports, a resolved cfg and a GPU (scripts/reinforcement_learning/skrl/"
            "train.py:64-75,205); the clone does not implement the external base's lifecycle or stop semantics",
            "the single-environment fake does not validate Isaac Lab tensor batching or its automatic resets; "
            "its counter directly mirrors the >= max_episode_length - 1 predicate at 599, while the external "
            "DirectRLEnv counter-update lifecycle was not executed",
            "the early-termination path on reference-body height is modelled by a placeholder lean/height rule, not "
            "by PhysX; the fake was never compared with the upstream environment",
            "no rendering, no video recording and no exact state snapshot/restore are offered",
        ],
    }
