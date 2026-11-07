# Facts and tags for gh.sunblaze-ucb/rl-generalization

Every fact cites its source at commit `5e05aa108aeadd4cf21f45d56128e9da3bddc14c`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The registered entry point of SunblazeCartPole-v0 is sunblaze_envs.classic_control:ModifiableCartPoleEnv | upstream_code | sunblaze_envs/__init__.py:7-12 |
| ModifiableCartPoleEnv subclasses gym's CartPoleEnv and the package's EnvBinarySuccessMixin | upstream_code | sunblaze_envs/classic_control.py:30 |
| SunblazeCartPole-v0 is registered with max_episode_steps=200 and reward_threshold=195.0 | upstream_code | sunblaze_envs/__init__.py:7-12 |
| EnvRegistry.make wraps an environment that has a timestep limit in sunblaze_envs.time_limit.TimeLimit | upstream_code | sunblaze_envs/registration.py:126-131 |
| sunblaze_envs.make delegates to the package's own EnvRegistry | upstream_code | sunblaze_envs/registration.py:166-167 |
| The package's TimeLimit resets its elapsed-step counter to 0 on reset | upstream_code | sunblaze_envs/time_limit.py:7-10 |
| ModifiableCartPoleEnv.reset sets nsteps=0 and returns the parent Gym reset() | upstream_code | sunblaze_envs/classic_control.py:52-56 |
| ModifiableCartPoleEnv.step increments nsteps and returns the parent Gym step() | upstream_code | sunblaze_envs/classic_control.py:62-65 |
| is_success returns True once nsteps reaches 195, the package's definition of a balanced episode | upstream_code | sunblaze_envs/classic_control.py:67-76 |
| The documented deterministic CartPole parameters are force 10, length 0.5 and mass 0.1 | vendor_doc | sunblaze_envs/README.md:22-24 |
| The commented parent defaults recorded in the clone are gravity 9.8, masscart 1.0, masspole 0.1, length 0.5 (half the pole's length), force_mag 10.0 and tau 0.02 s between state updates | upstream_code | sunblaze_envs/classic_control.py:340-347 |
| CartPoleEnv is imported from gym.envs.classic_control.cartpole, so the action space, the observation bounds and the failure thresholds are Gym's and are not stated by this repository | upstream_code | sunblaze_envs/classic_control.py:3 |
| setup.py pins gym==0.10.8r1, the legacy Gym API the environment is built on | upstream_code | setup.py:42-43 |
| The README documents sunblaze_envs.make('SunblazeCartPole-v0') as the construction path for the deterministic CartPole | vendor_doc | README.md:55-59 |

## Limits

The driver declares no Fact-backed numeric limit of its own. The only bounds it publishes are the bridge's derived
action-space limits (`Discrete(2)` gives `action.index` 0 to 1, with no source and the ref
`action_space of the fake backend .fake:FakeModifiableCartPoleEnv`) and the `ticks` bound of `cap.world.step.v1` (1 to
10000 by default). The action space, observation bounds and failure thresholds are inherited from
`gym.envs.classic_control.cartpole` (`sunblaze_envs/classic_control.py:3`); the clone states no values for them, so no
Fact or Limit copies one. The device is simulated (R0), so no bound is `operator_required`.

## Fidelity

The contract (`driver.py`, `fidelity = {...}`) is engine `sunblaze:SunblazeCartPole-v0`, level F1 (rigid-body
equations of motion inherited from Gym; no contacts, friction, actuator, sensor or noise model), determinism `seeded`
with seed control `parameter`, timestep 20 ms (`tau = 0.02` s, `sunblaze_envs/classic_control.py:347`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that
the fake's failure thresholds are placeholders and that it uses the randomized variants' -0.05 to 0.05 initial-state
spread (`sunblaze_envs/classic_control.py:296-299`) as a placeholder, that the 200-step TimeLimit is re-implemented
and reported through the legacy 4-tuple done flag, and that the fake was not compared with the upstream environment.

## Scope

The card's entry symbol is the deterministic CartPole class above. The repository also registers MountainCar, Pendulum
and Acrobot classic-control variants (`sunblaze_envs/__init__.py:28-83`) and the MuJoCo/Roboschool variants
(`sunblaze_envs/__init__.py:87-127`); this package does not implement them.

## Safety

Simulated R0 device. There is no hardware backend and no native stop. The e-stop is the runtime's software latch:
after it no step, reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator
for that), and the state stays readable.

## Tags

cartpole, classic-control, reinforcement-learning, simulation, gym
