# Facts and tags for gh.abizovnuralem/go2_omniverse

Every fact cites its source at commit `db18970d66fa77a68bf0976b0f7c183825cd2292`: `vendor_doc` (a text file of the
clone such as README.md or JAZZY.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream script defaults the Gymnasium task to Isaac-Velocity-Rough-Unitree-Go2-v0 | upstream_code | omniverse_sim.py:19 |
| The script creates the environment with gym.make(args_cli.task, cfg=env_cfg) after the Isaac Sim application has started | upstream_code | omniverse_sim.py:384 |
| AppLauncher(args_cli) starts the Isaac Sim application before the environment is created | upstream_code | omniverse_sim.py:50-51 |
| UnitreeGo2CustomEnvCfg extends LocomotionVelocityRoughEnvCfg | upstream_code | custom_rl_env.py:321 |
| UnitreeGo2CustomEnvCfg replaces the scene robot with UNITREE_GO2_CFG | upstream_code | custom_rl_env.py:326 |
| The action term is a JointPositionAction over every joint with use_default_offset=True and a scale of 0.5 in the base configuration | upstream_code | custom_rl_env.py:195 |
| UnitreeGo2CustomEnvCfg reduces the joint-position action scale to 0.25 | upstream_code | custom_rl_env.py:330 |
| The physics timestep is 0.005 s and the policy action is applied every 4 physics steps | upstream_code | custom_rl_env.py:296-300 |
| The episode length is 20.0 s | upstream_code | custom_rl_env.py:298 |
| The policy observation concatenates base linear velocity, base angular velocity, projected gravity, velocity commands, joint positions, joint velocities, last actions and a height scan, in that order | upstream_code | custom_rl_env.py:167-186 |
| The height scan is clipped to (-1.0, 1.0) | upstream_code | custom_rl_env.py:181 |
| Projected gravity is corrupted with uniform noise in (-0.05, 0.05) | upstream_code | custom_rl_env.py:172 |
| The height scanner samples a grid with 0.1 m resolution over a 1.6 m by 1.0 m extent | upstream_code | custom_rl_env.py:118-119 |
| The velocity command ranges are all zero: lin_vel_x, lin_vel_y, ang_vel_z and heading are (0, 0) | upstream_code | custom_rl_env.py:209-211 |
| The termination terms are a time-out and an illegal contact of the base body above a threshold of 1.0 | upstream_code | custom_rl_env.py:254-257 |
| The policy reads the observation group named policy | upstream_code | omniverse_sim.py:407 |
| The main loop advances the environment with the policy actions | upstream_code | omniverse_sim.py:454 |
| The environment base class is imported from isaaclab.envs, outside the clone | upstream_code | custom_rl_env.py:32 |
| Isaac Sim 5.0 and Isaac Lab 0.54.3 are installed into a separate Python 3.11 virtual environment | vendor_doc | JAZZY.md:61-69 |
| The twinbot mode drives the simulated Go2's joints from the physical robot's /lowstate stream; the simulation mirrors the real state rather than commanding it | vendor_doc | README.md:29-37 |

Limits: the driver declares none. The action space is the manager-based Isaac Lab joint-position Box; the clone states
the action term and its scale (`custom_rl_env.py:195`, `:330`) but no numeric action bound, so the fake publishes an
unbounded Box rather than inventing one. `ticks` is bounded by the bridge (1 to `max_ticks`, 10000 by default), and the
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:Isaac-Velocity-Rough-Unitree-Go2-v0`, level F0
(the checked fake is kinematic; the Isaac Lab engine is F1 but was not run), determinism `seeded` with `seed_control`
`parameter`, timestep 20 ms (4 x 0.005 s, `custom_rl_env.py:296-300`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled, including the illegal-contact termination and that
the fake was not compared with Isaac Sim.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
observation stays readable. The upstream twinbot mode mirrors a physical Go2 into the simulation but this driver serves
the simulation only and never commands the real robot.

Tags: unitree, go2, quadruped, locomotion, isaac-sim, isaac-lab, reinforcement-learning, simulation, gymnasium
