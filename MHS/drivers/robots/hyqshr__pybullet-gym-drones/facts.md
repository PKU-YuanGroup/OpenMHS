# Facts and tags for gh.hyqshr/pybullet-gym-drones

Every fact cites its source at commit `19a318c92914402d57a4dc9d1cb28cb72db268b3`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DroneNavigation-v0 is registered with id 'DroneNavigation-v0' and entry point 'drone_envs.envs:DroneNavigationV0' | upstream_code | drone_envs/__init__.py:2-5 |
| The action space is a 3-element Box with low [-0.1, -0.1, -0.1] and high [0.1, 0.1, 0.1] | upstream_code | drone_envs/envs/drone_env_v0.py:24-27 |
| The observation space is 9 elements: drone x and y in [-12, 12], z in [0, 12], each velocity in [-3, 3], goal x and y in [-9, 9] and goal z in [0, 9] | upstream_code | drone_envs/config.py:14-33 |
| A step applies the action, advances the pybullet simulation, reads the drone observation and returns the observation concatenated with the goal, the reward, done and reach_target | upstream_code | drone_envs/envs/drone_env_v0.py:64-76 |
| The simulation timestep is set to 1/30 s | upstream_code | drone_envs/envs/drone_env_v0.py:51-53 |
| Each thrust component is clipped to [-0.1, 0.1] and applied as an external force to link 4 in the link frame | upstream_code | drone_envs/resources/drone.py:19-35 |
| The drone is loaded at base position [0, 0, 0.1] | upstream_code | drone_envs/resources/drone.py:10-14 |
| The drone base link mass is 0.027 kg | upstream_code | drone_envs/resources/drone.urdf:11 |
| The drone observation is the base position followed by the base linear velocity | upstream_code | drone_envs/resources/drone.py:38-49 |
| A reset resets the simulation, reloads the plane and drone, draws a new goal and returns the initial observation | upstream_code | drone_envs/envs/drone_env_v0.py:82-97 |
| The goal is drawn with x and y uniform in [5, 9] or [-9, -5] and z uniform in [5, 9] | upstream_code | drone_envs/envs/drone_env_v0.py:135-142 |
| The reward is the decrease in distance to the goal; leaving x or y at +-12 or z at or below 0 or at or above 12 subtracts 1 and ends the episode, and a distance below 2 adds 50 and sets reach_target | upstream_code | drone_envs/envs/drone_env_v0.py:148-168 |
| seed() reseeds the environment random generator from gym.utils.seeding.np_random and returns the seed | upstream_code | drone_envs/envs/drone_env_v0.py:78-80 |
| The upstream run script creates the environment with gym.make(env_name) | upstream_code | run.py:87-92 |
| The project is a PyBullet and OpenAI Gym environment | vendor_doc | README.md:3 |

Limits: the driver declares none. The only input bounds are the upstream action space, which the bridge derives from
the environment (`Box` low `[-0.1, -0.1, -0.1]` and high `[0.1, 0.1, 0.1]`, so `action.values` is bounded per element),
and the bridge's `ticks` input (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is
`operator_required` and there is no operator overlay (`site-limits.example.json` is not needed).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic`, level F0 (a kinematic point-mass stand-in with
no rigid-body dynamics, contacts, gravity, drag, actuator, sensor or noise model), determinism `seeded` with
`seed_control` `parameter`, timestep 1000/30 ms (`1/30` s, `drone_env_v0.py:53`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say that the checked fake is not the upstream pybullet
model, that it was never compared with it, and that DroneNavigation-v1 and rendering are not covered.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: drone, navigation, reinforcement-learning, simulation, pybullet, gym

Coverage: this package serves DroneNavigation-v0 only. The second registered environment, DroneNavigation-v1
(`drone_envs/__init__.py:7-10`), adds a 16 x 16 camera and 30 obstacle cubes and would need its own driver and fake.
The upstream pybullet simulator was not run: the clone is read-only, its dependencies are not installed where the gate
ran, and package code never imports or runs it. The fake's trajectories were not compared with the upstream model.
