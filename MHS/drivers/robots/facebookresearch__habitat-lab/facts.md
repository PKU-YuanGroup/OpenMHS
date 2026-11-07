# Facts and tags for gh.facebookresearch/habitat-lab

Every fact cites its source at commit `0fb6f43ffe806a8088a171b036336c093bcf604e`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| GymHabitatEnv is a gym.Wrapper that builds an RLTaskEnv and wraps it in HabGymWrapper to expose the standard Gym API | upstream_code | habitat-lab/habitat/core/environments.py:116-128 |
| make_gym_from_config returns the gym.Env for the environment class named by habitat.env_task | upstream_code | habitat-lab/habitat/gym/gym_definitions.py:49-60 |
| Habitat-v0 is registered with entry point _make_habitat_gym_env, which takes cfg_file_path and override_options | upstream_code | habitat-lab/habitat/gym/gym_definitions.py:80-110 |
| HabGymWrapper.step returns the legacy four-value tuple (observation, reward, done, info) | upstream_code | habitat-lab/habitat/gym/gym_wrapper.py:254-281 |
| HabGymWrapper.reset resets the wrapped environment and returns its initial observation | upstream_code | habitat-lab/habitat/gym/gym_wrapper.py:316-327 |
| The wrapper flattens a continuous action space into one Box, uses Discrete(n) for a single discrete action, and Discrete(len(actions)) otherwise | upstream_code | habitat-lab/habitat/gym/gym_wrapper.py:102-123 |
| For the point-navigation test configuration the gym action space is Discrete(4) | upstream_code | test/test_gym_wrapper.py:89-112 |
| The point-navigation task defines the four actions stop, move_forward, turn_left and turn_right | upstream_code | habitat-lab/habitat/config/habitat/task/pointnav.yaml:3-7 |
| move_forward advances the agent by forward_step_size 0.25 m and the turn actions rotate it by turn_angle 10 degrees | upstream_code | habitat-lab/habitat/config/default_structured_configs.py:1791-1792 |
| The point-navigation test environment allows 500 steps per episode | upstream_code | habitat-lab/habitat/config/benchmark/nav/pointnav/pointnav_habitat_test.yaml:10 |
| The point-navigation test environment's rgb and depth sensors are 256 by 256 pixels | upstream_code | habitat-lab/habitat/config/benchmark/nav/pointnav/pointnav_habitat_test.yaml:14-20 |
| The point-goal observation is polar with dimensionality 2 | upstream_code | habitat-lab/habitat/config/default_structured_configs.py:405-406 |
| The distance_to_goal_reward measure is -(new_distance - previous_distance), the decrease of the distance to the goal | upstream_code | habitat-lab/habitat/tasks/nav/nav.py:1004-1006 |
| The depth sensor's max_depth is 10.0 | upstream_code | habitat-lab/habitat/config/default_structured_configs.py:1573 |
| habitat.env_task defaults to GymHabitatEnv | upstream_code | habitat-lab/habitat/config/default_structured_configs.py:1922 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(4)`: `action.index` from 0 to 3, with no source and the ref
`action_space of the fake backend .fake:FakeHabitatEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`, and no `site-limits.example.json` is needed: the
action space is the only bound and there is nothing to narrow.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `habitat-lab:gym.Habitat-v0`, level F0 (a kinematic,
event-driven stand-in; no contacts, actuator or sensor dynamics), determinism `seeded` with `seed_control`
`parameter`, timestep 0 (event-driven analytic model; habitat-sim's physics timestep is defined in the separate
habitat-sim repository), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say
what is not modelled, that the rgb and depth stand-ins are smaller than the 256 x 256 sensors of the test config,
and that the fake was not compared with habitat-sim.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: habitat, embodied-ai, pointnav, reinforcement-learning, simulation, gymnasium
