OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.darshmenon/ur3_ros2_pick_and_place

Every fact cites the pinned clone at commit `e58ea6178d8d8195beb92387ba365227840a96a9`.
The source is `upstream_code` and the reference is `path/in/clone:LINE`, using a
range where the statement spans adjacent lines. The same facts are written in
`driver.py` (`facts = [...]`); `REFERENCE.md` is generated from the driver, not
from this page.

The selected entry symbol is `mujoco_ur_rl_ros2.envs.ur_reach_env:URReachEnv`
(`mujoco_ur_rl_ros2/envs/ur_reach_env.py:26`). The original card named `RosDriver`
(family `ros`), but every confirmed entry symbol is a Gymnasium environment
class and the repository's ROS nodes are policy/deployment code around that
environment. This package therefore uses `GymnasiumDriver`; the regenerated
card now matches this source-backed selection through a registry override.
The original card and correction are recorded in `RESULT.json` notes.

## Facts

| fact | source | ref |
|---|---|---|
| URReachEnv is a Gymnasium environment (a gym.Env subclass) for a UR5e reach task. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:26-27 |
| URReachEnv resolves MuJoCo Menagerie models from $MUJOCO_MENAGERIE_PATH or ~/mujoco_menagerie and raises FileNotFoundError when that directory is absent. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:11-23 |
| URReachEnv models six UR5e joints and composes a 15-number observation from six joint positions, six joint velocities and three target coordinates. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:55-61 |
| The normalized joint-velocity action space is a six-element Box with low -1.0 and high 1.0. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:55-66 |
| Each upstream action is scaled by 0.5 to rad/s and advances the MuJoCo model with five mj_step calls. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:100-104 |
| URReachEnv stores the model timestep multiplied by five as its _dt attribute. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:56 |
| On reset the environment restores the MuJoCo data and samples the target radius from 0.2 to 0.55, the azimuth from -pi/2 to pi/2 and the elevation from 0.1 to pi/2. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:81-93 |
| The step reward is the negative end-effector-to-target distance plus 1.0 when that distance is below 0.05. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:106-111 |
| The episode terminates when the end-effector-to-target distance is below 0.02 and truncates after the simulated time exceeds 10.0 s. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:113-114 |
| render() lazily launches a passive MuJoCo viewer when render_mode is human, and close() closes that viewer. | upstream_code | mujoco_ur_rl_ros2/envs/ur_reach_env.py:121-129 |

## Scope

The package serves the Gymnasium interface through the `cap.world.step.v1`,
`cap.world.reset.v1` and `cap.world.seed.v1` catalogue classes. The bridge
derives the step schema from the fake's six-element action space and cites the
upstream `Box(low=-1.0, high=1.0, ...)` line. The action is a normalized
joint-velocity command; the bridge passes it to `env.step` unchanged.

The upstream environment's own ROS policy nodes, MoveIt configuration,
Gazebo launch files, RL training scripts, MJCF model files elsewhere in the
clone and every physical UR arm interface are **NOT COVERED**. The driver
binds the selected environment class only. This package is a simulator view:
it cannot command a real robot and does not start any ROS node or Gazebo
instance. The optional sim backend can open a MuJoCo viewer only when explicitly
configured with render_mode="human"; the fake never does.

## Fidelity contract

The gate-tested fake backend is the package's `FakeURReachEnv`, a deterministic
analytic stand-in. It is F0: engine `analytic:package stand-in (no MuJoCo
physics)`, `timestep_ms: 0`, `realtime_factor: 0`, lockstep clock, full reset,
seeded determinism and no snapshot/restore. It returns the upstream
observation size (15 numbers) with placeholder values, but it runs no MuJoCo
physics, contacts, gripper or rendering, and it always returns `terminated`
and `truncated` as false. The upstream reward and termination criteria are
recorded as source facts, not as fake behaviour.

The upstream simulator was not used: `URReachEnv` needs MuJoCo and a
`mujoco_menagerie` checkout under `$MUJOCO_MENAGERIE_PATH` or
`~/mujoco_menagerie` (`ur_reach_env.py:11-23`), and neither is installed. No
network access, pip install or upstream execution was used. Copied action bounds and observation dimensions are sourced declarations.
The fake's transition/state values marked `# placeholder` are test data, not
facts or sourced limits. The upstream info key `dist` is preserved.

## Safety

The device is a simulated world at R0. It has no physical actuator, no
independent hardware stop and no hardware backend. `safe_state` describes refusal of subsequent steps by the software latch;
it does not reset the episode or resample the target, and it does not preempt
an in-flight native step. This is not a physical safety claim. The runtime's software e-stop latch still applies, and the bridge is
not given an e-stop binding because the simulator has no native stop. No
`Limit` is declared for the action: a `GymnasiumDriver` derives the step
bounds from the action space, and the upstream line that writes them is cited
as `action_space_ref`.

## Tags

`gymnasium`, `mujoco`, `simulation`, `ur5e`, `reach`, `rl`

## Explicit simulator deployment (not run here)

The `sim` backend is `.sim:make_env`; it never falls back to the fake.
Pass the factory option `upstream_root` as the root of the pinned repository
(the directory containing `mujoco_ur_rl_ros2/envs/ur_reach_env.py`), and optionally
`render_mode` as null or `"human"`. The factory verifies the five eagerly imported
source files against hashes from the pin, temporarily provides the subproject
as the top-level `envs` import context, and rejects a foreign cached `envs` or
`envs.ur_reach_env` module instead of deleting it. Use a fresh interpreter if
another project has already imported that generic namespace.

The environment needs installed `numpy`, `gymnasium`, `mujoco` with `MjSpec`,
and `stable_baselines3` (the last is imported by `envs/__init__.py` through
`shared_arm_env.py`). `MUJOCO_MENAGERIE_PATH`, or the upstream default
`~/mujoco_menagerie`, must contain `universal_robots_ur5e/ur5e.xml` and
`robotiq_2f85/2f85.xml` plus their referenced assets. Missing source, dependencies
or assets fail explicitly. No install or simulator launch was performed here.

`fidelity_by_backend` keeps the fake analytical F0 separate from the simulator's
MuJoCo F1 deployment declaration. The factory reads the physics timestep from
the constructed model and exposes it as `dt` for SDK fidelity reporting; it
preserves upstream `_dt`, the control period of five physics steps. Each upstream
`env.step` advances those five substeps. There is no wall-clock pacing, exact
snapshot or hardware calibration claim. External Menagerie versions and
MuJoCo compatibility still require deployment validation. A private test with
synthetic modules proves factory selection, option forwarding and failure
behavior; it does not prove actual MuJoCo compatibility.

## Physics-tick declaration

The sim backend now opts into `physics_ticks_v1`: explicit ticks must be positive
multiples of five, and K requested physics ticks make K/5 native calls. The
physics clock is `data.time` and the interval is `model.opt.timestep`; the SDK
publishes both that interval and the five-step control period, with command-local
measured timing in receipts. Reset uses `mj_resetData` and `mj_forward` without
`mj_step` (pinned `ur_reach_env.py:81-98`); step has five `mj_step` calls and returns
without native autoreset (`:100-119`). Deployment must exclude any independent
clock advancement. Fake timing and its F0 contract are unchanged. Synthetic
factory/clock tests are not an actual MuJoCo run or physics validation.
