# Facts and tags for gh.greg-lund/gym-social-navigation

Every fact cites its source at commit `bdc8e72c0f7f738ebe99b6966b1c37af26a342af`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package registers social-nav-train-env-v0 with kwargs test=False and social-nav-test-env-v0 with kwargs test=True; both use the entry point gym_social_navigation.envs:SocialNavEnv | upstream_code | gym_social_navigation/__init__.py:3-12 |
| The environment uses data from the ETH Pedestrian dataset | vendor_doc | README.md:3 |
| The test flag selects the data/val files; otherwise the data/train files are used | upstream_code | gym_social_navigation/envs/social_nav_env.py:31-38 |
| The robot keeps 3 previous states per agent, tracks at most 4 agents within a 10-unit proximity radius, uses 4 path points and requires a normalised start-goal distance of at least 0.45 | upstream_code | gym_social_navigation/envs/social_nav_env.py:11-18 |
| The maximum robot velocity is 0.75 m/s, velocity is discretised by 0.25 m/s and the fixed steering angle is 30 degrees | upstream_code | gym_social_navigation/envs/social_nav_env.py:12-14 |
| An episode lasts 60 s | upstream_code | gym_social_navigation/envs/social_nav_env.py:19 |
| The dataset timestep is 0.4 s and the episode time is divided by it to give the step limit | upstream_code | gym_social_navigation/envs/social_nav_env.py:51-52 |
| The observation space is a Box of 3 + 2*num_agents*(agent_hist+1) + 2*num_path_points values with low 0 and high 1 | upstream_code | gym_social_navigation/envs/social_nav_env.py:55-58 |
| The action list has three left actions, four straight actions (including speed 0) and three right actions; the action space is Discrete(len(actions)) | upstream_code | gym_social_navigation/envs/social_nav_env.py:59-60 |
| The reward weights are alpha 3.5 for the change in path distance and beta 5 for the change in goal distance; the goal reward is 10, the collision penalty 20 and the out-of-bounds penalty 15 | upstream_code | gym_social_navigation/envs/social_nav_env.py:22-26 |
| The goal threshold is 0.05 and the collision distance is 0.30 | upstream_code | gym_social_navigation/envs/social_nav_env.py:27-28 |
| A reset picks a random dataset, a random start time and a random start and goal position | upstream_code | gym_social_navigation/envs/social_nav_env.py:192-205 |
| Step moves the pose with the fixed steering angle and timestep, then computes the reward from the change in goal distance and path distance | upstream_code | gym_social_navigation/envs/social_nav_env.py:224-263 |
| A collision ends the episode with -collision_penalty, reaching the goal with goal_reward, the time limit with the current reward and leaving the unit square with -out_of_bounds_penalty | upstream_code | gym_social_navigation/envs/social_nav_env.py:266-292 |
| The class derives from gym.Env | upstream_code | gym_social_navigation/envs/social_nav_env.py:1-6 |
| The observation and action spaces are gym.spaces.Box and gym.spaces.Discrete | upstream_code | gym_social_navigation/envs/social_nav_env.py:58-60 |

Limits: the driver declares none. The action bound (`action.index` 0 to 9) and the `ticks` bound (1 to 10000) are
derived by the Gymnasium bridge from the fake environment's `Discrete(10)` action space and the bridge's
`max_ticks`; the bridge gives the action bound no source and the ref
`action_space of the fake backend .fake:FakeSocialNavEnv`, and neither bound is a driver `Limit`. The device is
simulated (R0), so there is no operator-required bound. The upstream action list is built from `dv` and `max_vel` in
`social_nav_env.py:59`; the fake reproduces the same ten values.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym:social-nav-train-env-v0`, level F0 (kinematic pose
updates and a canned pedestrian trace; no contacts, forces, actuator, sensor or noise model), determinism `seeded`
with `seed_control` `parameter` (the fake's `reset(seed=...)`; upstream `reset()` takes no seed or options and uses
numpy's global generator, `social_nav_env.py:186`), timestep 400 ms (`social_nav_env.py:51`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The driver sets `autoreset = True`, so a step after a terminal
state resets the world and starts a new episode (upstream requires an explicit `reset()`). The gaps say what is not
modelled, that the pedestrian trace is synthetic test data rather than the ETH dataset, and that no rendering or
wall-clock pacing is provided.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. There is no hardware
backend and no hardware claim.

Tags: social-navigation, pedestrian, dubins-car, reinforcement-learning, simulation, gym
