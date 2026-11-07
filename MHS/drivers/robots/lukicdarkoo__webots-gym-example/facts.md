# Facts and tags for gh.lukicdarkoo/webots-gym-example

Every fact cites its source at commit `dd825e00f89f187f53130bcbde1ddd2a3ca44ab2`. The clone has no README, no
`docs/`, no licence text and no manual, so every fact is `upstream_code` from the Webots controller or the world file.
The same facts are written into `driver.py` (`facts = [...]`); the reference files are generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| The controller imports `Supervisor` from Webots' embedded `controller` module, not from a serial, USB, VISA or vendor transport library | upstream_code | controllers/gym_controller/gym_controller.py:2 |
| `WebotsStickEnv` subclasses `Supervisor` and `gym.Env` | upstream_code | controllers/gym_controller/gym_controller.py:16 |
| The action space is `Discrete(2)` | upstream_code | controllers/gym_controller/gym_controller.py:32 |
| The position threshold is 0.3 and the pole-angle threshold is 0.2 rad; the observation upper bound is twice each threshold for the position and angle entries and float32 maximum for the two velocity entries | upstream_code | controllers/gym_controller/gym_controller.py:21-33 |
| Each action sets all four wheel target velocities to 1.3 rad/s when the action is 1 and to -1.3 rad/s otherwise | upstream_code | controllers/gym_controller/gym_controller.py:76-77 |
| The observation is [robot position z, robot velocity z, position-sensor value, `POLE_ENDPOINT` angular velocity z] | upstream_code | controllers/gym_controller/gym_controller.py:81-84 |
| The episode is done when the position or the pole angle passes its threshold | upstream_code | controllers/gym_controller/gym_controller.py:87-92 |
| The reward is 0 on the step that reports done and 1 otherwise | upstream_code | controllers/gym_controller/gym_controller.py:94-95 |
| `reset` restarts the simulation physics and the world, then rebinds the four wheels and the position sensor | upstream_code | controllers/gym_controller/gym_controller.py:50-66 |
| `reset` takes no seed or options and returns a fixed four-zero observation | upstream_code | controllers/gym_controller/gym_controller.py:50-72 |
| `step` returns the legacy four-tuple `(state, reward, done, info)` | upstream_code | controllers/gym_controller/gym_controller.py:97 |
| The constructor default `max_episode_steps` is 1000 and is stored in `EnvSpec(id='WebotsEnv-v0')`; `reset` and `step` never enforce a time limit or truncate | upstream_code | controllers/gym_controller/gym_controller.py:17-35 |
| The world file is a Webots R2021a world | upstream_code | worlds/webotsgym.wbt:1 |
| The world places a `Pioneer3at` with controller `gym_controller` and `supervisor TRUE` | upstream_code | worlds/webotsgym.wbt:13-15 |
| The balancing pole is attached through a `HingeJoint` with a `PositionSensor` | upstream_code | worlds/webotsgym.wbt:17-26 |
| The pole is a 0.5 m cylinder with a 0.1 m ball at `POLE_ENDPOINT` whose mass is 0.2 kg | upstream_code | worlds/webotsgym.wbt:31-56 |

Limits: the driver declares none. The only action bound is the environment's `Discrete(2)` space, which the
Gymnasium bridge derives (`action.index` 0 to 1, source `upstream_code`, ref
`controllers/gym_controller/gym_controller.py:32`); `ticks` is bounded by the bridge's `max_ticks` (1 to 10000). The
device is simulated (R0), so no bound is `operator_required` and no `site-limits.example.json` is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:webots-gym-example`, level F0 (an analytic
transition per step, no rigid-body dynamics claim), determinism `exact` for the fake's fixed zero start and same
action sequence, `timestep_ms` 0 because the Webots basic time step is not stated in the clone, `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps state what is not modelled and that the fake was
never compared with a Webots run. The upstream Webots physics itself would be an F1 claim, but it is not the model this
package deploys on the checked backend.

Mock path: `backends = {"fake": ".fake:FakeWebotsStickEnv"}`. The fake is pure Python and mirrors the upstream
`reset`/`step` semantics (fixed zero reset, legacy four-tuple, wheel direction, thresholds, reward) with placeholder
analytic constants. No `sim` backend is offered because the class is not registered with `gymnasium.make` and its
`Supervisor` base exists only inside Webots. The Webots path was never run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the upstream class has no native stop);
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: webots, pioneer3at, inverted-pendulum, reinforcement-learning, simulation, gymnasium, legacy-gym
