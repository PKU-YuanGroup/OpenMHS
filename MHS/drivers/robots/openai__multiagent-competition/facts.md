# Facts and tags for gh.openai/multiagent-competition

Every fact cites its source at commit `b2e081a192429913b7d21a89525901d59c85e7f3`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| run-to-goal-ants-v0 is registered with entry point gym_compete.new_envs:MultiAgentEnv, two ant agents, the ant scene XML and the initial positions [(-1, 0, 0.75), (1, 0, 0.75)] | upstream_code | gym-compete/gym_compete/__init__.py:4-15 |
| MultiAgentEnv builds observation_space and action_space as a Tuple with one entry per agent | upstream_code | gym-compete/gym_compete/new_envs/multi_agent_env.py:103-111 |
| MultiAgentEnv._step advances the scene, collects per-agent rewards, dones and infos, and returns a tuple of per-agent observations | upstream_code | gym-compete/gym_compete/new_envs/multi_agent_env.py:135-157 |
| MultiAgentScene.simulate concatenates the per-agent actions and calls do_simulation with the scene's frame_skip | upstream_code | gym-compete/gym_compete/new_envs/multi_agent_scene.py:16-18 |
| MultiAgentScene constructs gym's MuJoCo environment with frame_skip 5 | upstream_code | gym-compete/gym_compete/new_envs/multi_agent_scene.py:12 |
| The ant scene XML sets the MuJoCo timestep to 0.01 s | upstream_code | gym-compete/gym_compete/new_envs/assets/world_body.ant_body.ant_body.xml:4 |
| Agent.set_action_space builds each agent's Box from the XML actuator ctrlrange and falls back to infinite bounds when no range is found | upstream_code | gym-compete/gym_compete/new_envs/agents/agent.py:50-75 |
| The ant XML declares eight motors with ctrlrange -1.0 to 1.0 | upstream_code | gym-compete/gym_compete/new_envs/assets/ant_body.xml:56-64 |
| The ant observation concatenates its qpos, qvel, clipped external contact forces and the other agent's qpos | upstream_code | gym-compete/gym_compete/new_envs/agents/ant.py:48-61 |
| The ant observation space is Box(-inf, inf) with the observation size computed from that observation | upstream_code | gym-compete/gym_compete/new_envs/agents/ant.py:63-68 |
| MultiAgentEnv._seed delegates seeding to the scene | upstream_code | gym-compete/gym_compete/new_envs/multi_agent_env.py:165-166 |
| MultiAgentEnv.dt returns the scene's dt | upstream_code | gym-compete/gym_compete/new_envs/multi_agent_env.py:176-178 |
| MultiAgentEnv.reset_model resets the scene and every agent and returns the per-agent observations | upstream_code | gym-compete/gym_compete/new_envs/multi_agent_env.py:186-191 |
| The tested stack is gym 0.9.1 with MuJoCo 1.31 and mujoco-py 0.5.7 on Python 3.6 | vendor_doc | README.md:9-11 |

Limits: the driver declares none. The action bounds are the environment's own Tuple of per-ant Box spaces, which the
bridge derives from the fake's action space; the step input's `ticks` is bounded by the bridge (1 to 10000 by
default). The device is simulated (R0), so no limit is `operator_required` and no site overlay exists.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym-compete:run-to-goal-ants-v0`, level F0 (the fake is
kinematic: no rigid-body dynamics, contacts, actuators, sensors or noise), determinism `seeded` with `seed_control`
`parameter`, timestep 50 ms (one environment step: MuJoCo timestep 0.01 s multiplied by frame_skip 5), `realtime_factor`
0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps disclose the missing MuJoCo model, the scalar
translation of the per-agent reward and done tuples, the reset two-tuple, the lack of goal or rendering logic, and
that the sim backend was not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware path exists.

Tags: multi-agent, ants, mujoco, gym, reinforcement-learning, simulation
