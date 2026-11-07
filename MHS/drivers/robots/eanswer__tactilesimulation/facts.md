# Facts and tags for gh.eanswer/tactilesimulation

Every fact cites the clone at commit `0c42783a8b5cc7abe1a9fa3e6aa65e4aeb8eb670`. The same facts are written into
`driver.py` (`facts = [...]`); the reference files are generated from the driver, not from this page. The package
serves the **TactilePush-v1** environment; the card's other three environments (StableGrasp-v1, TactileRotation-v1,
Insertion-v3) are separate environments of the same family and are not covered by this one `env_id`.

| fact | source | ref |
|---|---|---|
| TactilePush-v1 is registered with entry point envs.tactile_push_env:TactilePushEnv and max_episode_steps=100 | upstream_code | envs/__init__.py:9-13 |
| The constructor takes observation_type and defaults it to tactile_map | upstream_code | envs/tactile_push_env.py:21 |
| In tactile_flatten mode the tactile observation is a 390-number vector and the state observation has 3 numbers | upstream_code | envs/tactile_push_env.py:34-36 |
| In tactile_flatten mode the observation is the state numbers followed by the tactile vector | upstream_code | envs/tactile_push_env.py:114-119 |
| The state part of the observation is the goal position in the gripper frame (2 numbers) and the goal rotation relative to the gripper (1 number) | upstream_code | envs/tactile_push_env.py:83-106 |
| The action space is a Box with low -1 and high 1 for each of 3 control inputs | upstream_code | envs/tactile_push_env.py:69-70 |
| step applies tanh to the action and uses its first three components as the robot controls | upstream_code | envs/tactile_push_env.py:174-182 |
| frame_skip is 5 and dt is sim.options.h multiplied by frame_skip | upstream_code | envs/tactile_push_env.py:66-67 |
| The model integration timestep is 5e-3 s (5 ms) | upstream_code | envs/assets/pusher/pusher.xml:2 |
| A reset sets state_q[1] to -0.001 and draws state_q[4] uniformly from -0.02 to 0.02 | upstream_code | envs/tactile_push_env.py:134-136 |
| A reset draws the goal x from 0.15 to 0.25, the goal y from -0.2 to 0.2, and the goal rotation uniformly from goal_y*pi - pi/16 to goal_y*pi + pi/16 | upstream_code | envs/tactile_push_env.py:143-146 |
| Every tenth step draws a random force probability uniformly from 0 to 1 and, when it is below 0.5, an external force uniformly from -1 to 1 on each axis, otherwise zero | upstream_code | envs/tactile_push_env.py:184-193 |
| The reward is reward_pos + reward_rot + reward_touch + reward_action, built from the object-to-goal position and rotation errors, the contact variable difference and the squared action | upstream_code | envs/tactile_push_env.py:202-211 |
| step returns the observation, the reward, False and an info object with the reward components and the final position and rotation errors | upstream_code | envs/tactile_push_env.py:216-232 |
| The base class seeds with gym.utils.seeding.np_random and returns the seed as a list | upstream_code | envs/redmax_torch_env.py:48-50 |

The driver sets `env_kwargs = {"observation_type": "tactile_flatten"}`: the family bridge carries one observation
value, and the default `tactile_map` observation is a tuple. The constructor option is upstream's own
(`envs/tactile_push_env.py:21`), so the real `gym.make` path and the fake serve the same flat 393-number observation
(3 state numbers followed by 390 tactile numbers). The fake is kinematic and its tactile numbers are placeholders.

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1, 1)` per control input: `action.values[*]` from -1 to 1, with the source `upstream_code` and the ref
`envs/tactile_push_env.py:69-70`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so
no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:tactilesimulation/TactilePush-v1`, level F0
(the delivered fake is a kinematic stand-in with no dynamics; the upstream environment is a DiffRedMax rigid-body
contact simulation, F1), determinism `seeded` with `seed_control` `parameter`, timestep 25 ms (frame_skip 5 at the
5 ms model timestep: `envs/tactile_push_env.py:66-67` and `envs/assets/pusher/pusher.xml:2`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, including the absence of
force integration and contacts, the 390-number placeholder tactile vector and the difference between Python's
`random.Random` and the upstream numpy generator.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware backend is
declared and none was run.

Tags: tactile, pushing, reinforcement-learning, simulation, gymnasium, differential-simulation
