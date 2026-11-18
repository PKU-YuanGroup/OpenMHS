# Facts and tags for gh.jerome-graves/yertle

Every fact cites the clone at commit `9d04e2d2c1da07d5845807bd36b242b1d0eff843`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The fake's
numbers marked `# placeholder` are test data and appear in no fact, limit or reference.

| fact | source | ref |
|---|---|---|
| YertleEnv is a Gymnasium environment for the Yertle quadruped that loads simulation/yertle.urdf in PyBullet and exposes the standard Gymnasium API | upstream_code | learning/yertle_env.py:1-4 |
| YertleEnv subclasses gym.Env | upstream_code | learning/yertle_env.py:126 |
| The constructor takes an optional config and render_mode and defaults both to None | upstream_code | learning/yertle_env.py:131 |
| The URDF path is the repository root beside this module, simulation/yertle.urdf | upstream_code | learning/yertle_env.py:48-49 |
| smoke_test constructs YertleEnv directly | upstream_code | learning/smoke_test.py:18 |
| The robot has 12 actuated joints: the four leg prefixes lf, rf, lb and rb times the three segments shoulder, thigh and shin | upstream_code | learning/yertle_env.py:47-51 |
| The action space is one residual per actuated joint: a Box with low -1.0 and high 1.0 | upstream_code | learning/yertle_env.py:150-151 |
| The default action_scale is 0.4 rad | upstream_code | learning/yertle_env.py:83-84 |
| A step adds the scaled action residual to DEFAULT_STANCE and clips each target to the joint soft limits | upstream_code | learning/yertle_env.py:278-281 |
| The standing pose is shoulder 0.0, thigh -0.6 and shin 0.9 rad, repeated for the four legs | upstream_code | learning/yertle_env.py:65-71 |
| The per-joint soft limits are shoulder -45 to 45 degrees, thigh -90 to 20 degrees and shin 13 to 90 degrees | upstream_code | learning/yertle_env.py:56-63 |
| The observation space is a 48-dimensional Box of unbounded floats | upstream_code | learning/yertle_env.py:153-156 |
| The observation concatenates base linear velocity, base angular velocity, projected gravity, the velocity command, joint positions relative to the stance, joint velocities times 0.1 and the previous action | upstream_code | learning/yertle_env.py:332-343 |
| The default command ranges are vx 0.15 to 0.35 m/s, vy -0.1 to 0.1 m/s and yaw -0.4 to 0.4 rad/s | upstream_code | learning/yertle_env.py:91-95 |
| The simulation steps at 1/240 s and the control loop runs four physics steps per environment step (60 Hz), and an episode is 12 s | upstream_code | learning/yertle_env.py:78-81 |
| The maximum number of environment steps is int(episode_seconds / (sim_timestep * control_decimation)) | upstream_code | learning/yertle_env.py:140 |
| A step sets truncated when the step count reaches the maximum | upstream_code | learning/yertle_env.py:297-299 |
| The termination thresholds are 0.08 m base height and 0.7 rad tilt (about 40 degrees) | upstream_code | learning/yertle_env.py:97-99 |
| A step reports terminated when the base height is below min_base_height or the tilt exceeds max_tilt | upstream_code | learning/yertle_env.py:378-381 |
| The reward uses exponential kernels for linear and yaw velocity tracking, a forward-progress term clipped to +-0.5 and penalties on energy, action rate, orientation and height | upstream_code | learning/yertle_env.py:355-376 |
| A fall subtracts 5.0 from the reward | upstream_code | learning/yertle_env.py:380-381 |
| reset(seed) replaces the numpy generator, samples a new velocity command, resets the joints to DEFAULT_STANCE and returns (observation, {}) | upstream_code | learning/yertle_env.py:247-268 |
| Domain randomisation is on by default: base-mass scale 0.85 to 1.15, foot friction 0.6 to 1.2, observation noise 0.02 and random pushes every 150 steps of 0.25 m/s | upstream_code | learning/yertle_env.py:114-120 |
| The environment connects a PyBullet GUI client only when render_mode is human and a DIRECT (headless) client otherwise | upstream_code | learning/yertle_env.py:166-171 |
| render() returns a 640 by 480 RGB array when render_mode is rgb_array | upstream_code | learning/yertle_env.py:385-394 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1, 1, (12,))`: `action.values` per element from -1 to 1, source `upstream_code`, ref
`learning/yertle_env.py:151`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no
limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:learning.yertle_env:YertleEnv`, level F1
(the interface and reward of the environment, not its PyBullet dynamics), determinism `seeded` with `seed_control`
`parameter`, timestep 16.67 ms (four physics steps of 1/240 s per environment step, `learning/yertle_env.py:78-81`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake models no
contact, friction, servo, inertia override or fall, that a seed does not reproduce upstream's numpy stream, that
rendering is not covered, and that the sim backend constructs `YertleEnv` with the constructor defaults while the
fake was not compared with a PyBullet run.

No gymnasium id is registered for `YertleEnv`. The Isaac Lab entries in `isaac_lab/__init__.py` name the external
`isaaclab.envs:ManagerBasedRLEnv` (`isaac_lab/__init__.py:10-12`), and `learning/smoke_test.py:18` constructs
`YertleEnv` directly. The `fake` backend is the package's pure Python stand-in (`.fake:FakeYertleEnv`). The `sim`
backend is the callable `_build_sim_env`, which imports `learning.yertle_env:YertleEnv` (`learning/yertle_env.py:126`)
and calls it with the constructor defaults (`learning/yertle_env.py:131`): `render_mode` None connects a DIRECT
PyBullet client (`learning/yertle_env.py:166-171`). The URDF is `simulation/yertle.urdf` under the repository root
beside the module (`learning/yertle_env.py:48-49`). The import is inside the factory, so the fake backend does not
import PyBullet. The `sim` entry is a callable, so the lock's string entry (`fake` only) is unchanged.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the environment state stays readable.

Tags: quadruped, locomotion, reinforcement-learning, simulation, gymnasium, pybullet
