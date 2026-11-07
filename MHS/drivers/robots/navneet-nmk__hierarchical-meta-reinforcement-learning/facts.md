# Facts and tags for gh.navneet-nmk/hierarchical-meta-reinforcement-learning

Every fact cites its source at commit `4ef92cebfa11760d9de55d54fc8e827271982a63`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The TabularMDP-v0 registration fixes num_states=10 and num_actions=5 | upstream_code | maml_rl/envs/__init__.py:19 |
| The TabularMDP-v0 registration sets max_episode_steps=10 | upstream_code | maml_rl/envs/__init__.py:20 |
| The environment uses the legacy Gym API: it imports gym and gym.spaces and subclasses gym.Env | upstream_code | maml_rl/envs/mdp.py:3-7 |
| The action space is Discrete(num_actions), so a step action is an integer action index | upstream_code | maml_rl/envs/mdp.py:27 |
| The observation space is Box(0.0, 1.0, shape=(num_states,), dtype=float32) | upstream_code | maml_rl/envs/mdp.py:28-29 |
| The default task has uniform transition probabilities 1/num_states and zero mean rewards | upstream_code | maml_rl/envs/mdp.py:31-35 |
| seed replaces the environment's random generator and returns [seed] | upstream_code | maml_rl/envs/mdp.py:39-41 |
| sample_tasks draws transition rows from a Dirichlet(1) distribution and mean rewards from a Normal(1, 1) distribution | upstream_code | maml_rl/envs/mdp.py:43-50 |
| reset_task replaces the transition tensor and the mean rewards from a task dictionary | upstream_code | maml_rl/envs/mdp.py:52-55 |
| reset starts every episode in state 0 and returns a one-hot observation of length num_states | upstream_code | maml_rl/envs/mdp.py:57-63 |
| step draws the reward from a Normal(mean, 1) distribution, samples the next state from the transition row and returns the next one-hot observation | upstream_code | maml_rl/envs/mdp.py:65-75 |
| step always returns done=False, so the environment class itself never terminates an episode | upstream_code | maml_rl/envs/mdp.py:75 |

## Entry symbols of the card

The card lists four entries. This package implements one AST-confirmed device,
`maml_rl.envs.mdp:TabularMDPEnv` (`TabularMDP-v0`). It was chosen because the registration fixes both constructor
arguments and the class's step never terminates, so the world has a stable non-terminal trajectory; the fake uses the
same defaults. The others are not this device: `maml_rl.envs.bandit:BernoulliBanditEnv` (the `Bandit-K5-v0`,
`Bandit-K10-v0` and `Bandit-K50-v0` registrations, maml_rl/envs/bandit.py:7), `maml_rl.envs.navigation:Navigation2DEnv`
(the `2DNavigation-v0` registration, maml_rl/envs/navigation.py:7), and `maml_rl.envs.utils:mujoco_wrapper` (a wrapper
function, not an environment class, maml_rl/envs/utils.py:4-9; its MuJoCo environments need the model files and the
MuJoCo system dependency named in the card). One package per repository; a card correction can add them as their own
device classes.

Limits: the driver declares none. The only bounds are derived from the environment's action space by the bridge
(`Discrete(5)`: `action.index` from 0 to 4, with no source and the ref
`action_space of the fake backend .fake:FakeTabularMDPEnv`) and `ticks` (1 to `max_ticks`, 10,000 by default).
`num_actions=5` comes from the registration (`maml_rl/envs/__init__.py:19`) and the `Discrete` space from
`maml_rl/envs/mdp.py:27`. The device is simulated (R0), so no limit is `operator_required` and
there is no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:TabularMDP-v0`, level F0 (analytic tabular
MDP: a finite state transition table and a Normal reward, no dynamics, contacts, actuator, sensor or noise model),
determinism `seeded` with `seed_control` `parameter`, timestep 0 ms (the class has no physics timestep; a step is one
MDP transition), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is
not modelled, that the registered 10-step TimeLimit wrapper is not reproduced by the fake, and that this package's
fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: tabular-mdp, meta-reinforcement-learning, reinforcement-learning, simulation, gymnasium, gym
