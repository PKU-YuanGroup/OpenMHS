# Facts and tags for gh.abrar2652/imitation-learning-aloha

Every fact cites its source at commit `4180b39b634420e614be283c9336c1a62e307499`: `upstream_code` means code or a
comment of the clone, and the ref is the path from the clone root with its line. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The served
environment is `gym_aloha/AlohaInsertion-v0` (the card's family-config entry symbol `gym_aloha.env:AlohaEnv`).

| fact | source | ref |
|---|---|---|
| gym_aloha/AlohaInsertion-v0 is registered with entry_point gym_aloha.env:AlohaEnv, max_episode_steps 300 and kwargs obs_type pixels and task insertion | upstream_code | gym-aloha/gym_aloha/__init__.py:3-10 |
| The registered environment is nondeterministic: the registration says so because even seeded rendered observations are slightly different | upstream_code | gym-aloha/gym_aloha/__init__.py:7-9 |
| For a task other than pick_and_place the action space is Box(low=-1, high=1, shape=(len(ACTIONS),), dtype=float32) | upstream_code | gym-aloha/gym_aloha/env.py:126-132 |
| ACTIONS has 14 entries: six arm targets and a normalized gripper position per arm, with the gripper 0 close and 1 open | upstream_code | gym-aloha/gym_aloha/constants.py:30-48 |
| pick_and_place uses the seven SINGLE_ARM_ACTIONS instead of the bimanual ACTIONS | upstream_code | gym-aloha/gym_aloha/env.py:119-125 |
| With obs_type pixels the observation space is a Dict with one top Box of shape (observation_height, observation_width, 3), values 0 to 255 and dtype uint8 | upstream_code | gym-aloha/gym_aloha/env.py:56-66 |
| The default observation_width is 640 and observation_height is 480 | upstream_code | gym-aloha/gym_aloha/env.py:31-34 |
| The pixels observation keeps only the top camera frame from the raw observation | upstream_code | gym-aloha/gym_aloha/env.py:188-197 |
| The simulation control timestep is DT = 0.02 seconds (50 Hz) | upstream_code | gym-aloha/gym_aloha/constants.py:5-6 |
| The insertion task loads gym_aloha/assets/bimanual_viperx_insertion.xml and the InsertionTask | upstream_code | gym-aloha/gym_aloha/env.py:162-165 |
| A reset with a seed seeds the task RNG and samples the insertion peg and socket poses from that seed | upstream_code | gym-aloha/gym_aloha/env.py:209-219 |
| The insertion reset samples the peg x uniformly from 0.1 to 0.2 and the socket x from -0.2 to -0.1, both y from 0.4 to 0.6 at z 0.05 | upstream_code | gym-aloha/gym_aloha/utils.py:18-43 |
| The insertion reward is 0, 1, 2 or 3 on the way and 4 when the pin is touched; the pin-touch check is the successful insertion | upstream_code | gym-aloha/gym_aloha/tasks/sim.py:203-222 |
| step returns the observation, reward, terminated, truncated and info; terminated is reward == 4, info is_success is the same test, and AlohaEnv itself always returns truncated False | upstream_code | gym-aloha/gym_aloha/env.py:234-247 |
| The registered max_episode_steps is 300 | upstream_code | gym-aloha/gym_aloha/__init__.py:6 |
| render returns the top camera image from the MuJoCo physics | upstream_code | gym-aloha/gym_aloha/env.py:134-152 |
| close does nothing in AlohaEnv | upstream_code | gym-aloha/gym_aloha/env.py:249-250 |

Limits: the driver declares none of its own. The only bound is the environment's action space, which the bridge
derives from the fake backend and publishes as `action.values`: 14 elements, each from -1 to 1, with the source
`upstream_code` and the ref `gym-aloha/gym_aloha/env.py:127-132` (the registration declares the environment,
`gym-aloha/gym_aloha/__init__.py:3-10`). `ticks` is bounded by the bridge's `max_ticks` (10000 by default). The device
is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym_aloha:AlohaInsertion-v0 (dm_control MuJoCo)`, level
F1 for the upstream rigid-body model, determinism `statistical` with `seed_control` `parameter` (the registration sets
`nondeterministic=True`), timestep 20 ms (`DT = 0.02` s, `constants.py:5`), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore (AlohaEnv has `set_state` but no `get_state`, `env.py:252`). The gaps say the
package fake is a kinematic F0 stand-in, returns a 4 x 4 x 3 stand-in for the real 480 x 640 x 3 top image, does not
render MuJoCo, and was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No hardware backend and no hardware run.

Tags: aloha, bimanual, insertion, manipulation, imitation-learning, simulation, gymnasium
