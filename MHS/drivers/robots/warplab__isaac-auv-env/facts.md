# Facts and tags for gh.warplab/isaac-auv-env

Every fact cites its source at commit `7c5ebe7f7a08acd2570b5fba328e92b7f59f6794` as `upstream_code` (a path in the
clone and the line that shows the claim). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The task registers the Gymnasium id Isaac-WarpAUV-Direct-v1 with WarpAUVEnv as its entry point | upstream_code | __init__.py:19-21 |
| The registration disables the Gymnasium environment checker | upstream_code | __init__.py:22 |
| WarpAUVEnv is a DirectRLEnv subclass | upstream_code | warpauv_env.py:129 |
| The action space is Box(-1.0, 1.0, shape=(6,)): six continuous inputs in the range -1.0 to 1.0 | upstream_code | warpauv_env.py:71 |
| The six actions are PWM commands between -1 and 1, one per thruster | upstream_code | warpauv_env.py:401-410 |
| The observation space is Box(-inf, inf, shape=(17,)) | upstream_code | warpauv_env.py:70 |
| The observation concatenates the goal, the offset from the origin in the body frame, the root quaternion, the body-frame linear velocity and the body-frame angular velocity | upstream_code | warpauv_env.py:248-257 |
| The simulation physics timestep is 1/120 s | upstream_code | warpauv_env.py:61 |
| The configuration sets decimation = 2 | upstream_code | warpauv_env.py:74 |
| The episode length cap is enabled with episode_length_s = 3.0 | upstream_code | warpauv_env.py:75-76 |
| The configuration enables boundaries with max_auv_x = 7, max_auv_y = 7 and max_auv_z = 7 | upstream_code | warpauv_env.py:81-84 |
| The done flags returned by _get_dones are the out-of-bounds flags and the time-out flags | upstream_code | warpauv_env.py:283-304 |
| starting_depth is 8 | upstream_code | warpauv_env.py:85 |
| The robot's initial position is (0.0, 0.0, starting_depth) | upstream_code | warpauv_env.py:213 |
| goal_spawn_radius is 2.0 | upstream_code | warpauv_env.py:91 |
| A reset offsets the initial position by a sample from a sphere of radius goal_spawn_radius | upstream_code | warpauv_env.py:316-318 |
| A reset draws the goal orientation from a random orientation | upstream_code | warpauv_env.py:346-348 |
| Actions are clipped to the range -1 to 1 before the dynamics are computed | upstream_code | warpauv_env.py:227-232 |
| Thruster commands with absolute value below 0.08 are zeroed; from 0.08 upward the command is converted by -139*v^2 + 500*v + 8.28 and from -0.08 downward by 161*v^2 + 517.86*v - 5.72 | upstream_code | warpauv_env.py:408-410 |
| rotor_constant is 0.1/100.0 | upstream_code | warpauv_env.py:111 |
| The rotor force conversion returns rotorConstant * abs(value) * value | upstream_code | thruster_dynamics.py:141 |
| The first-order rotor time constant is 0.05 s | upstream_code | warpauv_env.py:112 |
| The rotor update sets alpha to zero so the state follows the command | upstream_code | thruster_dynamics.py:110-115 |
| The dynamics allocate six thrusters per environment | upstream_code | warpauv_env.py:209 |
| The water density is 997.0 kg/m^3 and the dynamic viscosity is 0.001306 Pa s | upstream_code | warpauv_env.py:109-110 |
| The AUV mass is 22.701 kg and the volume is 0.022747843530591776 m^3, which the comment describes as neutrally buoyant | upstream_code | warpauv_env.py:113-115 |
| The inertia tensor used by the dynamics is (0.37, 0.97, 1.19) | upstream_code | warpauv_env.py:174-176 |
| The centre-of-buoyancy offset is [0.0, 0.0, 0.01] m | upstream_code | warpauv_env.py:108 |
| The quadratic drag force on each body axis is -2*rho*rj*rk*abs(v)*v and the viscous force is -6*beta*pi*r_eq*v | upstream_code | rigid_body_hydrodynamics.py:68-90 |
| The reward scales are position 0.2, angle 0.5 and actions 0.2, with linear velocity, angular velocity and terminated at 0.0 | upstream_code | warpauv_env.py:96-105 |
| The total reward is the sum of the angular, action, position and angular-velocity terms | upstream_code | warpauv_env.py:607 |

Limits: the driver declares none of its own. The only bound is the environment's action space, which the bridge
derives from the live Box (`action.values` from -1.0 to 1.0 per element, sourced `upstream_code` from
`warpauv_env.py:71`), plus the bridge's `ticks` schema (1 to `max_ticks`, 10000 by default). The device is simulated
R0, so no limit is `operator_required` and no site overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:Isaac-WarpAUV-Direct-v1`, level F0 (a reduced
analytic model: thrust, drag and a point-mass/quaternion integration, with no contact solver), determinism `seeded`
with `seed_control` `parameter`, timestep 1/120 s = 8.333 ms (`warpauv_env.py:61`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake is not IsaacSim/PhysX, that the
upstream runs two physics substeps per control step while the fake runs one, that the clone configures four parallel
environments while the fake serves one, that neutral buoyancy is assumed, and that the fake was not compared with an
upstream run.

Safety: simulated R0 device. The runtime's software latch is the stop; the environment exposes no native stop, so
after an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays
readable. There is no physical e-stop, no watchdog and no hazard on a simulated world; no hardware backend exists.

Tags: auv, underwater, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium
