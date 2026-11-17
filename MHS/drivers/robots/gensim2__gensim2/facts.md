# Facts and tags for gh.gensim2/gensim2

Every fact cites `upstream_code` at commit `4c3a5da3b515a9e772e73a93f0a315732af1c937`. The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| create_gensim builds a SapienEnv with create_sapien | upstream_code | gensim2/env/create_task.py:10 |
| create_gensim instantiates the named task class and returns GenSimTaskWrapper | upstream_code | gensim2/env/create_task.py:20-21 |
| The factory's __main__ example calls create_gensim with TurnOnFaucet and a second argument Sapien | upstream_code | gensim2/env/create_task.py:24-25 |
| GenSimTaskWrapper delegates reset(random) to task.reset(random) | upstream_code | gensim2/env/wrappers.py:112-113 |
| GenSimTaskWrapper.step calls task.env.step and returns obs, reward, done, info (the legacy four-value Gym tuple) | upstream_code | gensim2/env/wrappers.py:66-110 |
| The reward is task.get_reward(); an exception in that call is replaced by reward 0 | upstream_code | gensim2/env/wrappers.py:69-72 |
| The wrapper sets done when the task reports success (unless whole_eps) and calls reset_internal when done | upstream_code | gensim2/env/wrappers.py:79-94 |
| The environment step calls step_action, sim_step, get_observation, is_done and get_info and returns obs, done, info | upstream_code | gensim2/env/base/base_env.py:244-276 |
| is_done is current_step >= horizon | upstream_code | gensim2/env/base/base_env.py:101-102 |
| horizon is 50 control steps and action_dim is 8 | upstream_code | gensim2/env/base/base_env.py:111-117 |
| The action space is Box(low=-1, high=1, shape=(action_dim,)) | upstream_code | gensim2/env/base/base_env.py:327-329 |
| The simulator sets _sim_freq=100, _sim_steps_per_control=80 and dt=_sim_steps_per_control/_sim_freq | upstream_code | gensim2/env/sapien/sim.py:80-84 |
| sim_step executes _sim_steps_per_control scene steps and increments current_step once | upstream_code | gensim2/env/sapien/sim.py:221-226 |
| The state observation is 15 float32 values: end-effector position (3), end-effector quaternion (4) and the first 8 joint positions | upstream_code | gensim2/env/base/base_env.py:304-319 |
| The action's first three values are the target end-effector position, elements 3:7 are the quaternion for an eight-value action, and the last value is the gripper command | upstream_code | gensim2/env/base/base_env.py:209-220 |
| Seeding replaces the environment's np_random generator and returns [seed] | upstream_code | gensim2/env/base/base_env.py:76-78 |
| The wrapper's seed delegates to task.env.seed | upstream_code | gensim2/env/wrappers.py:130-131 |
| The wrapper's close delegates to task.close | upstream_code | gensim2/env/wrappers.py:127-128 |
| GenSimBaseEnv subclasses gym.Env | upstream_code | gensim2/env/base/base_env.py:21 |
| set_gripper writes int(openness) * 0.04 as the target of each of the last two active joints | upstream_code | gensim2/env/sapien/env.py:424-435 |
| GenSimBaseTask.reset_objects prints the selected Asset ID | upstream_code | gensim2/env/base/base_task.py:108 |

Limits: the driver declares none. A GymnasiumDriver derives the `action.values` bounds from the environment's action
space; this package cites `gensim2/env/base/base_env.py:329` (`Box(low=-1, high=1, shape=(self.action_dim,))`), so
the eight action values are bounded to [-1, 1] with source `upstream_code`. `ticks` is bounded by `max_ticks`
(1 to 10000, the SDK default). The device is simulated (R0), so no bound is `operator_required`.

Fidelity: the `fake` backend is the deployed analytic stand-in (F0, kinematic, timestep 800 ms, seeded, lockstep,
reset full, no snapshot/restore); its gaps name the absent dynamics, contacts, sensors and image observation and the
placeholder start/target values. The `sim` backend entry describes the SAPIEN environment (F1, with contact and
actuator fidelity as the engine's own, not validated) and remains blocked pending a lifecycle adapter; `env.seed` sets `np_random`, but the task's
random pose and openness helpers use the global numpy generator (`gensim2/env/utils/pose.py:294` and `:335`), so a
seeded random reset is not reproducible upstream.

Safety: simulated R0 device. The e-stop is the runtime's software latch: after it, no step, reset or seed is accepted
until `mhs.safety.reset` clears the latch, and the state stays readable. There is no physical e-stop and no hardware
backend.

Tags: gensim2, sapien, manipulation, simulation, gymnasium, reinforcement-learning

Model review scope: only the fake contract was executed. The legacy upstream reset takes random=False, not
seed/options; the bridge falls back to seed(seed), reset() and drops options, so options['random'] does not select a
randomized native reset. The fake now uses the same signature. The gripper fake copies int(openness) * 0.04, including
negative targets, from sapien/env.py:424-435; its immediate target tracking remains a kinematic placeholder.

The declared sim factory needs a lifecycle adapter: wrapper.close calls task.close (wrappers.py:127-128), absent
from the shipped task classes and GenSimBaseTask. Fake close is only stand-in cleanup. Upstream construction and
reset print to stdout (sapien/sim.py:21-26; base/base_task.py:108); isolate those writes from an MHS stdio stream.
Planning failure is swallowed by move_to_pose/step_action (base/base_env.py:224-240), and reward exceptions become
zero, so a completed world step proves neither successful planning nor achievement of a requested pose. The latch
does not interrupt an in-flight planner. The separate panda_py/libfranka initialization in
gensim2/agent/utils/init_panda.py is a hardware path outside this package. The factory's __main__ example passes
'Sapien' as task_code_input (create_task.py:7,16-17,25), rather than selecting an engine; this is not the deployment
factory call used here.
