# Facts and tags for gh.pairlab/leibnizgym

Every fact cites its source at commit `2c1cb14fbfece09644445d58fe7ac28c41611e5f`: `upstream_code` is a file:line of
the clone, `vendor_doc` is text of the clone.  The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TrifingerEnv is the concrete IsaacGym environment for the three-finger TriFinger robot | upstream_code | leibnizgym/envs/trifinger/trifinger_env.py:118 |
| TrifingerEnv derives from IsaacEnvBase, the repository's own base class, not from gym.Env or gymnasium.Env | upstream_code | leibnizgym/envs/env_base.py:79 |
| The default configuration sets episode_length to 750, command_mode to position, normalize_action to true and the object initial state to random | upstream_code | leibnizgym/envs/trifinger/trifinger_env.py:30-66 |
| The robot has three fingers with three joints each, so the joint position, joint velocity and joint torque dimensions are 9 | upstream_code | leibnizgym/envs/trifinger/utils.py:35-39 |
| The joint position limits are [-0.33, 0.0, -2.7] to [1.0, 1.57, 0.0] per finger, the joint velocity limit is 10 rad/s and the maximum joint torque is 0.36 N m | upstream_code | leibnizgym/envs/trifinger/trifinger_env.py:149-167 |
| The comment on normalize_action says the action is denormalized from [-1, 1], and the default value is true | upstream_code | leibnizgym/envs/trifinger/trifinger_env.py:45-46 |
| The VecTask wrapper builds the action space as Box(-clip_actions, clip_actions) with clip_actions 1.0 | upstream_code | leibnizgym/wrappers/vec_task.py:34-56 |
| step takes an action tensor of shape [num_instances, action_dim] and returns observation, reward, termination and info buffers | upstream_code | leibnizgym/envs/env_base.py:345-400 |
| step resets the instances whose reset flag is set before applying the action, and sets that flag when the step count reaches episode_length | upstream_code | leibnizgym/envs/env_base.py:373-395 |
| reset returns the observation tensor [num_instances, obs_dim] | upstream_code | leibnizgym/envs/env_base.py:322-343 |
| The observation spec is robot_q 9, robot_u 9, object_q 7, object_q_des 7 and command 9, 41 values in total for the default action dimension | upstream_code | leibnizgym/envs/trifinger/trifinger_env.py:280-286 |
| seed sets Python's random, NumPy and PyTorch seeds | upstream_code | leibnizgym/envs/env_base.py:312-320 |
| The constructor seeds the environment from its config, whose default seed is 0 | upstream_code | leibnizgym/envs/env_base.py:169 |
| The default physics timestep is 0.02 s and control_decimation is 1, so one environment step advances 0.02 s | upstream_code | leibnizgym/envs/env_base.py:38-49 |
| TrifingerEnv.__init__ takes config, device, verbose and visualize | upstream_code | leibnizgym/envs/trifinger/trifinger_env.py:258 |
| The README states that the repository provides an IsaacGym environment for the TriFinger robot and that it supports IsaacGym Preview Release 2 | vendor_doc | README.md:7-17 |
| The install requirements list numpy, scipy, gym, torch, hydra-core and rl_games, with no serial, VISA, USB or vendor hardware package | upstream_code | setup.py:12-28 |

Limits: the action envelope is the normalized range [-1, 1] of the VecTask action space
(`leibnizgym/wrappers/vec_task.py:34-56`), which the environment denormalizes with `normalize_action` true
(`leibnizgym/envs/trifinger/trifinger_env.py:45-46` and `:654-659`).  The joint position and torque limits above are
internal command scales, not the normalized action input, so the driver does not publish them as input limits.  The
device is simulated (R0); no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaacgym:TrifingerEnv`, level F1 (rigid-body simulation,
no validated device), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (`dt` 0.02 s times
`control_decimation` 1, `leibnizgym/envs/env_base.py:38-49`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore.  The gaps say that the fake models one instance with placeholder kinematics and was not compared
with the upstream environment.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (the upstream has no native stop for a
simulation); after it no step, reset or seed is accepted until `mhs.safety.reset` clears the latch, and the last
observation and tick stay readable.

Tags: trifinger, isaacgym, robot, simulation, reinforcement-learning
