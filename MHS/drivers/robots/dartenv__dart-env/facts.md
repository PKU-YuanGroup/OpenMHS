# Facts and tags for gh.dartenv/dart-env

Every fact cites its source at commit `43e5f8c17b534e180e2340ec2ef405950ad7f542`: `upstream_code` is code of the
clone (the clone's README and docs were not needed). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Copy-v0 is registered with entry point gym.envs.algorithmic:CopyEnv and max_episode_steps=200 | upstream_code | gym/envs/__init__.py:6-11 |
| The action space is a three-tuple of Discrete spaces: left or right movement, a write flag with 2 values, and a character in 0 .. base - 1 | upstream_code | gym/envs/algorithmic/algorithmic_env.py:74-80 |
| The observation space is Discrete(base + 1): the character under the read head, and the blank index base when the head is out of bounds | upstream_code | gym/envs/algorithmic/algorithmic_env.py:81-83 |
| The movements are left and right and the read head starts at index 0 | upstream_code | gym/envs/algorithmic/algorithmic_env.py:244-245 |
| The observation is the input character at the read head; a position below 0 or past the tape returns the blank index base | upstream_code | gym/envs/algorithmic/algorithmic_env.py:251-261 |
| A correct write earns +1, a wrong character earns -0.5 and ends the episode, and a step without a write earns 0 | upstream_code | gym/envs/algorithmic/algorithmic_env.py:162-188 |
| The episode also ends when the write head reaches the target length, and a step that passes the time limit earns -1 and ends the episode | upstream_code | gym/envs/algorithmic/algorithmic_env.py:186-192 |
| The time limit is input_width + len(target) + 4 steps | upstream_code | gym/envs/algorithmic/algorithmic_env.py:198-203 |
| A reset draws a tape length of randint(3) + min_length and derives the target from that tape | upstream_code | gym/envs/algorithmic/algorithmic_env.py:219-230 |
| The Copy task's target is the input tape itself | upstream_code | gym/envs/algorithmic/copy_.py:12-13 |
| The minimum tape length starts at 2 (AlgorithmicEnv's starting_min_length default) | upstream_code | gym/envs/algorithmic/algorithmic_env.py:49 |
| The environment raises min_length by one after its promotion window and caps it at 30 | upstream_code | gym/envs/algorithmic/algorithmic_env.py:205-217 |
| AlgorithmicEnv.seed seeds the environment from gym.utils.seeding | upstream_code | gym/envs/algorithmic/algorithmic_env.py:91-93 |
| CopyEnv's constructor defaults are base=5 and chars=True | upstream_code | gym/envs/algorithmic/copy_.py:9 |

Limits: the driver declares none. The Copy-v0 environment is simulated (R0) and its input bounds are the Tuple
action space, which the Gymnasium bridge publishes only as a three-element array without per-element limits. The
fake checks the tuple element by element exactly as the upstream `step` does (`algorithmic_env.py:163`), so an
invalid element is a device fault, not a runtime envelope refusal. This is listed in the fidelity `gaps` and in
`RESULT.json` notes.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym:Copy-v0`, level F0 (an event-driven analytic tape
and write head, no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 0 because commands
advance the world one discrete transition at a time, `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled, that the fake was not compared with the upstream
environment, and that the registered 200-step TimeLimit wrapper is not modelled because the environment's own time
limit ends an episode first.

Safety: simulated R0 device. The e-stop is the runtime's software latch; after it no step or reset is accepted
until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware stop exists and none is claimed.

Tags: algorithmic, copy, gym, reinforcement-learning, simulation, world-model
