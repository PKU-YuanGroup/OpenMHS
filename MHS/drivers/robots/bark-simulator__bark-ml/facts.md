# Facts and tags for gh.bark-simulator/bark-ml

Every fact cites its source at commit `ea2ee58be406e71c5e95c80c0ffbe56c03d6ec60`: `upstream_code` is a line of the
clone's code or comments, `vendor_doc` is a line of the clone's documentation. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| highway-v0 is registered with the gym entry point bark_ml.environments.gym:ContinuousHighwayGym | upstream_code | bark_ml/environments/gym.py:155-157 |
| ContinuousHighwayGym builds the runtime with render=True | upstream_code | bark_ml/environments/gym.py:35-36 |
| SingleAgentRuntime.reset and step call render when the runtime was built with render=True | upstream_code | bark_ml/environments/single_agent_runtime.py:58-89 |
| The continuous highway behavior model takes the steering rate and the acceleration as its action | upstream_code | bark_ml/environments/gym.py:25-29 |
| The continuous action space is BoundedContinuous(2) over acceleration and steering rate, with the default lower bound [-5.0, -0.2] and upper bound [4.0, 0.2] | upstream_code | bark_ml/behaviors/cont_behavior.py:29-43 |
| The highway blueprint uses a 0.2 s simulation step | upstream_code | bark_ml/environments/blueprints/highway/highway.py:103-113 |
| The highway blueprint builds four lane corridors, marks lane 2 as the controlled ego lane, places the ego agent between s 40 and 80 and other agents between s 0 and 250 | upstream_code | bark_ml/environments/blueprints/highway/highway.py:65-85 |
| The highway scenario is a curved four-lane road whose vehicles are controlled by the intelligent driver model (IDM) | vendor_doc | Readme.md:30 |
| The nearest observer defaults to four nearest agents and concatenates six ego values plus four values per agent, 22 values in total | upstream_code | bark_ml/observers/nearest_observer.hpp:66-82 |
| The ego block is normalized s, d, theta, longitudinal velocity and lateral velocity, followed by the raw lane-corridor index | upstream_code | bark_ml/observers/nearest_observer.hpp:100-109 |
| The observer declares its observation space as a Box over observation_len_ values with low 0 and high 1 | upstream_code | bark_ml/observers/nearest_observer.hpp:170-176 |
| The default step-count evaluator terminates an episode after more than 220 steps | upstream_code | bark_ml/evaluators/general_evaluator.py:88-91 |
| SingleAgentRuntime.reset takes only a scenario and returns the observer's observation | upstream_code | bark_ml/environments/single_agent_runtime.py:47-64 |
| SingleAgentRuntime.step advances the world by its fixed step time and returns observation, reward, done and info | upstream_code | bark_ml/environments/single_agent_runtime.py:66-91 |
| The continuous highway blueprint's scenario generator uses random_seed 0 by default | upstream_code | bark_ml/environments/blueprints/highway/highway.py:119-125 |

Limits: the driver declares none. The bridge derives the action limits from the fake's ``BoundedContinuous``:
``action.values[0]`` acceleration from -5.0 to 4.0 and ``action.values[1]`` steering rate from -0.2 to 0.2
(cont_behavior.py:29-43). The device is simulated (R0), so no limit is ``operator_required`` and no operator overlay
is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `bark-ml:highway-v0`, level F1 (a kinematic vehicle
model without contacts, traffic dynamics, sensors or noise), determinism `seeded` with `seed_control` `none`
(the upstream reset takes a scenario, not a seed; the generator is configured with random_seed 0), timestep 200 ms
(highway.py:103), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is
not modelled, including rendering (the upstream environment always renders) and the fact that the sim backend was
not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
observation stays readable.

Tags: autonomous-driving, highway, reinforcement-learning, simulation, gymnasium, bark-ml

Scope: this package serves `highway-v0` (`ContinuousHighwayGym`). The clone also registers `highway-v1`
(`DiscreteHighwayGym`), `merging-v0`, `merging-medium-v0`, `merging-v1`, `intersection-v0`, `intersection-v1` and
`singlelane-v0` (gym.py:159-185); they are separate environments with their own action spaces and blueprints and are
not covered by this package.
