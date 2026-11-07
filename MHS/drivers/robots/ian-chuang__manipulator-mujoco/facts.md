# Facts and tags for gh.ian-chuang/manipulator-mujoco

Every fact cites its source at commit `f2d7d776a74034387e825dec6a13a91b1e1f493e`: `upstream_code` is a line of the
clone.  The same facts are written into `driver.py` (`facts = [...]`); the reference files are generated from the
driver, not from this page.

## What this package serves

The card lists two Gymnasium entry symbols: `manipulator_mujoco.envs:AuboI5Env` (`manipulator_mujoco/envs/aubo_i5_env.py:13`)
and `manipulator_mujoco.envs:UR5eEnv` (`manipulator_mujoco/envs/ur5e_env.py:13`).  This package implements the first,
`AuboI5Env`, because the card's model entries are the AG95 assets and this is the environment that composes the
Aubo i5 arm with the AG95 gripper (`manipulator_mujoco/envs/aubo_i5_env.py:44-51`).  `UR5eEnv` is the second
environment, registered as `manipulator_mujoco/UR5eEnv-v0` (`manipulator_mujoco/__init__.py:12-18`); it was not
implemented (one device per package).  The card also lists `assets/robots/ag95/scene.xml` and `ag95.xml`.  The
environment attaches the AG95 robot model (`ag95.xml`) to the Aubo i5 arm; the standalone `ag95/scene.xml` (a
temporary scene with a hanging box and a tendon, `assets/robots/ag95/scene.xml:28-40`) is not loaded by either
environment.  The Aubo i5 model used by the environment is `assets/robots/aubo_i5/aubo_i5.xml`
(`manipulator_mujoco/robots/aubo_i5.py:4-7`).

## Facts

| fact | source | ref |
|---|---|---|
| AuboI5Env is declared as a gymnasium.Env subclass | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:13 |
| AuboI5Env is registered as manipulator_mujoco/AuboI5Env-v0 with entry point manipulator_mujoco.envs:AuboI5Env | upstream_code | manipulator_mujoco/__init__.py:4-10 |
| The second environment of the package is registered as manipulator_mujoco/UR5eEnv-v0 with entry point manipulator_mujoco.envs:UR5eEnv | upstream_code | manipulator_mujoco/__init__.py:12-18 |
| The observation space is a Box of shape (6,) with -inf and +inf float64 bounds | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:22-24 |
| The action space is a Box of shape (6,) with every element bounded by -0.1 and 0.1 (float64) | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:27-29 |
| The environment builds a StandardArena, a mocap Target, an AuboI5 arm, an AG95 gripper attached to the arm and a box with 0.02 m half-extents attached as a free body, then creates the physics | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:39-67 |
| AuboI5Env hands the OSC min_effort -150.0, max_effort 150.0, kp 300, ko 300, kv 30, vmax_xyz 1.0 and vmax_abg 2.0 | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:70-81 |
| The operational-space controller computes the task-space command and adds gravity compensation before passing the joint effort to the effort controller | upstream_code | manipulator_mujoco/controllers/operational_space_controller.py:91-103 |
| The joint effort controller clips every commanded effort to [min_effort, max_effort] and writes it to the joints' qfrc_applied | upstream_code | manipulator_mujoco/controllers/joint_effort_controller.py:28-32 |
| The arena sets the physics timestep to 0.002 s on the MJCF option | upstream_code | manipulator_mujoco/arenas/standard.py:7 |
| The environment stores the physics model's opt.timestep as its own step interval | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:84 |
| The Aubo i5 model bounds each of its six joints to -3.04 to 3.04 rad | upstream_code | manipulator_mujoco/assets/robots/aubo_i5/aubo_i5.xml:60-101 |
| The AG95 model gives its joints and the fingers actuator a joint range and ctrlrange of 0 to 0.943 and a forcerange of -5 to 5 | upstream_code | manipulator_mujoco/assets/robots/ag95/ag95.xml:6-13 |
| The AG95 fingers_actuator is a general actuator driven by the split tendon of the two outer knuckle joints | upstream_code | manipulator_mujoco/assets/robots/ag95/ag95.xml:132-148 |
| The ag95/scene.xml file includes ag95.xml and adds a free box with 0.015 m half-extents tied to an anchor by a spatial tendon limited to 0 to 0.02 m | upstream_code | manipulator_mujoco/assets/robots/ag95/scene.xml:6-40 |
| reset(seed, options) calls super().reset(seed=seed), sets the six arm joints to the qpos [0, 0, 1.5707, 0, 1.5707, 0], places the mocap target at [0.5, 0, 0.04] with quaternion [0, 0, 0, 1] and returns the observation and the info dict from _get_info() | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:96-109 |
| _get_obs returns np.zeros(6) and _get_info returns an empty dict | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:88-94 |
| step(action) does not read its action argument: it takes the current mocap target pose, runs the OSC toward it and steps the physics once | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:111-121 |
| step returns the observation, reward 0, terminated False, truncated False and the info dict | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:127-133 |
| Neither registered environment id sets max_episode_steps; the two register calls pass only id and entry_point and both max_episode_steps lines are commented out | upstream_code | manipulator_mujoco/__init__.py:4-18 |
| render returns physics.render() when render_mode is rgb_array, and close closes the viewer if one was launched | upstream_code | manipulator_mujoco/envs/aubo_i5_env.py:135-178 |

## Limits

The driver declares no limit of its own.  The only bounds are derived by the Gymnasium bridge from the
environment's spaces and from `max_ticks`:

- `cap.world.step.v1` input `action.values` is bounded per element by the action space, from -0.1 to 0.1
  (`manipulator_mujoco/envs/aubo_i5_env.py:27-29`); the bridge publishes them with no source and the ref
  `action_space of the fake backend .fake:FakeAuboI5Env`.
- `cap.world.step.v1` input `ticks` is an integer from 1 to 10000 (`GymnasiumDriver.max_ticks`).
- `cap.world.reset.v1` input `seed` is a non-negative integer; `options` is an object the environment accepts and
  ignores (`manipulator_mujoco/envs/aubo_i5_env.py:96-97`).

The observation space is unbounded (-inf/+inf, `aubo_i5_env.py:22-24`) and is not a writable field.  There is no
numeric command that needs an operator bound, so no limit is `operator_required` and there is no
`site-limits.example.json`.

## Safety

The device is a simulation: `mode = "simulated"`, no hardware backend, no native stop, no physical e-stop.  The
risk is R1, above the card's R0 floor, because the capability advances a simulated robot (simulation stepping is the
R1 example in MHS-004 section 2.1); nothing in the package touches a physical Aubo i5, AG95 or MuJoCo device.  The
runtime's software e-stop latch stops the simulation: after an e-stop no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the last state stays readable.  No protection beyond that runtime latch is
claimed, and no hardware run was made.

## Mock path

The card's `mock_strategy.preferred` is `upstream-sim`, but the upstream environment is not importable where the
gate runs: it imports `mujoco`, `dm_control`, `numpy` and `gymnasium` (`requirements.txt:1-4`), `mujoco`,
`dm_control` and `gymnasium` are not installed, the gate never installs the upstream package and the sandbox has no
network.  The `fake` backend is the package's own pure Python stand-in (`fake.py`) for the public API of
`AuboI5Env`: `reset`, `step`, `render`, `close`, the observation space, the action space, a tick counter and the
upstream all-zero observation.  It integrates no dynamics and was never compared with the upstream environment.
A backend name that `backends` does not list (`sim`) is opened by
`gymnasium.make("manipulator_mujoco/AuboI5Env-v0")`; that path was not run.

## Fidelity

The contract in `driver.py` describes the fake as deployed: engine
`gymnasium:manipulator_mujoco/AuboI5Env-v0`, level F0 (kinematic stand-in, no dynamics), determinism `seeded` with
`seed_control: parameter`, timestep 2 ms (`manipulator_mujoco/arenas/standard.py:7`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot/restore.  The upstream model would justify F1 with MuJoCo rigid-body
dynamics, but that engine is not part of this package's fake; the gaps say so.  The gaps also state that the action
is ignored by the upstream step (`aubo_i5_env.py:111-121`), that the observation is the constant zeros(6), that
there is no rendering, no wall-clock pacing, no snapshot and no validation against a physical robot.

Tags: aubo-i5, ag95, manipulation, mujoco, gymnasium, simulation, reinforcement-learning
