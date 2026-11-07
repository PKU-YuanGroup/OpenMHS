# Facts and tags for gh.dh-ng/tacex

Every fact cites its source at commit `adceed41afb7cb48f9ec1f66a662fb8e5a06627f`: `upstream_code` (code or a comment of
the clone) or `vendor_doc` (documentation text of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TacEx-Ball-Rolling-Privileged-v0 is registered with entry_point tacex_tasks.ball_rolling_privileged.base_env:BallRollingEnv and disable_env_checker=True | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/__init__.py:20-31 |
| BallRollingEnv is an Isaac Lab DirectRLEnv subclass configured by BallRollingEnvCfg | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:235 |
| The cfg sets decimation to 1 and sim.dt to 0.01 s, so one environment step advances 10 ms | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:80-83 |
| The environment computes its step interval as sim.dt times decimation | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:256 |
| The configured episode length is 8.3333 / 2 s; the source comment calls it 500 timesteps, but at dt 0.01 s the quotient is about 416.7 | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:222 |
| The action space has five components (dx, dy, dz, droll, dpitch); dyaw is omitted | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:223 |
| Every action component is clamped to [-1, 1] before it is passed to the IK controller | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:381 |
| The differential IK controller is configured for pose commands in relative mode with the damped least squares method | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:171 |
| The observation space has 14 values: 3 for the end-effector position, 2 for its roll and pitch, 2 for the goal, 2 for the object position and 5 for the actions | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:224-226 |
| The observation concatenates the end-effector position, its roll and pitch, the object xy position, the desired goal xy position and the five actions | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:588-603 |
| The success reward has weight 10 and a 0.005 m object-goal threshold | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:199-203 |
| The reward adds the success term when the object-goal distance is below success_reward['threshold'] | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:480 |
| The ball is spawned at (0.5, 0, 0.01) m | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:188 |
| The ball radius is 0.005 m | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:229 |
| The object bounds are x in (0.225, 0.75) m and y in (-0.375, 0.375) m, and too_far_away_threshold is 0.35 m | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:230-232 |
| An episode ends when the object leaves the configured x or y bounds, is more than 1 m from the goal, or is farther from the end effector than the configured too_far_away_threshold | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:409-424 |
| obj_pos_randomization_range lists [-0.1, 0.1] per axis in its first entry and [-0.25, 0.25] in its second | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:219 |
| The reset sets the goal to the object default position plus a uniform offset in each axis, using the obj_pos_randomization_range entry indexed by curriculum_phase_id | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:555-562 |
| The robot is the Franka Panda arm with a GelSight Mini sensor and stiff PD control | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:102-103 |
| The cfg runs 1024 environments in parallel by default | upstream_code | source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py:100 |
| TacEx requires Isaac Sim 4.5 and Isaac Lab 2.1.1; the installation was tested on Ubuntu 22.04 with a 4090 GPU | vendor_doc | README.md:40-41 |
| The local installation requires Isaac Sim 4.5 and Isaac Lab 2.1.1 on Ubuntu 22.04 | vendor_doc | docs/source/installation/Local-Installation.md:2-6 |

## Limits

The driver declares no numeric bound of its own. The only action bound is `[-1, 1]` per component, read from the clamp
at `base_env.py:381`; the fake's five-element action Box uses it, so the bridge publishes `action.values[*]` with that
range and refuses an out-of-range step before the environment is touched. The catalogue `cap.world.step.v1` schema
bounds `ticks` (1 to the bridge's `max_ticks`, 10000) and `cap.world.seed.v1` bounds `seed` to a non-negative integer;
the runtime enforces both. No field is `operator_required`: the device is simulated R0 and there is no physical bound
for an operator to supply.

## Fidelity

The deployed model is the package fake, F0 (kinematic/analytic): engine `gymnasium:TacEx-Ball-Rolling-Privileged-v0`,
determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 10.0 (sim.dt 0.01 s at decimation 1,
`base_env.py:80-83` and `:256`), `realtime_factor` 0, clock `lockstep`, reset `full`, `snapshot_restore` false. The gaps
in `driver.py` state what is not modelled: Isaac Sim physics, IK, the Franka arm, tactile/RGB/depth sensors and
rendering; only the success term of the reward; a placeholder end-effector pose and push gain; a 416-step truncation
derived from `episode_length_s / dt`; the 1024-environment vectorization reduced to one; and that the upstream stack
was never started here.

## Safety

Simulated R0 device: no physical effect, no hardware backend and no hardware run. The e-stop is the runtime's software
latch: after it no step or reset is accepted until `mhs.safety.reset` clears the latch, the fake is not advanced and the
state stays readable. No physical stop exists and none is claimed.

Tags: tacex, tactile, isaac-sim, isaac-lab, ball-rolling, reinforcement-learning, simulation, gymnasium
