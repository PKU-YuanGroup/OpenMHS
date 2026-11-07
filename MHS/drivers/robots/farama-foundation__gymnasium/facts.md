# Facts and tags for gh.farama-foundation/gymnasium

Every fact cites its source at commit `d77197c284406e6094c9d1a74d4988a8749ce849`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The action space is Discrete(2): the integer action 0 or 1 | upstream_code | gymnasium/envs/classic_control/cartpole.py:151 |
| Action 1 pushes the cart with +force_mag and any other action with -force_mag | upstream_code | gymnasium/envs/classic_control/cartpole.py:171 |
| The physics constants are gravity 9.8, masscart 1.0, masspole 0.1, length 0.5 (half the pole's length), force_mag 10.0 and tau 0.02 s between state updates, integrated with the euler scheme | upstream_code | gymnasium/envs/classic_control/cartpole.py:125-133 |
| The failure thresholds are 12 degrees for the pole angle and 2.4 for the cart position | upstream_code | gymnasium/envs/classic_control/cartpole.py:136-137 |
| The episode terminates when the cart position or the pole angle passes its threshold | upstream_code | gymnasium/envs/classic_control/cartpole.py:199-204 |
| The observation is [cart position, cart velocity, pole angle, pole angular velocity] with the bounds +-4.8, +-inf, about +-0.418 rad (24 degrees) and +-inf | upstream_code | gymnasium/envs/classic_control/cartpole.py:44-51 |
| The reward is +1 for every step, including the step that terminates the episode, and 0 after it | upstream_code | gymnasium/envs/classic_control/cartpole.py:206-221 |
| CartPole-v1 is registered with max_episode_steps=500 | upstream_code | gymnasium/envs/__init__.py:26-32 |
| CartPoleEnv.step never truncates: the time limit is the TimeLimit wrapper that gymnasium.make adds | upstream_code | gymnasium/envs/classic_control/cartpole.py:226 |
| A reset draws the four state values uniformly from (-0.05, 0.05) | upstream_code | gymnasium/envs/classic_control/cartpole.py:238-243 |
| The reset option low or high replaces a bound of that draw (low must not exceed high) | upstream_code | gymnasium/envs/classic_control/utils.py:35-44 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(2)`: `action.index` from 0 to 1, with the source `upstream_code` and the ref
`gymnasium/envs/classic_control/cartpole.py:151`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is
simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:CartPole-v1`, level F1 (rigid-body equations of
motion, no contacts, no actuator, sensor or noise model), determinism `seeded` with `seed_control` `parameter`, timestep
20 ms (`tau = 0.02` s, `cartpole.py:132`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say what is not modelled and that this package's fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: cartpole, classic-control, reinforcement-learning, simulation, gymnasium
