# Facts and tags for gh.openai/robosumo

Every fact cites its source at commit `3a317e27d2342dd47a869950e93315b23a74921a`.  The upstream has no licence file
and no text documentation beyond `README.md` and `setup.py`, so every claim below is `upstream_code`: Python source,
the model XML files or the registration file.  The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SumoEnv is a multi-agent sumo environment whose goal is for each agent to push the other agent outside the tatami area | upstream_code | robosumo/envs/sumo.py:28-36 |
| RoboSumo-Ant-vs-Ant-v0 registers SumoEnv with agent_names ['ant', 'ant'], agent_densities [13., 13.], tatami_size 2.0 and timestep_limit 500 | upstream_code | robosumo/__init__.py:8-17 |
| The agent models are ant, bug and spider, loaded from assets/ant.xml, assets/bug.xml and assets/spider.xml | upstream_code | robosumo/envs/sumo.py:21-25 |
| The observation space and the action space are Tuple spaces of the per-agent spaces | upstream_code | robosumo/envs/sumo.py:109-114 |
| Each agent's action space is a Box built from the actuator ctrlrange; the ant's eight motors each have ctrlrange -1.0 1.0 | upstream_code | robosumo/envs/assets/ant.xml:58-65 |
| An agent's observation concatenates its qpos, its qvel and its clipped external contact forces, then the opponent's first seven qpos values and the opponent torso contact forces | upstream_code | robosumo/envs/agents.py:190-212 |
| A reset places each agent on a circle of radius 1.15 at height 1.25 with a random start angle, then adds uniform position noise and Gaussian velocity noise | upstream_code | robosumo/envs/sumo.py:232-252 |
| An agent loses when its z position is below 0.29 or max(\|x\|, \|y\|) is at least the environment's _tatami_size | upstream_code | robosumo/envs/sumo.py:149-150 |
| The environment stores _tatami_size as tatami_size + 0.1 | upstream_code | robosumo/envs/sumo.py:55 |
| The reward constants are WIN_REWARD 2000, DRAW_PENALTY -1000, MOVE_TO_OPP_COEF 0.1 and PUSH_OUT_COEF 10.0 | upstream_code | robosumo/envs/sumo.py:38-43 |
| The control cost coefficient is 0.1 | upstream_code | robosumo/envs/agents.py:15-19 |
| The control reward is minus the control cost coefficient times the sum of the squared action values | upstream_code | robosumo/envs/agents.py:217-221 |
| An episode is drawn when the step counter is greater than the timestep limit | upstream_code | robosumo/envs/sumo.py:165-167 |
| The environment step is model.opt.timestep times frame_skip | upstream_code | robosumo/envs/mujoco_env.py:122-123 |
| The tatami model sets the MuJoCo option timestep to 0.01 s and the RK4 integrator | upstream_code | robosumo/envs/assets/tatami.xml:3 |
| SumoEnv takes frame_skip with a default of 5 | upstream_code | robosumo/envs/sumo.py:50 |
| The RoboSumo-Ant-vs-Ant-v0 registration sets no frame_skip | upstream_code | robosumo/__init__.py:8-17 |

Limits: the driver declares none of its own.  The only bounds are the catalogue class's `ticks` range and the
per-agent action Boxes.  The action bounds are real (`ant.xml:58-65`: the ant's eight motors are limited to
`-1.0 .. 1.0`).  The upstream action space is a `Tuple` of two Boxes (`sumo.py:112-114`) and the gymnasium bridge
derives no limits from the elements of a `Tuple`, so the fake exposes the same two Boxes as the `Dict` members
`ant0` and `ant1`; the bridge then publishes the per-motor bounds as `action.ant0` and `action.ant1` limits, sourced
from the environment's own action space.  That named shape is a fake-level mapping, not the upstream
`Tuple`; the fidelity `gaps` say so.  No limit is `operator_required`: the device is simulated R0.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `robosumo:RoboSumo-Ant-vs-Ant-v0`, level F0 (the fake
is kinematic, with no force or contact model; the upstream simulator is F1), determinism `seeded` with `seed_control`
`parameter`, timestep 50 ms (0.01 s model timestep at
`tatami.xml:3` times frame_skip 5 at `sumo.py:50`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore.  The gaps name the reduced fake, the real 120-value observation per agent, the named `Dict` action
mapping, the summed scalar reward and the missing shaping terms.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: robosumo, sumo, multi-agent, mujoco, reinforcement-learning, simulation, gym
