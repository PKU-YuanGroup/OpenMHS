# Facts and tags for gh.nickgeramanis/gym-navigation

Every fact cites its source at commit `98be757c6aa2b2834cecbb7dde3c2c05e5f1b57b`. `upstream_code` is a code or
comment line of the clone; the same facts are written into `driver.py` (`facts = [...]`), and the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| NavigationTrack-v0 is registered with entry point gym_navigation.envs.navigation_track:NavigationTrack | upstream_code | gym_navigation/__init__.py:4-6 |
| The action space is Discrete(3): one integer per Action enum member | upstream_code | gym_navigation/envs/navigation_track.py:46 |
| The three actions are FORWARD (0, linear shift 0.2 m, angular 0), ROTATE_RIGHT (1, 0.04 m, 0.2 rad) and ROTATE_LEFT (2, 0.04 m, -0.2 rad) | upstream_code | gym_navigation/enums/action.py:21-23 |
| The observation is five range measurements at -pi/2, -pi/4, 0, pi/4 and pi/2 from the heading | upstream_code | gym_navigation/envs/navigation_track.py:30-34 |
| The scan range constants are 30.0 maximum and 0.2 minimum | upstream_code | gym_navigation/envs/navigation_track.py:31-32 |
| The observation space is a Box of N_OBSERVATIONS = N_MEASUREMENTS (5) elements whose high and low are the scan range constants | upstream_code | gym_navigation/envs/navigation_track.py:48-51 |
| The shift and sensor noise standard deviations are 0.02 | upstream_code | gym_navigation/envs/navigation_track.py:21-22 |
| Each action draws Gaussian noise N(0, 0.02) for the angular and the linear shift, moves the pose and then rotates it | upstream_code | gym_navigation/envs/navigation_track.py:53-60 |
| Positions and ranges are in metres: the renderer maps 1 m to 20 pixels | upstream_code | gym_navigation/envs/navigation.py:25-26 |
| The yaw is measured from the y axis in [-pi, pi], positive clockwise | upstream_code | gym_navigation/geometry/pose.py:74-81 |
| The collision threshold is 0.4 m | upstream_code | gym_navigation/envs/navigation_track.py:24 |
| The episode terminates when any scan range is below the collision threshold | upstream_code | gym_navigation/envs/navigation_track.py:102-106 |
| The collision reward is -200.0, the forward reward +5.0 and the rotation reward -0.5 | upstream_code | gym_navigation/envs/navigation_track.py:26-28 |
| The reward is the collision reward on a collision, the forward reward for FORWARD and the rotation reward otherwise | upstream_code | gym_navigation/envs/navigation_track.py:108-116 |
| A reset restores the world from the track walls and returns the observation and an info dict | upstream_code | gym_navigation/envs/navigation.py:89-102 |
| A reset draws one spawn area, x and y uniformly inside it and the yaw uniformly in [-pi, pi] | upstream_code | gym_navigation/envs/navigation_track.py:125-131 |
| step always returns truncated False | upstream_code | gym_navigation/envs/navigation.py:60 |
| NavigationTrack reports an empty info dict | upstream_code | gym_navigation/envs/navigation_track.py:122-123 |
| The track model is TRACK1, twelve wall segments and six spawn areas | upstream_code | gym_navigation/enums/track.py:26-49 |

Limits: the driver declares none. The only input bound is the action space, which the bridge derives from the
environment (`Discrete(3)`: `action.index` from 0 to 2, with no source and the ref
`action_space of the fake backend .fake:FakeNavigationTrack`), and `ticks` (1 to `max_ticks`, 10000 by default) from
the bridge's step schema. The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:NavigationTrack-v0`, level F0 (kinematic
geometry, no dynamics or contacts), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 0 (the
environment declares no step interval; a tick is one transition), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled and that this package's fake was not compared
with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: navigation, 2d, ray-casting, reinforcement-learning, simulation, gymnasium
