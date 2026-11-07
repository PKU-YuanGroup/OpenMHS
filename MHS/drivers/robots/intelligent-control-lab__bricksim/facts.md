# Facts and tags for gh.intelligent-control-lab/bricksim

Every fact cites its source at commit `cbd5de3238e6ac12f44ef699e1507a9f16bdafc3`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The assemble-brick package registers Lego-AssembleBrick-v0 with entry point isaaclab.envs:ManagerBasedRLEnv and env_cfg_entry_point <this package>.env:AssembleBrickEnvCfg | upstream_code | python/bricksim/envs/assemble_brick/__init__.py:7-14 |
| The same package registers Lego-AssembleBrick-RGB-v0 and Lego-AssembleBrick-RGBD-v0 with the RGB and RGB-D configuration classes | upstream_code | python/bricksim/envs/assemble_brick/__init__.py:16-32 |
| The Python package requires Python 3.11 or newer and depends on gymnasium 1.2.0 | upstream_code | python/pyproject.toml:5-8 |
| The isaacsim and isaaclab optional extras pin isaacsim[all,extscache]==5.1.0 and isaaclab==2.3.2.post1 | upstream_code | python/pyproject.toml:17-19 |
| BrickSim requires an x86-64 Linux platform and an NVIDIA driver compatible with Isaac Sim | vendor_doc | README.md:32-37 |
| AssembleBrickBaseEnvCfg extends isaaclab.envs.ManagerBasedRLEnvCfg | upstream_code | python/bricksim/envs/assemble_brick/env.py:468-469 |
| The scene runs one environment instance with an environment spacing of 5.0 | upstream_code | python/bricksim/envs/assemble_brick/env.py:472 |
| Each control step applies 6 simulation steps of 1/60 s and an episode is 12.0 s long | upstream_code | python/bricksim/envs/assemble_brick/env.py:492-494 |
| AssembleBrickEnvCfg removes the hand, front and side cameras and the image observation group, so the state-based environment returns no images | upstream_code | python/bricksim/envs/assemble_brick/env.py:506-516 |
| The arm action is a differential inverse-kinematics relative pose command | upstream_code | python/bricksim/envs/assemble_brick/env.py:278-290 |
| The arm action is scaled per axis by (0.2, 0.2, 0.2, 1.0, 1.0, 1.0) | upstream_code | python/bricksim/envs/assemble_brick/env.py:90 |
| The gripper action opens the fingers to 0.04 m above the 0.2 threshold and closes them to 0.0 m below the -0.2 threshold | upstream_code | python/bricksim/envs/assemble_brick/env.py:292-300 |
| The ActionsCfg docstring tells callers to send finite actions in [-1, 1] | upstream_code | python/bricksim/envs/assemble_brick/env.py:274 |
| The policy observation group is end-effector pose, gripper width, gripper speed, brick pose and target pose | upstream_code | python/bricksim/envs/assemble_brick/env.py:323-332 |
| The privileged observation group adds brick_grasped, connection_created and brick_dimensions and sets concatenate_terms to False | upstream_code | python/bricksim/envs/assemble_brick/env.py:334-342 |
| The termination terms are a timeout, a formed target connection with the gripper open, a non-target connection and a brick dropped below its height threshold | upstream_code | python/bricksim/envs/assemble_brick/env.py:458-465 |
| A reset applies a Gaussian joint offset with mean 0.0 and standard deviation 0.02 | upstream_code | python/bricksim/envs/assemble_brick/env.py:417-425 |
| A reset places the brick uniformly over x 0.36 to 0.56 m, y 0.16 to 0.32 m and yaw 0 to 2*pi | upstream_code | python/bricksim/envs/assemble_brick/env.py:427-439 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(7)` over [-1, 1]: `action.values` per element, with no source and the ref
`action_space of the fake backend .fake:FakeAssembleBrickEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:Lego-AssembleBrick-v0`, level F1, determinism
`seeded` with `seed_control` `parameter`, timestep 100 ms (6 decimations of 1/60 s, `env.py:492-494`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled: Isaac
Sim's physics is external, the RGB/RGB-D variants are not served, the fake is kinematic, and this package was never
run against Isaac Sim or Isaac Lab.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: brick-assembly, gymnasium, isaac-lab, isaac-sim, lego, manipulation, reinforcement-learning, simulation
