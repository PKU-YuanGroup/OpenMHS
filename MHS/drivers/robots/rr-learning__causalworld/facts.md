# Facts and tags for gh.rr-learning/causalworld

Every fact cites its source at commit `1045277101a92c506db42704da28f6e7227d401b`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| CausalWorld subclasses gym.Env, the legacy OpenAI Gym environment API | upstream_code | causal_world/envs/causalworld.py:18 |
| With visualization disabled the structured observation mode uses an in-process PyBullet client connected with pybullet.DIRECT | upstream_code | causal_world/envs/causalworld.py:962-967 |
| The documented use constructs the environment as CausalWorld(task=task, enable_visualization=True) | vendor_doc | README.md:215 |
| The constructor defaults to structured observations, joint_positions actions and normalized actions and observations | upstream_code | causal_world/envs/causalworld.py:29-32 |
| One environment step multiplies a 1/250 s simulation step by skip_frame | upstream_code | causal_world/envs/causalworld.py:93-96 |
| skip_frame defaults to 10 | upstream_code | causal_world/envs/causalworld.py:26 |
| The reaching task's default episode length is 5 seconds | upstream_code | causal_world/task_generators/base_task.py:1198-1202 |
| The constructor converts the task's default episode length to int(length / dt) | upstream_code | causal_world/envs/causalworld.py:167-170 |
| The joint-position action bounds are [-1.57, -1.2, -3.0] repeated for three fingers to [1.0, 1.57, 3.0] repeated | upstream_code | causal_world/envs/robot/action.py:21-24 |
| When actions are normalized the action space is Box(low=-1, high=1), one element per joint-position bound | upstream_code | causal_world/envs/robot/action.py:61-64 |
| The reaching task's robot observation keys are time_left_for_task, joint_positions, joint_velocities and end_effector_positions | upstream_code | causal_world/task_generators/reaching.py:47-51 |
| The reaching task's stage observation keys are the three goal cartesian positions | upstream_code | causal_world/task_generators/reaching.py:85-89 |
| A goal silhouette's cartesian position is bounded from [-0.5, -0.5, 0] to [0.5, 0.5, 0.5] | upstream_code | causal_world/envs/scene/silhouette.py:41-56 |
| The structured observation space concatenates the robot and stage spaces into one Box | upstream_code | causal_world/utils/env_utils.py:31-40 |
| Normalized observations use the bounds -1 and 1 | upstream_code | causal_world/envs/robot/observations.py:73-74 |
| A step returns observation, reward, done and info, and scales the reward by dt | upstream_code | causal_world/envs/causalworld.py:274-290 |
| reset takes no seed and returns the task's structured observation | upstream_code | causal_world/envs/causalworld.py:346-372 |
| seed reseeds gym's np_random and numpy and returns the seed in a list | upstream_code | causal_world/envs/causalworld.py:333-344 |
| An episode is done when the episode length is greater than the maximum episode length | upstream_code | causal_world/envs/causalworld.py:422-430 |
| The info dictionary carries desired_goal, achieved_goal, success and fractional_success | upstream_code | causal_world/task_generators/base_task.py:312-340 |
| The environment exposes get_state and set_state for pybullet_state and control_index | upstream_code | causal_world/envs/causalworld.py:492-521 |
| close saves an attached data recorder and closes the robot | upstream_code | causal_world/envs/causalworld.py:401-410 |
| The reaching task's default goals are [0, 0, 0.10], [0, 0, 0.13] and [0, 0, 0.16] | upstream_code | causal_world/task_generators/reaching.py:10-12 |

The structured reaching observation has 37 elements by construction: time-left (1) + joint positions (9) + joint
velocities (9) + end-effector positions (9) + three goal cartesian positions (3 each). The key lists are
`reaching.py:47-51` and `:85-89`; the element counts are the bounds in `observations.py:38-46` and
`silhouette.py:41-56`. The time-left and goal values are normalized with the same -1..1 convention
(`observations.py:73-74`), so the whole observation space is `Box(-1, 1, shape=(37,))`.

Limits: the driver declares none of its own. The bridge derives the only input bound from the fake environment's
action space (`action.values` from -1 to 1 per element, no source, ref
`action_space of the fake backend .fake:FakeCausalWorld`) and `ticks` from 1 to `max_ticks` (10000). The class's
normalized action space is the upstream Box(-1, 1) described above. The device is simulated (R0), so no bound is
`operator_required` and no site-limits overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic`, level F0 (the checked fake is kinematic; the
upstream PyBullet model is not modelled), determinism `seeded` with `seed_control` `parameter`, timestep 40 ms (one
1/250 s simulation step times the default skip_frame 10, `causalworld.py:26`, `:93-96`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps name the missing PyBullet dynamics, contacts, controller,
pixel observations, the different random generator and the absent snapshot support.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop to a machine); after
it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. The upstream
environment is a PyBullet simulation (`causalworld.py:962-967`), not hardware.

Tags: causalworld, trifinger, robotic-manipulation, pybullet, reinforcement-learning, simulation, gym
