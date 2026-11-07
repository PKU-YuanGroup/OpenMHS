# Facts and tags for gh.jr-robotics/robo-gym

Every fact cites its source at commit `f086bc90068c41ffd1889d290f3766d69291bf26`: `upstream_code` is a code or
comment line of the clone (`path/in/clone.py:LINE` or a line range). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ExampleEnvSim-v0 is registered with entry point robo_gym.envs:ExampleEnvSim | upstream_code | robo_gym/__init__.py:6-9 |
| ExampleEnvSim sets cmd to `roslaunch example_robot_server robot_server.launch` and starts the simulation through the Simulation wrapper | upstream_code | robo_gym/envs/example/example_env.py:227-232 |
| Simulation starts the simulated robot server with `sm_client.start_new_server(cmd=self.cmd, gui=self.gui)` | upstream_code | robo_gym/envs/simulation_wrapper.py:56-64 |
| ExampleEnv declares max_episode_steps = 300 | upstream_code | robo_gym/envs/example/example_env.py:25 |
| The action space is a Box of two elements, each from -1.0 to 1.0 | upstream_code | robo_gym/envs/example/example_env.py:224 |
| The observation space is a Box of four unbounded elements | upstream_code | robo_gym/envs/example/example_env.py:211-214 |
| The environment state is [pos_x, pos_y, lin_vel, ang_vel] taken from the robot server state dictionary | upstream_code | robo_gym/envs/example/example_env.py:192-198 |
| reset takes options.position as the initial [x, y], asserts exactly two elements and defaults to [0, 0] | upstream_code | robo_gym/envs/example/example_env.py:67-73 |
| reset writes the initial state to the robot server and reads it back; every reset requires the client created from rs_address | upstream_code | robo_gym/envs/example/example_env.py:86-99 |
| step increments elapsed_steps, rejects an action outside the action space, sends action.tolist() to the robot server and returns (state, reward, done, False, info) | upstream_code | robo_gym/envs/example/example_env.py:119-147 |
| reward returns 0 and done=True with info final_status `max_steps_exceeded` once elapsed_steps reaches max_episode_steps | upstream_code | robo_gym/envs/example/example_env.py:109-117 |
| Simulation.close kills the simulated robot server when one is running | upstream_code | robo_gym/envs/simulation_wrapper.py:89-108 |

## Limits

The driver declares no Limit of its own. The only action bound is the Box the environment publishes
(`-1.0` to `1.0` for each of the two action `values`), which the Gymnasium bridge derives from the fake's
`action_space` and enforces before `step` with source `upstream_code` and ref
`robo_gym/envs/example/example_env.py:224`. The catalogue classes also bound `ticks` to 1 to 10000 and `seed` to
non-negative integers. The device is simulated (R0), so no limit is `operator_required` and there is no
`site-limits.example.json`.

## Fidelity contract

`driver.py` `fidelity`: engine `robo-gym:ExampleEnvSim-v0 (external robot server and Gazebo not included)`, level F0
(kinematic placeholder, no dynamics), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 0 (the
clone declares no fixed timestep; the external server owns it), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot/restore. The gaps say that no dynamics, contacts, sensors, noise or wall-clock pacing are modelled, that
the fake was not compared with the external robot server, and that nothing was validated against a physical device.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it no step or reset is accepted until
`mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state stays readable. The
package has no hardware backend and no path to a physical machine.

Tags: robo-gym, gymnasium, simulation, example environment, reinforcement learning, robot server
