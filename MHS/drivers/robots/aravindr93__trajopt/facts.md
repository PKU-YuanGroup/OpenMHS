# Facts and tags for gh.aravindr93/trajopt

Every fact cites its source at commit `23fbc453af2e980788348e5bde18136ad52378f0`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README describes the package as trajectory optimization algorithms for continuous-control tasks simulated with MuJoCo | vendor_doc | README.md:2 |
| The README names MuJoCo and mjrl as the main dependencies and says mujoco_py must be installed before the package is used | vendor_doc | README.md:5-7 |
| The concrete environment class Reacher7DOFEnv extends mjrl's MujocoEnv and gym's EzPickle | upstream_code | trajopt/envs/reacher_env.py:8 |
| The constructor passes the model path curr_dir+'/assets/sawyer.xml' and the number 2 to MujocoEnv.__init__ | upstream_code | trajopt/envs/reacher_env.py:20-21 |
| The environment declares observation_dim 26 and action_dim 7 | upstream_code | trajopt/envs/reacher_env.py:23-24 |
| get_obs concatenates qpos, qvel, the finger site position and the finger-minus-target site difference | upstream_code | trajopt/envs/reacher_env.py:41-47 |
| step calls do_simulation(a, frame_skip), computes the reward -l1_dist - 5.0*l2_dist from the finger and target site positions, and returns False as done | upstream_code | trajopt/envs/reacher_env.py:29-39 |
| The target reset draws the target site position uniformly from x -0.3..0.3, y -0.2..0.2 and z -0.25..0.25 | upstream_code | trajopt/envs/reacher_env.py:56-62 |
| reset_model resets the robot and the target and returns get_obs | upstream_code | trajopt/envs/reacher_env.py:64-71 |
| The registration comment says max_episode_steps is not used internally in trajopt; trajopt_reacher-v0 is registered with 75 and trajopt_continual_reacher-v0 with 250 | upstream_code | trajopt/envs/__init__.py:6-19 |
| The reacher_env module imports gym.utils, mjrl.envs.mujoco_env and mujoco_py.MjViewer | upstream_code | trajopt/envs/reacher_env.py:1-4 |
| setup.py's install_requires lists click, gym, mujoco_py, termcolor, tqdm and numpy, but not mjrl | upstream_code | setup.py:20-27 |
| The MJCF model is named '7dof reacher', compiles angles in radians and local coordinates, and resolves inertia from the geoms | upstream_code | trajopt/envs/assets/sawyer.xml:1-2 |
| The model option sets timestep 0.01 s, gravity 0 0 0 and the Euler integrator | upstream_code | trajopt/envs/assets/sawyer.xml:3 |
| The default joint class sets armature 0.004, damping 0.8 and limited true | upstream_code | trajopt/envs/assets/sawyer.xml:5 |
| The model has seven hinge joints with ranges: r_shoulder_pan -2.2854..1.714602, r_shoulder_lift -0.5236..1.3963, r_upper_arm_roll -1.5..1.7, r_elbow_flex -2.3213..0, r_forearm_roll -1.5..1.5, r_wrist_flex -1.094..0 and r_wrist_roll -1.5..1.5, all in radians | upstream_code | trajopt/envs/assets/sawyer.xml:2-50 |
| The actuator block declares seven motor actuators, one per hinge joint, each with ctrllimited true and ctrlrange -1.0..1.0; the shoulder-pan gear is 20 and the other six are 10 | upstream_code | trajopt/envs/assets/sawyer.xml:101-109 |
| The model declares a target site at position 0.1 0.1 0.1 and a finger site on the wrist-roll body | upstream_code | trajopt/envs/assets/sawyer.xml:13-59 |
| The repository LICENSE is the MIT License, copyright 2018 Aravind Rajeswaran | vendor_doc | LICENSE:1-3 |

Limits: the driver declares none. The only action bound is the model's per-actuator control range, which the bridge
derives from `actuator_ctrlrange` (source `upstream_code`, ref `trajopt/envs/assets/sawyer.xml:actuator_ctrlrange`).
All seven motors state a range, so no control path is `operator_required` and no `site-limits.example.json` is
needed. `ticks` is the bridge's bounded step count (1 to `max_ticks`), not a device bound.

Fidelity contract (`driver.py`): engine `mujoco:7dof reacher`, level F1 for the real engine path, determinism `none`
(MuJoCo reset has no seed), timestep 10 ms (`sawyer.xml:3`), `realtime_factor` 0, clock `lockstep`, reset `full`,
snapshot and restore available. The fake backend publishes F0, engine
`analytic:stand-in mujoco module (no physics)`, because MuJoCo is not installed and `fake.py` integrates a placeholder
torque model; its gaps say what is not modelled. The real F1 path was not run.

Safety: simulated R0 device (isolated simulation stepping, MHS-004 SAFE-006). The e-stop is the runtime's software
latch; after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.
No hardware backend exists and no hardware run is claimed.

Tags: trajopt, reacher, mujoco, mjcf, simulation, robot-arm, reinforcement-learning
