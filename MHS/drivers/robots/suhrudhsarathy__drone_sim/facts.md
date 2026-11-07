# Facts and tags for gh.suhrudhsarathy/drone_sim

Every fact cites its source at commit `1a324f178a5719676bdb0caaa2a2d545a7158fdd`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment class SimpleDroneEnv subclasses gym.Env | upstream_code | drone_sim/gym/simple_drone_env.py:11 |
| The action space is a Box of four float32 values in [0, 1] | upstream_code | drone_sim/gym/simple_drone_env.py:35 |
| The observation space is a Box of shape (3, 3) whose low and high are both -inf | upstream_code | drone_sim/gym/simple_drone_env.py:30-36 |
| The environment constructs Drone(0, 0, 2, enable_death=False) and sets init_position to [0, 0, 2] | upstream_code | drone_sim/gym/simple_drone_env.py:19-28 |
| The environment stores the module constant NULL_ROT and step multiplies the action by it before Drone.step | upstream_code | drone_sim/gym/simple_drone_env.py:40-46 |
| NULL_ROT = 620.2943 | upstream_code | drone_sim/sim/parameters.py:15 |
| Drone.step maps four values to w1 = v0, w2 = -v1, w3 = v2, w4 = -v3 and then calls update | upstream_code | drone_sim/sim/drone.py:117-122 |
| The observation has three rows: [x, y, z], [ax, ay, az] and [p, q, r] | upstream_code | drone_sim/gym/simple_drone_env.py:50-56 |
| The reward is 1 - dist(current, init_position) / dist(goal_position, init_position) | upstream_code | drone_sim/gym/simple_drone_env.py:58-62 |
| A roll or pitch beyond 60 degrees or a z below 0 sets done, resets the drone and subtracts 5 from the reward; a distance below 0.01 from init_position sets done and adds 10 | upstream_code | drone_sim/gym/simple_drone_env.py:64-78 |
| Step returns (observation, reward, done, info), the legacy four-value API | upstream_code | drone_sim/gym/simple_drone_env.py:84 |
| Reset takes no seed and no options; it calls Drone.__reset__ and returns the observation | upstream_code | drone_sim/gym/simple_drone_env.py:86-97 |
| Drone.__reset__ restores the position (0, 0, 0.5) and zeroes the angles, velocities and p, q, r | upstream_code | drone_sim/sim/drone.py:101-115 |
| The simulation advances by a fixed step DT = 0.004 between updates | upstream_code | drone_sim/sim/parameters.py:4 |
| The drone parameters are mass 0.468, K = 2.980e-6, B = 1.140e-7, L = 0.225 and G = 9.8 | upstream_code | drone_sim/sim/parameters.py:8-13 |
| The inertia is IXX = IYY = 4.856e-3 and IZZ = 8.801e-3 | upstream_code | drone_sim/sim/parameters.py:18-20 |
| The drag coefficients are AX = AY = AZ = 0.25 | upstream_code | drone_sim/sim/parameters.py:23-25 |
| Thrust is K times the sum of the four squared rotor speeds along body z | upstream_code | drone_sim/sim/drone.py:163-169 |
| The torque is [L*K*(w1^2-w3^2), L*K*(w2^2-w4^2), B*(w1^2-w2^2+w3^2-w4^2)] | upstream_code | drone_sim/sim/drone.py:171-177 |
| Acceleration is gravity plus (1/mass) times the rotated thrust plus (1/mass) times the drag force | upstream_code | drone_sim/sim/drone.py:183-185 |
| p, q and r are overwritten with the angular acceleration from the inertia and the torque | upstream_code | drone_sim/sim/drone.py:187-197 |
| update integrates with Euler steps: angle += angular velocity*DT, velocity += acceleration*DT and position += the updated velocity*DT | upstream_code | drone_sim/sim/drone.py:209-228 |
| normalise_theta keeps an angle in the -pi to pi range | upstream_code | drone_sim/sim/drone.py:231-241 |

Limits: the driver declares none of its own. The only action bound is derived by the Gymnasium bridge from the
environment's action space `Box(low=0, high=1, shape=(4,))` (`simple_drone_env.py:35`): every element of
`action.values` is bounded 0 to 1. `ticks` is bounded 1 to the bridge's `max_ticks` (10000). The device is simulated
(R0), so no limit is `operator_required` and there is no site-limit overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `custom:drone_sim.sim.drone`, level F1 (rigid-body
dynamics with an ideal rotor-to-thrust and rotor-to-torque mapping), determinism `seeded` with `seed_control`
`parameter` (the upstream reset() takes no seed and restores a fixed state, so the seed is recorded but does not
change the trajectory), timestep 4 ms (`DT = 0.004`, `parameters.py:4`), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say what is not modelled and that this package's fake was not
compared with an upstream run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. There is no hardware backend and no independent hardware stop to cite.

Tags: drone, quadcopter, rigid-body, reinforcement-learning, simulation, gym
