# Facts and tags for gh.proroklab/vectorizedmultiagentsimulator

Every fact cites its source at commit `9658bc56e886f96e4b62033e5df009eccb92122b`; the same facts are written into
`driver.py` (`facts = [...]`) and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| VMAS describes itself as a vectorized differentiable simulator designed for efficient MARL benchmarking | upstream_code | README.md:26 |
| make_env loads the named scenario, constructs an Environment and returns the requested wrapper, or the Environment itself when wrapper is None | upstream_code | vmas/make_env.py:80-101 |
| The published scenario list includes the name balance | upstream_code | vmas/__init__.py:32 |
| make_env defaults device to cpu and continuous_actions to True | upstream_code | vmas/make_env.py:17-18 |
| make_env defaults dict_spaces to False and terminated_truncated to False | upstream_code | vmas/make_env.py:22-26 |
| get_action_space returns a Tuple of per-agent spaces when dict_spaces is false and a Dict keyed by agent name when dict_spaces is true | upstream_code | vmas/simulator/environment/environment.py:431-441 |
| A continuous agent action space is a Box whose shape is the agent's action size | upstream_code | vmas/simulator/environment/environment.py:474-488 |
| Environment.step accepts a dict of actions keyed by agent name | upstream_code | vmas/simulator/environment/environment.py:354-366 |
| Environment.step requires each action tensor to have shape (num_envs, action_size) | upstream_code | vmas/simulator/environment/environment.py:376-384 |
| With terminated_truncated set, the step result is obs, rewards, terminated, truncated and infos | upstream_code | vmas/simulator/environment/environment.py:300-303 |
| The balance reward returns the same ground_rew + pos_rew tensor for every agent | upstream_code | vmas/scenarios/balance.py:223-241 |
| GymnasiumWrapper.step converts its action with _action_list_to_tensor, which requires one action per agent in a sequence | upstream_code | vmas/simulator/environment/gym/base.py:94-109 |
| The Gymnasium wrapper requires gymnasium and shimmy and raises ImportError when either is absent | upstream_code | vmas/simulator/environment/gym/gymnasium.py:14-23 |
| The Gymnasium wrapper serves one vectorized environment only: it asserts num_envs == 1 and terminated_truncated | upstream_code | vmas/simulator/environment/gym/gymnasium.py:36-42 |
| GymnasiumWrapper.reset(seed, options) seeds the wrapped Environment and resets environment 0; options is accepted and not used | upstream_code | vmas/simulator/environment/gym/gymnasium.py:65-75 |
| GymnasiumWrapper.step converts the per-agent action list, steps the wrapped Environment and returns obs, rewards, terminated, truncated and info | upstream_code | vmas/simulator/environment/gym/gymnasium.py:51-63 |
| GymnasiumWrapper converts the wrapped Environment's observation and action spaces with shimmy's _convert_space | upstream_code | vmas/simulator/environment/gym/gymnasium.py:43-44 |
| The balance scenario defaults to 3 agents and constructs agent_0, agent_1 and agent_2 with u_multiplier=0.7 | upstream_code | vmas/scenarios/balance.py:17-39 |
| An Agent uses Holonomic dynamics by default and takes its action size from the dynamics' needed_action_size | upstream_code | vmas/simulator/core.py:929-937 |
| Holonomic.needed_action_size is 2, so each balance agent has a two-value action | upstream_code | vmas/simulator/dynamics/holonomic.py:9-12 |
| The default Agent action range u_range is 1.0 | upstream_code | vmas/simulator/core.py:851 |
| The balance observation concatenates agent position, velocity, package-relative position, line-relative position, package-goal offset, package velocity, line velocity, line angular velocity and line rotation | upstream_code | vmas/scenarios/balance.py:245-256 |
| World's default simulation timestep dt is 0.1 s | upstream_code | vmas/simulator/core.py:1095 |
| The balance scenario constructs the World with gravity (0.0, -0.05) and y_semidim 1 and does not override dt | upstream_code | vmas/scenarios/balance.py:33 |

Limits: the driver declares no sourced Limit of its own. The only action bound is the environment's action space,
which the Gymnasium bridge derives from the fake's Dict of Boxes (`u_range` 1.0 on each of the two axes, cited by the
facts above). The device is simulated (R0), so no limit is `operator_required` and there is no hardware stop.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `vmas:balance`, level F1, determinism `seeded` with
`seed_control` `parameter`, timestep 100 ms (World `dt` 0.1 s, `vmas/simulator/core.py:1095`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot/restore. The gaps state that the fake has no contact or actuator model, is
not the upstream PyTorch engine, reduces the per-agent rewards to one scalar, accepts both the bridge's Dict action and
the wrapper's list action, has no vectorized batch dimension, no rendering/lidar/communication and no snapshot, and
that the sim backend calls `vmas.make_env` (`wrapper=None`), adds a leading batch axis of 1 to each Dict action and returns the shared reward as one number, and that this authoring workspace did not run that path.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: vmas, multi-agent, reinforcement-learning, simulation, gymnasium, balance
