# Facts and tags for gh.openai/roboschool

Every fact cites its source at commit `d32bcb2b35b94168b5ce27233ca62f3c8678886f`: `upstream_code` is a line of the
clone (`path/in/clone.py:LINE`).  The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RoboschoolInvertedPendulum-v1 is registered with entry point roboschool:RoboschoolInvertedPendulum, max_episode_steps 1000 and reward_threshold 950.0 | upstream_code | roboschool/__init__.py:11-17 |
| RoboschoolInvertedPendulum is a continuous-control inverted pendulum: keep a pole upright by moving the 1-D cart | upstream_code | roboschool/gym_pendulums.py:69-74 |
| The class is constructed with action_dim 1 and obs_dim 5 | upstream_code | roboschool/gym_pendulums.py:78 |
| The action space is Box(-high, high) with high = np.ones([action_dim]), so with action_dim 1 it is bounded by -1 and 1; the observation space is Box(-inf*ones([obs_dim]), inf*ones([obs_dim])) | upstream_code | roboschool/gym_mujoco_xml_env.py:26-29 |
| The scene uses gravity 9.8, timestep 0.0165 s and frame_skip 1 | upstream_code | roboschool/gym_pendulums.py:81 |
| The pole hinge angle is drawn uniformly from -0.1 to 0.1 radians before each episode | upstream_code | roboschool/gym_pendulums.py:87-88 |
| Each step applies a motor torque of 100 times the action clipped to -1..1 | upstream_code | roboschool/gym_pendulums.py:91-93 |
| The observation is [cart position, cart velocity, cos(theta), sin(theta), theta angular velocity] | upstream_code | roboschool/gym_pendulums.py:95-102 |
| A non-swingup step rewards 1.0 and terminates when the absolute pole angle exceeds 0.2 radians | upstream_code | roboschool/gym_pendulums.py:104-120 |
| RoboschoolInvertedPendulum.step is the legacy Gym API: it returns the four-tuple (state, reward, done, info) | upstream_code | roboschool/gym_pendulums.py:120 |
| The base environment seeds its numpy generator with gym.utils.seeding.np_random(seed) and returns [seed] | upstream_code | roboschool/gym_mujoco_xml_env.py:35-37 |
| The base reset recreates the scene, resets the robot and returns the initial observation | upstream_code | roboschool/gym_mujoco_xml_env.py:39-78 |

Limits: the driver declares none.  The only input bound is the action space, which the bridge derives from the
environment (`Box(-1, 1)` with one element: `action.values` from -1 to 1, with no source and the ref
`action_space of the fake backend .fake:FakeInvertedPendulum`), and `ticks` (1 to `max_ticks`, 10000 by default).  The
device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `roboschool:RoboschoolInvertedPendulum-v1`, level F1
(the rigid-body scene, no contacts or sensor model), determinism `seeded` with `seed_control` `parameter`, timestep
16.5 ms (`timestep=0.0165`, `roboschool/gym_pendulums.py:81`), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore.  The gaps say what the fake does not model and that it was not compared with the upstream
scene.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: inverted-pendulum, cartpole, continuous-control, reinforcement-learning, roboschool, simulation
