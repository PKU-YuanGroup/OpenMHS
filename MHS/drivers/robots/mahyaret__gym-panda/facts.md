# Facts and tags for gh.mahyaret/gym-panda

Every fact cites its source at commit `92c769fcd4d910b5913f99f96aa7cb1231a9d069`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PandaEnv is registered as panda-v0 with entry point gym_panda.envs:PandaEnv | upstream_code | gym_panda/__init__.py:3-6 |
| The action space is a four-element Box with every element between -1 and 1 | upstream_code | gym_panda/envs/panda_env.py:22 |
| The observation space is declared as a five-element Box with every element between -1 and 1 | upstream_code | gym_panda/envs/panda_env.py:23 |
| A step moves the hand target by action[0], action[1] and action[2] times 0.005 | upstream_code | gym_panda/envs/panda_env.py:28-31 |
| The fourth action element is the position target of finger joints 9 and 10 | upstream_code | gym_panda/envs/panda_env.py:32-41 |
| The hand state is link 11 and the finger state is joints 9 and 10 | upstream_code | gym_panda/envs/panda_env.py:34-47 |
| The observation is the hand position followed by the two finger positions as a float32 array | upstream_code | gym_panda/envs/panda_env.py:65-66 |
| The episode ends with reward 1 when the object is above z = 0.45, otherwise the reward is 0 and done is false | upstream_code | gym_panda/envs/panda_env.py:51-56 |
| MAX_EPISODE_LEN is 20*100 | upstream_code | gym_panda/envs/panda_env.py:13 |
| A step after MAX_EPISODE_LEN ends the episode with reward 0 | upstream_code | gym_panda/envs/panda_env.py:58-62 |
| A reset draws the object start uniformly in x 0.5 to 0.8 and y -0.2 to 0.2 at z = 0.05 | upstream_code | gym_panda/envs/panda_env.py:87-88 |
| A reset sets gravity to -10 and loads the plane, Panda, table and tray in PyBullet | upstream_code | gym_panda/envs/panda_env.py:73-85 |
| A reset puts the seven arm joints at fixed rest poses and both fingers at 0.08 | upstream_code | gym_panda/envs/panda_env.py:77-82 |
| A step calls PyBullet's stepSimulation once | upstream_code | gym_panda/envs/panda_env.py:43 |
| The constructor opens a PyBullet GUI | upstream_code | gym_panda/envs/panda_env.py:20 |
| render() returns an image with 960 columns and 720 rows | upstream_code | gym_panda/envs/panda_env.py:106-115 |
| close() disconnects the PyBullet client | upstream_code | gym_panda/envs/panda_env.py:121-122 |
| The README's PD example states that PyBullet's default timestep is 240 Hz | vendor_doc | README.md:65 |

Limits: the driver declares none. The only bound of the action is the environment's own `Box([-1]*4, [1]*4)`
(`panda_env.py:22`), which the bridge derives into per-element limits on `action.values` with the source
`upstream_code` and the ref `gym_panda/envs/panda_env.py:22`; `ticks` is bounded to 1 through the family's
`max_ticks` (10000). The device is simulated (R0), so no limit is `operator_required` and there is no
`site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:panda-v0`, level F1 (PyBullet rigid-body
dynamics with contacts), determinism `seeded` with `seed_control` `parameter` (the fake draws the object start from
`random.Random(seed)`), timestep 1000/240 ms (about 4.17 ms) from the README's statement that PyBullet's default is
240 Hz (`README.md:65`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say
that the checked fake is kinematic, that the upstream reset() cannot be seeded, that there is no renderer and that no
physical device was modelled or validated.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. Nothing was tested on hardware.

Tags: franka-panda, pybullet, grasping, reinforcement-learning, simulation, gym
