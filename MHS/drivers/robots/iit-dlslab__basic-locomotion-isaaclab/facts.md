# Facts and tags for gh.iit-dlslab/basic-locomotion-isaaclab

Every fact cites its source at commit `8bda7c7df8b223acf649e0b212635a92c8528900`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a reinforcement-learning implementation of quadruped locomotion in IsaacLab with sim-to-sim and sim-to-real scripts | vendor_doc | README.md:14 |
| The README lists Aliengo, Go2, B2, A2 and HyQReal2 and flat and rough locomotion environment name patterns | vendor_doc | README.md:37-39 |
| Training requires Isaac Lab to be installed first and installs the library with pip install -e source/basic_locomotion_isaaclab | vendor_doc | README_train.md:3-16 |
| Locomotion-Go2-Flat is registered with entry point LocomotionEnv and the Go2FlatEnvCfg environment configuration | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/__init__.py:57-65 |
| The package top-level __init__ imports .tasks, which runs the gym.register calls | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/__init__.py:5-6 |
| LocomotionEnv subclasses DirectRLEnv imported from isaaclab.envs, so the Gymnasium base and its spaces live in the external Isaac Lab package | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:17 |
| LocomotionEnv is the registered entry class | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:55 |
| LocomotionEnv takes the environment configuration cfg, an optional render_mode and extra keyword arguments | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:57 |
| Go2FlatEnvCfg sets episode_length_s 20.0, decimation 4, action_scale 0.5 and action_space 12 | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/go2_env_cfg.py:167-172 |
| A Go2-Flat observation frame is 52 values: 3 base linear velocity, 3 base angular velocity, 3 projected gravity, 3 command, 12 joint positions, 12 joint velocities, 12 last actions and 4 clock values | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/go2_env_cfg.py:173-183 |
| The observation history keeps 5 frames and observation_space is multiplied by history_length, so the policy observation is 260 values | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/go2_env_cfg.py:185-191 |
| SimulationCfg sets dt to 1/200 s and render_interval to decimation | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/go2_env_cfg.py:307-309 |
| Go2FlatEnvCfg creates 4096 parallel environments | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/go2_env_cfg.py:337 |
| desired_clip_actions is 3.0 and use_filter_actions is True | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/go2_env_cfg.py:387-389 |
| Before the action is applied, _pre_physics_step clamps it to +/- desired_clip_actions, filters it with alpha 0.8 and scales it by action_scale | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:316-331 |
| The standard observation concatenates base linear velocity, base angular velocity, projected gravity, commands, joint position deviation, joint velocity, last actions and clock values in that order | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:399-416 |
| The observation history appends the newest frame last and flattens the frames into one vector | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:417-420 |
| LocomotionEnv returns the observations as a dict with common, critic and policy groups; policy is the standard observation | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:423-455 |
| The episode times out when episode_length_buf reaches max_episode_length - 1 and terminates on a base or hip contact force above 1.0 | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:571-577 |
| A reset perturbs joint positions uniformly within +/-0.2 of the default and draws a random yaw | upstream_code | source/basic_locomotion_isaaclab/basic_locomotion_isaaclab/tasks/locomotion/locomotion_env.py:652-658 |
| The training script launches the Isaac Sim application with AppLauncher | upstream_code | scripts/rsl_rl/train.py:51 |
| The training script creates the environment with gym.make(task, cfg=env_cfg), so the task needs an environment configuration object | upstream_code | scripts/rsl_rl/train.py:174 |
| Real-robot control matches the external unitree-ros2-dls ROS 2 repository; hardware transport is not part of this clone | vendor_doc | README_deploy.md:50 |
| The repository licence is BSD-3-Clause | vendor_doc | LICENSE:1 |

Limits: the driver declares none. The only bound would be the environment's action space, which the bridge derives
from the environment; the real object is created by the external Isaac Lab `DirectRLEnv`, which this clone does not
contain, and the fake exposes an unbounded Box of 12 values rather than invent an envelope. The clone's own
`_pre_physics_step` clamps an action to +/-3.0 (`locomotion_env.py:322-323`, `go2_env_cfg.py:388`), but that is a clamp
inside the environment, not a rejection by an action-space object, so it is not published as a limit. `ticks` (1 to
`max_ticks`, 10000 by default) comes from the bridge. The device is simulated (R0), so no limit is
`operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mhs-fake:Locomotion-Go2-Flat`, level F0 (interface
stand-in, no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (decimation 4 times
sim.dt 1/200 s, `go2_env_cfg.py:170` and `:307-309`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps say what is not modelled: physics, contacts, actuator, sensor, noise, reward, the 4096
environment batch, the `common`/`critic`/`policy` observation groups, the episode time limit and the contact-based
termination, and the external action-space object.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: go2, quadruped, legged-locomotion, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium
