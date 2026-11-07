# Facts and tags for gh.sail-research-lab/robust-gymnasium

This card names five class entry symbols: `CartPoleEnv` (`robust_gymnasium/envs/classic_control/cartpole.py:19`),
`MountainCarEnv` (`mountain_car.py:16`), `Continuous_MountainCarEnv` (`continuous_mountain_car.py:27`), `PendulumEnv`
(`pendulum.py:18`) and `AcrobotEnv` (`acrobot.py:28`). One package implements one device, so this driver serves the
first confirmed symbol, `robust_gymnasium.envs.classic_control.cartpole:CartPoleEnv` (CartPole-v1). The other four
symbols were checked to exist and are not implemented here.

Every fact below cites `upstream_code` at commit `af6de64d92793ef4c01b80e51e3f2bcd35f8066b`. The same facts are in
`driver.py`; `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The action space is Discrete(2): the only valid actions are the integers 0 and 1 | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:149 |
| Action 1 applies a push of +force_mag and any other valid action applies -force_mag | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:169 |
| The model constants are gravity 9.8, cart mass 1.0, pole mass 0.1, pole half-length 0.5, force magnitude 10.0, integration step 0.02 s and the euler integrator | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:123-131 |
| The episode fails when the pole angle leaves 12 degrees or the cart position leaves 2.4 | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:134-135 |
| The observation bounds are twice the failure thresholds: cart position +-4.8, pole angle about +-0.418 rad, and the two velocity bounds are the float32 maximum | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:134-150 |
| The observation has four elements: cart position, cart velocity, pole angle and pole angular velocity | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:42-49 |
| step returns the state as a float32 numpy array | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:232 |
| The episode terminates when the cart position or the pole angle crosses its threshold | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:196-201 |
| The constructor's sutton_barto_reward default is False | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:118-121 |
| When sutton_barto_reward is False every step pays 1.0, including the terminating step, and 0.0 after the episode; when it is True a non-terminal step pays 0.0 and a terminal or post-terminal step pays -1.0 | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:203-227 |
| CartPoleEnv.step always reports truncated=False; the episode length limit is the TimeLimit wrapper that make() adds | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:231-232 |
| CartPole-v1 is registered with max_episode_steps=500 | upstream_code | robust_gymnasium/envs/__init__.py:27-33 |
| reset() accepts options and uses the default bounds -0.05 and 0.05; it draws the four state values uniformly between low and high | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:243-246 |
| The model is a cart on a frictionless track with an un-actuated pole joint; an action is a fixed-magnitude push | upstream_code | robust_gymnasium/envs/classic_control/cartpole.py:25-35 |

The reset-options helper is imported from the installed `gymnasium` package (`cartpole.py:13`), not from this clone.
The clone carries an identical copy at `robust_gymnasium/envs/classic_control/utils.py:32-46`; the fake mirrors that
logic but the fact above cites the call in `cartpole.py`, which is the code that decides the defaults.

## Limits

The driver declares no `Limit`. The bridge derives the only action bound from the environment itself: `Discrete(2)`
makes `action.index` run from 0 to 1, with the source `upstream_code` and the ref
`robust_gymnasium/envs/classic_control/cartpole.py:149`. The bridge's `max_ticks` default of 10000 and the catalogue's
`cap.world.step.v1` `ticks` maximum of 10000 are SDK/catalogue configuration, not a bound stated by the clone, so they
are not written as a driver Limit and no number is copied into a Fact. The device is simulated R0, so no bound is
`operator_required`.

## Fidelity contract

`fidelity = {...}` in `driver.py`: engine `robust_gymnasium:CartPole-v1`, level F1 (rigid-body equations of a cart and
a pole), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (`tau = 0.02` s,
`cartpole.py:130`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot/restore not offered. The `gaps` say
what is not modelled: contacts, friction, actuator dynamics, sensor noise and wall-clock pacing, that the fake is not
the upstream environment, and that the bridge's unlisted `sim` path would open the base Gymnasium package rather than
this fork.

## Safety

Simulated R0 device: no hardware backend and no machine stop exist. The runtime's software latch is the e-stop; after
it no step or reset is accepted until `mhs.safety.reset` clears the latch, while the last observation stays readable.
The fake backend is a pure Python re-implementation of the clone's equations and time limit; it was never compared
with the upstream environment, and neither robust_gymnasium nor gymnasium was installed where the gate ran.

Tags: cartpole, classic-control, robust-reinforcement-learning, simulation, gymnasium
