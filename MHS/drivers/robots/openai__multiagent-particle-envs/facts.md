# Facts and tags for gh.openai/multiagent-particle-envs

Every fact cites its source at commit `83ba4d1aeb00282f7c4acd6912435b3ca642c227`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same list is in `driver.py`; the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone registers `MultiagentSimple-v0` with entry point `multiagent.envs:SimpleEnv` and `max_episode_steps=100` | upstream_code | `multiagent/__init__.py:9-15` |
| The clone registers `MultiagentSimpleSpeakerListener-v0` with entry point `multiagent.envs:SimpleSpeakerListenerEnv` and `max_episode_steps=100` | upstream_code | `multiagent/__init__.py:17-21` |
| `make_env` builds a `MultiAgentEnv` from a scenario's `make_world`, `reset_world`, `reward` and `observation` callbacks | upstream_code | `make_env.py:32-44` |
| The simple scenario has one movable agent that is silent and does not collide, and one landmark that does not move or collide | upstream_code | `multiagent/scenarios/simple.py:9-19` |
| The world has two position dimensions, a 0.1 s timestep and damping 0.25 | upstream_code | `multiagent/core.py:90-96` |
| The physical action space of a movable agent is `Discrete(world.dim_p * 2 + 1)` | upstream_code | `multiagent/environment.py:43-49` |
| `discrete_action_input` defaults to False, whose comment describes the action as a one-hot N-dimensional vector | upstream_code | `multiagent/environment.py:30-31` |
| With `discrete_action_input` true, action 1 sets the x force to -1, 2 to +1, 3 sets the y force to -1 and 4 to +1 | upstream_code | `multiagent/environment.py:164-167` |
| The physical action is multiplied by a sensitivity of 5.0 when `agent.accel` is None | upstream_code | `multiagent/environment.py:178-181` |
| A reset draws the agent and landmark positions uniformly from -1 to +1 and zeroes their velocities | upstream_code | `multiagent/scenarios/simple.py:32-39` |
| The observation concatenates the agent velocity with each landmark position relative to the agent | upstream_code | `multiagent/scenarios/simple.py:45-50` |
| The reward is the negative squared distance between the agent and the first landmark | upstream_code | `multiagent/scenarios/simple.py:41-43` |
| The world integrates velocity with damping and `force/mass*dt`, then position with `velocity*dt` | upstream_code | `multiagent/core.py:158-169` |
| An agent's mass is 1.0, its motor noise is None and the world applies noise only when `u_noise` is set | upstream_code | `multiagent/core.py:47-69` |
| `MultiAgentEnv.step` returns per-agent observation, reward and done lists plus an info dict | upstream_code | `multiagent/environment.py:80-104` |
| `MultiAgentEnv.reset` calls the scenario reset callback and returns a list of per-agent observations | upstream_code | `multiagent/environment.py:106-116` |
| A missing done callback makes every done flag False | upstream_code | `multiagent/environment.py:132-135` |
| The observation space is a `Box` from -inf to +inf with shape `(obs_dim,)` for each agent | upstream_code | `multiagent/environment.py:67-69` |
| `make_env` without `benchmark` passes no done callback to `MultiAgentEnv` | upstream_code | `make_env.py:40-44` |
| The README says the code base is an archive and that the maintained version is PettingZoo | vendor_doc | `README.md:1-5` |

## What the package serves

The card's two entry symbols are the strings in the `gym.register` calls; the clone has no `multiagent/envs.py` at
the pinned commit, so neither registered environment id can be constructed. The package therefore names the class the
documented factory builds, `multiagent.environment:MultiAgentEnv` (`make_env.py:32-44`), and serves the single-agent
`multiagent/scenarios/simple.py` world that `MultiagentSimple-v0` was meant to register. The speaker-listener
registration and the other scenarios of the clone are not served. Gate G7 reports `NOT_AN_ENTRY_SYMBOL` for the
different `native`; that warning is recorded in `RESULT.json`.

The fake backend is `fake.py`, a pure Python stand-in because the upstream imports legacy gym and numpy
(`multiagent/environment.py:1-5`, `setup.py:12`) and package code never imports the clone. It implements the
`simple.py` physics (two position dimensions, `world.dt` 0.1 s, damping 0.25, mass 1.0, sensitivity 5.0), the
`Discrete(5)` action space, the reset positions in [-1, +1], the relative-landmark observation and the negative
squared-distance reward. It applies the `discrete_action_input=True` branch (`multiagent/environment.py:164-167`) so
the declared integer action is meaningful; upstream leaves that flag False and expects a 5-element vector. It draws
from Python's `random.Random`, not numpy's global generator, and has no rendering, viewer, `PassiveEnvChecker` or
wall-clock pacing. The fake is not the upstream environment and was not compared with an upstream run. The fidelity
contract is F0 with `timestep_ms` 100.0, `realtime_factor` 0 and snapshot/restore false; the gaps in `driver.py`
state every difference.

The numbers in `fake.py` are placeholder test data, not facts, not limits and not device bounds.

## Tags

`multiagent`, `particle-environment`, `reinforcement-learning`, `simulation`, `gym`
