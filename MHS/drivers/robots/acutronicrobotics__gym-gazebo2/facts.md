# Facts and tags for gh.acutronicrobotics/gym-gazebo2

Every fact cites its source at commit `545e203e07895927fd7aae66596d83d97ee89fe5`. The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| gym-gazebo2 describes itself as a toolkit for developing and comparing reinforcement learning algorithms using ROS 2 and Gazebo, built as an extension of gym-gazebo | vendor_doc | README.md:5 |
| The installation instructions require ROS 2 Dashing and Gazebo 9.9.0, and state that lower versions such as 9.0.0 will not work | vendor_doc | INSTALL.md:17-22 |
| The package registers MARA-v0 with entry point gym_gazebo2.envs.MARA:MARAEnv | upstream_code | gym_gazebo2/__init__.py:6-9 |
| MARAEnv is a subclass of gym.Env | upstream_code | gym_gazebo2/envs/MARA/mara.py:40 |
| MARAEnv launches the Gazebo launch description returned by generateLaunchDescriptionMara in a new service process | upstream_code | gym_gazebo2/envs/MARA/mara.py:67-69 |
| The MARA launch description starts gzserver or gazebo with libgazebo_ros_factory.so and libgazebo_ros_init.so, then the MARA spawn and cognition nodes | upstream_code | gym_gazebo2/utils/ut_launch.py:142-155 |
| MARAEnv publishes JointTrajectory commands on /mara_controller/command, subscribes to JointTrajectoryControllerState on /mara_controller/state and /gazebo_contacts, and creates an Empty client for /reset_simulation | upstream_code | gym_gazebo2/envs/MARA/mara.py:148-152 |
| The number of joints comes from the KDL chain and the observation dimension is numJoints + 6 + 12 | upstream_code | gym_gazebo2/envs/MARA/mara.py:160-164 |
| The action space is Box(-pi, pi) over numJoints and the observation space is Box(-inf, inf) of obs_dim | upstream_code | gym_gazebo2/envs/MARA/mara.py:169-176 |
| take_observation concatenates joint positions, end-effector position error, end-effector velocities, current end-effector position and a 9-element rotation matrix | upstream_code | gym_gazebo2/envs/MARA/mara.py:272-276 |
| getTrajectoryMessage writes the action values into JointTrajectoryPoint.positions and the configured velocity into velocities | upstream_code | gym_gazebo2/utils/ut_mara.py:84-102 |
| seed() seeds numpy's generator through seeding.np_random and returns [seed] | upstream_code | gym_gazebo2/envs/MARA/mara.py:294-296 |
| step() publishes the trajectory, takes an observation, calls collision(), computes the reward, sets done when iterator equals max_episode_steps, and returns the legacy four-tuple (obs, reward, done, info) | upstream_code | gym_gazebo2/envs/MARA/mara.py:298-354 |
| MARAEnv sets max_episode_steps to a default of 1024 that baselines can update | upstream_code | gym_gazebo2/envs/MARA/mara.py:77-77 |
| collision() calls the /reset_simulation service when a contact message was received since the last check | upstream_code | gym_gazebo2/envs/MARA/mara.py:280-292 |
| take_observation() calls rclpy.spin_once in a loop until a controller state message passes its stamp check; the loop has no timeout | upstream_code | gym_gazebo2/envs/MARA/mara.py:235-243 |
| reset() calls the /reset_simulation service, resets iterator and returns only the observation | upstream_code | gym_gazebo2/envs/MARA/mara.py:356-376 |
| close() destroys the ROS node, kills the launch process and its children, and shuts rclpy down | upstream_code | gym_gazebo2/envs/MARA/mara.py:378-385 |
| MARAEnv.__init__ parses the process command line with getArgsParserMARA().parse_args() | upstream_code | gym_gazebo2/envs/MARA/mara.py:49-50 |
| MARARealEnv starts the launchReal description in a new launch service process | upstream_code | gym_gazebo2/envs/MARA/mara_real.py:44-45 |
| launchReal runs the hros_cognition_mara_components node with the motors.yaml configuration and the real argument | upstream_code | gym_gazebo2/utils/ut_launch.py:158-168 |
| MARARealEnv uses /mara_controller/command for its robot publisher and /mara_controller/state for its subscriber | upstream_code | gym_gazebo2/envs/MARA/mara_real.py:72-74 |
| MARARealEnv.step() publishes ut_mara.getTrajectoryMessage(action[:numJoints], ...) on self._pub | upstream_code | gym_gazebo2/envs/MARA/mara_real.py:222-228 |

## Limits

The driver declares no `Limit`. The bridge derives the `cap.world.step.v1` action bounds from the environment's
action space. The fake copies the upstream `Box(-pi, pi)` over `numJoints` (`mara.py:169-172`), and `driver.py`
sets `action_space_ref = "gym_gazebo2/envs/MARA/mara.py:169-172"` so those derived bounds are `upstream_code`.
The number of joints is read from the MARA chain at run time (`mara.py:160-164`); the fake's dimension 6 follows
the six-joint `JOINT_ORDER` (`mara.py:123-124`) and is not a separately invented bound. The values are absolute
joint-position targets (`ut_mara.py:84-102`), in radians for MARA's revolute joints by ROS convention (the clone
states no unit). `cap.world.reset.v1` and `cap.world.seed.v1` inputs are
bounded by their catalogue classes. The device risk is R2 (REVIEW.md item 12): `MARAEnv` publishes
`JointTrajectory` commands on `/mara_controller/command` (`mara.py:99`, `149`), and `MARARealEnv`
publishes the same topic (`mara_real.py:72-74`, `222-228`). The package still declares no `Limit` of
its own, so no bound is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity`: engine `gym-gazebo2:MARA-v0 analytic fake (no Gazebo, no ROS 2)`, level F0, determinism
`seeded` with `seed_control` `parameter`, `timestep_ms` 0, `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore. The fake is an analytic kinematic stand-in, not a recording. Every number it emits is
test data marked `# placeholder`; the 24-value observation size and the ±pi action bounds are the upstream code's
(the action bound is the fake's copy and is cited by `action_space_ref`, per the authoring guide). The gaps say
what is not modelled and that the fake was never compared with the upstream environment.

## Safety

Device risk R2, an arm. There is no hardware transport and no native stop; the e-stop is the runtime's software
latch. After an e-stop every step, reset and seed is refused until `mhs.safety.reset` clears the latch, and
the last observation and tick stay readable. The upstream environment exposes no `get_state`/`set_state`, so a
snapshot is not offered. In a live MARA-v0 deployment Gazebo runs in its own process: the latch neither pauses
Gazebo nor publishes a zero `JointTrajectory`, so the controller keeps executing the last command, and it
cannot interrupt a native step() or reset() that waits without a timeout for a controller state
(`mara.py:235-243`).

This package does not serve MARAReal-v0 (`MARARealEnv`). That class starts `launchReal` (the
`hros_cognition_mara_components` node in real mode) and publishes the action as a `JointTrajectory` on
`/mara_controller/command` (`mara_real.py:44-45`, `72-74`, `222-228`; `ut_launch.py:158-168`). The served
`MARAEnv` publishes that same topic, which is why this simulated package is R2. It still declares no hardware
backend.

## Tags

gym-gazebo2, mara, robot-arm, ros2, gazebo, simulation, gymnasium
