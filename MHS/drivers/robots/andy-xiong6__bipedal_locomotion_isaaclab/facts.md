# Facts and tags for gh.andy-xiong6/bipedal_locomotion_isaaclab

The package serves the pointfoot blind-flat Isaac Lab task. The card lists two environment-configuration classes as
entry symbols; this driver uses `PFBlindFlatEnvCfg` and the registered task `Isaac-PF-Blind-Flat-v0`
(`exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/robots/__init__.py:64-71`). The registered entry point
itself is the external `omni.isaac.lab.envs:ManagerBasedRLEnv`, so `native` names the configuration class the card
confirmed and the fake implements the Gymnasium environment interface. The wheelfoot task and the other flat, rough
and stair task registrations are not served by this package.

Every fact cites its source at commit `748f879e099aaa3d3d19437a7eed48c9a72b1e28`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The reference file is generated from
`driver.py`, not from this page.

| fact | source | ref |
|---|---|---|
| This repository is used to train and simulate bipedal robots such as the limxdynamics TRON1 | vendor_doc | README.md:17 |
| The project targets Isaac Sim 4.2.0 and Isaac Lab 1.4.0 | vendor_doc | README.md:7-8 |
| The extension is installed with `python -m pip install -e exts/bipedal_locomotion` using a Python interpreter that has Isaac Lab installed | vendor_doc | README.md:42-45 |
| The training command selects the registered task `Isaac-PF-Blind-Flat-v0` | vendor_doc | README.md:67 |
| Real-robot deployment is delegated to the external `rl-deploy-with-python` repository's `mlp` branch | vendor_doc | README.md:109 |
| `Isaac-PF-Blind-Flat-v0` is registered with the external entry point `omni.isaac.lab.envs:ManagerBasedRLEnv` and `env_cfg_entry_point` `pointfoot_env_cfg.PFBlindFlatEnvCfg` | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/robots/__init__.py:64-71 |
| The flat task inherits `PFBaseEnvCfg` and sets the height scanner, the policy and critic heights observations and the terrain-level curriculum to `None` | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/robots/pointfoot_env_cfg.py:72-80 |
| The pointfoot base environment sets the robot to `POINTFOOT_CFG` and the six leg joint initial positions to 0.0, 0.0, 0.0918, 0.0918, -0.057 and -0.057 | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/robots/pointfoot_env_cfg.py:31-39 |
| `POINTFOOT_CFG`'s initial state names the six leg joints plus `foot_L_Joint` and `foot_R_Joint`, eight joints in all | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/assets/config/pointfoot_cfg.py:29-42 |
| The action term is a joint-position action over the six named leg joints with scale 0.25 and `use_default_offset` True | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:112-117 |
| The base velocity command has `heading_command` True | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:97 |
| The base velocity command ranges are lin_vel_x -1.0 to 1.0, lin_vel_y -0.5 to 0.5, ang_vel_z -1 to 1 and heading -pi to pi | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:103-105 |
| The gait command ranges are frequency 1.5 to 2.5 Hz, offset 0.5 and duration 0.5, resampled every 5.0 s | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:85-93 |
| The policy observation terms in order are base angular velocity, projected gravity, joint positions, joint velocities, last action, velocity command, gait phase and gait command | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:128-145 |
| The policy observation group concatenates its terms, enables corruption and uses `history_length` 5 with `flatten_history_dim` True | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:150-154 |
| The simulation advances by `sim.dt` 0.005 s, the control decimation is 4, an episode is 20.0 s long and the configured seed is 42 | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:435-440 |
| The episode ends through the `time_out` term or an illegal contact of `base_Link` above a threshold of 1.0 | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:395-402 |
| `get_gait_phase` returns the gait phase as [sin(phase), cos(phase)] with shape (num_envs, 2) | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/mdp/observations.py:117-124 |
| `get_gait_command` returns the gait command parameters [frequency, offset, duration] with shape (num_envs, 3) | upstream_code | exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/mdp/observations.py:143-150 |

Tags (short lowercase keywords): `pointfoot`, `bipedal`, `locomotion`, `blind-flat`, `isaac-lab`, `isaac-sim`,
`reinforcement-learning`, `simulation`, `gymnasium`.

## The contract

`GymnasiumDriver` is configuration only, so the contract is derived from the fake environment's spaces:

* `cap.world.step.v1` takes `{ticks, action}`. The action is `{"values": [six numbers]}`; the fake's `Box` is
  unbounded because the clone configures no action clip and the real bounds come from the external
  `ManagerBasedRLEnv` implementation. `ticks` is an integer from 1 to the driver's `max_ticks` (the SDK default
  10000). Each tick advances 20 ms of simulated time (4 x 0.005 s, `base_env_cfg.py:435-439`).
* `cap.world.reset.v1` takes `{seed, options}`; the bridge starts a full episode. `cap.world.seed.v1` takes `{seed}`
  and applies it to the next reset, so it makes no native call.
* The world state is the bridge's `observation`, `reward`, `terminated`, `truncated`, `tick`, `episode`, `seed` and
  `info` fields. No hardware stop exists: the device is simulated at R0 and an e-stop latches the bridge.

## The fake, and what it does not model

The upstream task needs Isaac Sim 4.2.0 and Isaac Lab 1.4.0 with a GPU (`README.md:7-8`) and package code never
imports the clone, so `fake.py` is a pure Python kinematic stand-in. Its action scale, default joint positions,
eight joint names, command ranges, time step and 1000-step time limit are read from the clone. Everything else is
test data marked `# placeholder`:

* the policy observation is a 185-value stand-in built from the eight terms and `history_length` 5
  (`base_env_cfg.py:128-154`); observation corruption, command resampling and the real Isaac Lab observation space
  were not observed;
* there is no rigid-body dynamics, contact, friction, actuator, sensor, terrain or noise model; the base-contact
  termination and the reward terms are not modelled;
* the fake's base angular velocity, projected gravity, reward, gait values and velocity-command heading are
  placeholders;
* the fake was not compared with an Isaac Sim trajectory, and neither the `sim` backend nor the registered task was
  run.

No safety limit, no hardware stop and no operator-required bound is declared: the device is a simulation at R0 and
the action space carries no sourced numeric bound.
