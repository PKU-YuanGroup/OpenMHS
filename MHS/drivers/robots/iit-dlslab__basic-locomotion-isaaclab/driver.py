"""OpenMHS driver for gh.iit-dlslab/basic-locomotion-isaaclab: the Locomotion-Go2-Flat Isaac Lab task.

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered task and the bridge derives the whole
contract from the environment spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action being the flat
``{values}`` array of the environment action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no stop path to
a machine and no operator-required limit.

The task is registered as ``Locomotion-Go2-Flat`` at
``source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/__init__.py:57-65`` with the entry point
``LocomotionEnv`` and ``Go2FlatEnvCfg``.  ``LocomotionEnv`` subclasses ``isaaclab.envs.DirectRLEnv``
(``locomotion_env.py:17`` and ``:55``), so the Gymnasium base class, the action-space object and the time-limit rule
live in the external Isaac Lab package, which this clone does not contain.  The training path needs Isaac Sim (the
script starts ``AppLauncher`` at ``scripts/rsl_rl/train.py:51``) and passes an environment configuration object to
``gym.make`` (``scripts/rsl_rl/train.py:174``); neither Isaac Sim nor Isaac Lab is installed where the acceptance gate
runs, and package code never imports or runs the clone.  The ``fake`` backend is therefore this package's pure Python
interface stand-in (see fake.py): it reproduces the action, observation, step and reset contract, not the Isaac Sim
physics.  The fidelity ``gaps`` say exactly what is not modelled.

Every Fact cites a line or a line range of the clone at the pinned commit
8bda7c7df8b223acf649e0b212635a92c8528900.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and no hardware or simulator run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

LOCOMOTION = "source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion"
ENV = f"{LOCOMOTION}/locomotion_env.py"
REGISTRATION = f"{LOCOMOTION}/__init__.py"
GO2_CFG = f"{LOCOMOTION}/go2_env_cfg.py"
PACKAGE_INIT = "source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/__init__.py"
TRAIN = "scripts/rsl_rl/train.py"


class Go2Flat(GymnasiumDriver):
    """The Locomotion-Go2-Flat velocity-tracking task of the iit-dlslab Isaac Lab repository."""

    device_id = "go2-flat"
    env_id = "Locomotion-Go2-Flat"
    native = "basic_locomotion_isaaclab.tasks.locomotion.locomotion_env:LocomotionEnv"
    backends = {"fake": ".fake:FakeGo2FlatEnv"}
    display_name = "Isaac Lab Locomotion-Go2-Flat quadruped locomotion task"
    vendor, model = "IIT-DLSLab", "Locomotion-Go2-Flat"
    tags = ["go2", "quadruped", "legged-locomotion", "isaac-lab", "isaac-sim", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("The repository is a reinforcement-learning implementation of quadruped locomotion in IsaacLab with "
             "sim-to-sim and sim-to-real scripts", source="vendor_doc", ref="README.md:14"),
        Fact("The README lists Aliengo, Go2, B2, A2 and HyQReal2 and flat and rough locomotion environment name "
             "patterns", source="vendor_doc", ref="README.md:37-39"),
        Fact("Training requires Isaac Lab to be installed first and installs the library with "
             "pip install -e source/basic_locomotion_isaaclab", source="vendor_doc", ref="README_train.md:3-16"),
        Fact("Locomotion-Go2-Flat is registered with entry point LocomotionEnv and the Go2FlatEnvCfg environment "
             "configuration", source="upstream_code", ref=f"{REGISTRATION}:57-65"),
        Fact("The package top-level __init__ imports .tasks, which runs the gym.register calls", source="upstream_code",
             ref=f"{PACKAGE_INIT}:5-6"),
        Fact("LocomotionEnv subclasses DirectRLEnv imported from isaaclab.envs, so the Gymnasium base and its "
             "spaces live in the external Isaac Lab package", source="upstream_code", ref=f"{ENV}:17"),
        Fact("LocomotionEnv is the registered entry class", source="upstream_code", ref=f"{ENV}:55"),
        Fact("LocomotionEnv takes the environment configuration cfg, an optional render_mode and extra keyword "
             "arguments", source="upstream_code", ref=f"{ENV}:57"),
        Fact("Go2FlatEnvCfg sets episode_length_s 20.0, decimation 4, action_scale 0.5 and action_space 12",
             source="upstream_code", ref=f"{GO2_CFG}:167-172"),
        Fact("A Go2-Flat observation frame is 52 values: 3 base linear velocity, 3 base angular velocity, 3 projected "
             "gravity, 3 command, 12 joint positions, 12 joint velocities, 12 last actions and 4 clock values",
             source="upstream_code", ref=f"{GO2_CFG}:173-183"),
        Fact("The observation history keeps 5 frames and observation_space is multiplied by history_length, so the "
             "policy observation is 260 values", source="upstream_code", ref=f"{GO2_CFG}:185-191"),
        Fact("SimulationCfg sets dt to 1/200 s and render_interval to decimation", source="upstream_code",
             ref=f"{GO2_CFG}:307-309"),
        Fact("Go2FlatEnvCfg creates 4096 parallel environments", source="upstream_code", ref=f"{GO2_CFG}:337"),
        Fact("desired_clip_actions is 3.0 and use_filter_actions is True", source="upstream_code",
             ref=f"{GO2_CFG}:387-389"),
        Fact("Before the action is applied, _pre_physics_step clamps it to +/- desired_clip_actions, filters it with "
             "alpha 0.8 and scales it by action_scale", source="upstream_code", ref=f"{ENV}:316-331"),
        Fact("The standard observation concatenates base linear velocity, base angular velocity, projected gravity, "
             "commands, joint position deviation, joint velocity, last actions and clock values in that order",
             source="upstream_code", ref=f"{ENV}:399-416"),
        Fact("The observation history appends the newest frame last and flattens the frames into one vector",
             source="upstream_code", ref=f"{ENV}:417-420"),
        Fact("LocomotionEnv returns the observations as a dict with common, critic and policy groups; policy is the "
             "standard observation", source="upstream_code", ref=f"{ENV}:423-455"),
        Fact("The episode times out when episode_length_buf reaches max_episode_length - 1 and terminates on a base "
             "or hip contact force above 1.0", source="upstream_code", ref=f"{ENV}:571-577"),
        Fact("A reset perturbs joint positions uniformly within +/-0.2 of the default and draws a random yaw",
             source="upstream_code", ref=f"{ENV}:652-658"),
        Fact("The training script launches the Isaac Sim application with AppLauncher", source="upstream_code",
             ref=f"{TRAIN}:51"),
        Fact("The training script creates the environment with gym.make(task, cfg=env_cfg), so the task needs an "
             "environment configuration object", source="upstream_code", ref=f"{TRAIN}:174"),
        Fact("Real-robot control matches the external unitree-ros2-dls ROS 2 repository; hardware transport is not "
             "part of this clone", source="vendor_doc", ref="README_deploy.md:50"),
        Fact("The repository licence is BSD-3-Clause", source="vendor_doc", ref="LICENSE:1"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The contract of the model this package serves on the fake backend (spec 05-fidelity).  The upstream task is an
    #: Isaac Sim rigid-body simulation, but this package ships no sim backend and the fake models no dynamics, so the
    #: level is F0 and the gaps carry every omission.  The timestep is the task's control step: decimation 4 times
    #: sim.dt 1/200 s is 20 ms (go2_env_cfg.py:170 and :307-309).
    fidelity = {
        "engine": "mhs-fake:Locomotion-Go2-Flat",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) and cap.world.seed.v1 set the seed of the next reset. The fake's reduced state "
                     "is fully deterministic and its fixed observation does not depend on the seed; the upstream "
                     "reset's uniform joint-position noise and random yaw (locomotion_env.py:652-658) are not "
                     "modelled, and the upstream Isaac Sim environment was not run, so its own determinism is not "
                     "claimed.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an interface stand-in: it models no rigid-body dynamics, contacts, actuator, sensor or "
            "noise model, and no command, reward or height scan; the upstream task runs Isaac Sim and Isaac Lab "
            "(README_train.md:3), which this package does not install or run, and no simulator run is claimed",
            "the fake serves one environment with a 12-value action and a 260-value policy observation, while the "
            "upstream Go2FlatEnvCfg batches 4096 environments (go2_env_cfg.py:337) and LocomotionEnv returns a dict "
            "of common, critic and policy observation groups (locomotion_env.py:423-455); only a flat policy-sized "
            "Box is represented, and the critic group is not represented",
            "the fake's 260-value observation follows the 52-value frame order of go2_env_cfg.py:173-183 and the "
            "5-frame history of :185-191, but every value except the last-action tail of the newest frame is a "
            "fixed placeholder; no robot pose, command, clock, contact or reward is simulated",
            "the fake never terminates or truncates: the episode time limit and the contact-based termination of "
            "locomotion_env.py:571-577 are not modelled (the time-limit rule itself lives in the external "
            "DirectRLEnv, which the clone does not contain)",
            "the action space of the upstream environment is created by the external DirectRLEnv and was not "
            "inspected; the fake exposes an unbounded Box of 12 values and does not reject or clamp, while the "
            "clone's own _pre_physics_step clamps to +/-3.0 (locomotion_env.py:322-323 and go2_env_cfg.py:388)",
            "no snapshot or restore: the environment exposes no get_state/set_state and the fake offers none",
            "only the fake backend is declared; opening the registered task through gymnasium.make needs Isaac Sim, "
            "Isaac Lab and an environment configuration object (scripts/rsl_rl/train.py:51 and :174), and was not "
            "run",
        ],
    }
