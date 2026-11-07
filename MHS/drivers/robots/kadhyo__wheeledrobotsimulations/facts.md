# Facts and tags for gh.kadhyo/wheeledrobotsimulations

Every fact cites its source at commit `821f75691403aa92d683c4fe7c080933dea72bf6`. The same facts are in
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves `kitchen-v1` only. `kitchen-v0` registers `assets/kitchen.xml` (`fastsim/gym_fastsim/__init__.py:15-16`),
whose map is `cuisine.pbm` (`fastsim/gym_fastsim/assets/kitchen.xml:5`); the clone's asset directory has
`fastsim/gym_fastsim/assets/kitchen.pbm`, not `cuisine.pbm`, so `kitchen-v0` is not a working scene. `kitchen-v1`
registers the same scene with the ten range-1 lasers (`fastsim/gym_fastsim/__init__.py:17-18`,
`fastsim/gym_fastsim/assets/kitchen_lasers.xml:5-20`).

| fact | source | ref |
|---|---|---|
| SimpleNavEnv subclasses gym.Env | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:66 |
| step unpacks its action into v1 and v2, the left and right wheel velocities | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:186-188 |
| maxVel is 4, the value used in the C++ sferes2 experiment | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:86 |
| step clips both motor orders to -maxVel through +maxVel before moving the robot | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:190-191 |
| The action space is Box(low=-maxVel, high=maxVel, shape=(2,), dtype=float32) | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:120-121 |
| The observation-space high array is maxSensorRange repeated n_lasers, then 1.0 repeated twice, then 1.0 repeated n_lightsensors; low is 0.0 repeated n_lasers, 0.0 repeated twice and -1 (or 0 in realistic mode) repeated n_lightsensors | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:118-119 |
| get_all_sensors returns only the laser ranges: the bumper and light-sensor terms are commented out | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:182-184 |
| get_laserranges maps a negative laser distance to maxSensorRange and clips the rest to 0..maxSensorRange | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:143-156 |
| maxSensorRange is the first laser's range, or 0 when the robot has no laser | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:89-95 |
| step calls robot.move(left, right, map, sticky_walls) once with the clipped motor orders | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:193-194 |
| step sets episode_over to dist_obj <= goal.get_diam(), the goal's full diameter | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:209-210 |
| step returns the legacy 4-tuple (sensors, reward, episode_over, info) with info dist_obj and robot_pos | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:212 |
| The default reward_func is binary_goalbased | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:67 |
| binary_goalbased returns 1.0 when the goal distance is at most goalRadius and 0.0 otherwise | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:33-39 |
| goalRadius is half the goal diameter | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:114-116 |
| The other reward functions are minimize_energy (minus the sum of the absolute motor orders), displacement (distance from the previous position) and none (0) | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:42-63 |
| reset restores the initial pose, zeroes both motor orders and returns get_all_sensors(); it draws no random number and takes no seed | upstream_code | fastsim/gym_fastsim/simple_nav/nav_env.py:217-223 |
| kitchen_env is assets/kitchen.xml | upstream_code | fastsim/gym_fastsim/__init__.py:9 |
| kitchen_lasers_env is assets/kitchen_lasers.xml | upstream_code | fastsim/gym_fastsim/__init__.py:10 |
| kitchen-v0 is registered with entry_point gym_fastsim.simple_nav:SimpleNavEnv and kwargs xml_env=join(dirname(__file__), kitchen_env) | upstream_code | fastsim/gym_fastsim/__init__.py:15-16 |
| kitchen-v1 is registered with entry_point gym_fastsim.simple_nav:SimpleNavEnv and kwargs xml_env=join(dirname(__file__), kitchen_lasers_env) | upstream_code | fastsim/gym_fastsim/__init__.py:17-18 |
| kitchen_lasers.xml places the robot at x=2, y=4, theta=0, the goal at x=0.5, y=0.5 with diameter 0.2, and ten lasers of range 1 | upstream_code | fastsim/gym_fastsim/assets/kitchen_lasers.xml:6-20 |
| kitchen_lasers.xml names the map kitchen.pbm | upstream_code | fastsim/gym_fastsim/assets/kitchen_lasers.xml:5 |
| assets/kitchen.xml names the map cuisine.pbm | upstream_code | fastsim/gym_fastsim/assets/kitchen.xml:5 |
| The first simulation environment is based on the fast simulation library libfastsim | vendor_doc | README.md:5 |

Limits: the driver declares no hand-written Limit. The only bound is the environment's action space, which the
Gymnasium bridge derives from the configured environment object (`Box(low=-4, high=4, shape=(2,))`,
`nav_env.py:120-121`): each of `action.values` is from -4 to 4, with no source and the bridge reference
`action_space of the fake backend .fake:FakeSimpleNavEnv`. The device is simulated (R0), so no limit is
`operator_required` and there is no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `libfastsim:kitchen-v1`, level F0 (the checked fake is a
kinematic stand-in and models no rigid-body dynamics, contacts, actuators or sensors), determinism `seeded` with
`seed_control` `parameter` (the upstream reset restores a fixed pose and draws no random number), `timestep_ms` 0
(the clone states no integration interval; one tick is one `robot.move` call), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps name the kinematic stand-in, the observation-space mismatch, the
unused seed, the reward/terminal rule, the missing rendering and info fields, and the absence of a physical device.

Safety: simulated R0 world. There is no hardware backend and no native stop; the e-stop is the runtime's software latch.
After it, no step or reset is accepted until `mhs.safety.reset` clears the latch, and the world state stays readable.

Tags: wheeled-robot, navigation, laser, reinforcement-learning, simulation, gym, libfastsim
