# Facts and tags for gh.isaaczh/himloco_lab

Every fact cites `upstream_code` at commit `c3fbd0173f2a53a86e472c099f8e2e9744cf7639`; the path is relative to the
clone root, including the `source/` layout.  The same facts are in `driver.py` (`facts = [...]`), and the reference
files are generated from the driver.

| fact | source | ref |
|---|---|---|
| Unitree-Go2-Velocity is registered with entry point himloco_lab.envs:HimlocoManagerBasedRLEnv and the training configuration velocity_env_cfg:RobotEnvCfg | upstream_code | source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/__init__.py:3-13 |
| HimlocoManagerBasedRLEnv extends isaaclab.envs.ManagerBasedRLEnv | upstream_code | source/himloco_lab/himloco_lab/envs/him_manager_based_rl_env.py:3-6 |
| The environment's step returns six values: observations after reset, observations before reset, rewards, terminated flags, timeout flags and extras | upstream_code | source/himloco_lab/himloco_lab/envs/him_manager_based_rl_env.py:120 |
| The Go2 asset lists 12 joints: hip, thigh and calf for each of the four legs | upstream_code | source/himloco_lab/himloco_lab/assets/unitree.py:133-138 |
| The joint-position action applies scale 0.25 with the default joint offset and clips the processed action to -100 to 100 | upstream_code | source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py:247-249 |
| The velocity command is an SE(2) command: linear velocity in x and y plus angular velocity around z | upstream_code | source/himloco_lab/himloco_lab/tasks/locomotion/mdp/commands/commands.py:22-25 |
| The policy observation group has velocity commands, base angular velocity, projected gravity, relative joint positions, relative joint velocities and the last action | upstream_code | source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py:261-271 |
| Every policy observation term is clipped to -100 to 100 | upstream_code | source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py:262-271 |
| The environment advances 4 physics steps of 0.005 s per environment step and an episode lasts 20 s | upstream_code | source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py:488-492 |
| The upstream licence metadata is inconsistent: the setup.py SPDX header says BSD-3-Clause while the setup() call declares Apache-2.0 | upstream_code | source/himloco_lab/setup.py:4-35 |

## Device and contract

The driver serves the Gymnasium environment `Unitree-Go2-Velocity` registered at
`source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/__init__.py:3-13`.  The class registered as the entry point
is an Isaac Lab `ManagerBasedRLEnv` subclass (`source/himloco_lab/himloco_lab/envs/him_manager_based_rl_env.py:3-6`),
so the environment needs Isaac Lab, Isaac Sim, torch and a GPU; `README.md:55-72` makes installing Isaac Lab the first
installation step.  The gate does not install or import any of that.  The `native` symbol is still the card's entry
symbol, and the `fake` backend is `fake.py` (a pure Python contract stand-in), not the upstream class.

The action is a 12-element joint-position action, one value per Go2 joint
(`source/himloco_lab/himloco_lab/assets/unitree.py:133-138`).  The upstream `JointPositionActionCfg` applies
`scale=0.25` with the default joint offset and clips the processed action to `(-100.0, 100.0)`
(`source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py:247-249`).  The fake's action space
uses that clip as its bounds; the raw action space of the Isaac Lab environment is provided by Isaac Lab and was not
observed here (see the fidelity gaps).  No `Limit` object is declared in `driver.py`: the step bound is derived from the
environment's action space by `GymnasiumBridge`; it has no source, and its ref names the fake backend
(`action_space of the fake backend .fake:FakeHimlocoEnv`), not a clone line.

The policy observation group combines the 3-component SE(2) velocity command, 3 base angular velocity values, 3 projected
gravity values, 12 relative joint positions, 12 relative joint velocities and the 12 last actions
(`source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py:261-271`); every term is clipped to
`-100..100` (`:262-271`).  The fake exposes this policy group only; the critic group (base linear velocity, external
force and a height scan) is not modelled, and that is a fidelity gap.

## Timing and determinism

One environment step is `decimation = 4` physics steps of `sim.dt = 0.005 s`, i.e. 20 ms, and an episode is
`episode_length_s = 20.0 s` (`source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py:488-492`).
The fake advances one tick per `step` call, truncates at `20.0 / (4 * 0.005) = 1000` ticks, and declares
`timestep_ms = 20.0`, `realtime_factor = 0`, `clock = lockstep` and `reset = full`.

The fake reseeds its command draw from `reset(seed)`; the same seed repeats the initial observation, but the fake does
not reproduce upstream's numpy/torch random streams, its domain randomisation or its heading controller.  No exact
state snapshot/restore is offered (`snapshot_restore = false`).

## Safety

Simulated R0 device: the driver builds `mode = "simulated"`, has no hardware backend and exposes no physical stop.
The e-stop is the runtime's software latch.  After it, `cap.world.step.v1`, `cap.world.reset.v1` and
`cap.world.seed.v1` are refused until `mhs.safety.reset` clears the latch; the last observation remains readable.  The
C++ DDS controller under `deploy/robots/go2` that can command a real Go2 (README.md:190-196) is a different interface
and is not covered by this package.

## Licence recon

The repository has no `LICENSE` file at the clone root.  `source/himloco_lab/setup.py:4` says
`SPDX-License-Identifier: BSD-3-Clause`, while `source/himloco_lab/setup.py:35` sets `license="Apache-2.0"`; the card
pins `NOASSERTION` with class `unknown`.  The package copies no upstream code (the fake is a clean-room contract
stand-in), but publication is a licence-review decision for the owner.

Tags: quadruped, unitree-go2, locomotion, velocity-tracking, isaac-lab, reinforcement-learning, simulation, gymnasium
