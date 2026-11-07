OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.rvl-lab-utoronto/panda_robot

Every fact cites the pinned clone at commit `494e9db28a8b38290a3339fea3644379f3d5b9ad`:
`vendor_doc` is documentation text in the clone (README.md), and `upstream_code` is Python or
build source.  The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes Gym-like interfaces through ROS for the real Franka Emika Panda arm, for reinforcement-learning prototyping. | vendor_doc | README.md:3 |
| The documented deployment has two Ubuntu 18.04 machines: a real-time Linux NUC connected directly to the Franka FCI computer and a second ROS machine connected to the NUC. | vendor_doc | README.md:7 |
| The installation assumes ROS Melodic, libfranka 0.5 and franka_ros, with franka_ros built from source on the melodic-devel branch. | vendor_doc | README.md:10 |
| Running the Gym environments is documented as launching panda_robot.launch and kinect_azure.launch, then running panda_env_test.py; the test should move the robot along x, y and z in cartesian velocity mode and occasionally reset it to the home configuration. | vendor_doc | README.md:49-65 |
| PandaReacherEnv is the concrete reacher environment class and derives from gym.Env. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:23 |
| PandaReacherEnv.__init__ starts a ROS node named panda_robot_reacher_v0, sets dt to 0.1 s (a 10 Hz rate), and builds PandaClient with the end-effector safety zone [[0.2, 0.7], [-0.3, 0.05], [0.15, 0.4]] and Kinect enabled. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:26-32 |
| PandaReacherEnv stores hole_goal (0.455, -0.005, 0.25), threshold 0.05, sparse False and _max_episode_steps 50. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:33-36 |
| PandaReacherEnv.apply_velocity_action copies action[0], action[1] and action[2] into Twist.linear.x, .y and .z and calls PandaClient.set_ee_velocity. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:38-43 |
| The dense reward is minus the Euclidean distance to hole_goal; the sparse branch returns -(distance >= threshold). | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:45-58 |
| PandaReacherEnv.preprocess_action returns the action unchanged. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:60-61 |
| PandaReacherEnv.step applies the action, sleeps one rate period, reads the observation, computes the reward and done = distance < threshold, and returns a four-tuple (observation, reward, done, info); it does not test _max_episode_steps. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:63-76 |
| PandaReacherEnv.reset calls PandaClient.go_home() and returns the observation. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:78-81 |
| PandaReacherEnv.get_obs concatenates PandaClient.O_P_EE and O_V_EE, the end-effector position and velocity, into one observation. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:83-89 |
| PandaReacherEnv.close publishes a zero linear velocity through set_ee_velocity. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:91-96 |
| PandaReacherEnv imports PandaClient as a top-level module (from panda_client import PandaClient), not as a package-relative import. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:9 |
| PandaClient creates actionlib clients for /franka_gripper/homing, /franka_gripper/move and /franka_gripper/grasp. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:98-103 |
| PandaClient creates an actionlib client for /franka_control/error_recovery. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:160-161 |
| PandaClient publishes Twist commands on /franka_control/target_velocity with queue size 1 and subscribes to /franka_control/current_target_velocity. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:169-171 |
| PandaClient subscribes to /franka_state_controller/franka_states with franka_msgs/FrankaState and stores the message in update_state. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:173-175 |
| PandaClient.set_ee_velocity clips only velocity components that would move the end effector farther outside the configured safety zone, then publishes the Twist on /franka_control/target_velocity. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:320-353 |
| PandaClient.go_home switches to the position joint trajectory controller when it is not running, moves to a fixed home joint configuration and switches back to the cartesian velocity controller. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:364-380 |
| PandaClient contains Python 2 print statements, for example print "Waiting for gripper homing server". | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:105 |
| PandaClient uses the Python 2 exception syntax except rospy.ServiceException, e:. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:396 |
| The gym package registers panda-robot-reacher-v0 with entry point gym_panda_robot.envs:PandaReacherEnv and panda-robot-reacher-v1 with entry point gym_panda_robot.envs:PandaReacherEnv1. | upstream_code | src/gym-panda-robot/gym_panda_robot/__init__.py:3-10 |
| The envs package imports PandaReacherEnv from panda_reacher_env and PandaReacherEnv1 from gym_panda_robot.envs.panda_reacher_manga; no panda_reacher_manga module exists in the clone. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/__init__.py:1-2 |
| The top-level package registers panda-robot-v0 with entry point gym_panda_robot.envs:PandaPegInHoleEnv. | upstream_code | src/__init__.py:3-6 |
| PandaPegInHoleEnv imports PandaBaseEnv from panda_base_env; no panda_base_env module exists in the clone. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_peg_in_hole.py:12 |
| PandaPegInHoleEnv.step is declared with no action parameter and then refers to an undefined action variable. | upstream_code | src/gym-panda-robot/gym_panda_robot/envs/panda_peg_in_hole.py:45-47 |
| The gym package declares only gym as its install dependency. | upstream_code | src/gym-panda-robot/setup.py:5 |

## Scope

The package serves the registered `panda-robot-reacher-v0` environment through
`PandaReacherEnv` (`src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:23`).  It does
not serve the other card entries: `PandaPegInHoleEnv` is not exported by the `envs` package, imports
a missing `panda_base_env`, and its `step` has no action parameter;
`PandaReacherEnv1` is registered but the module that would define it is missing
(`src/gym-panda-robot/gym_panda_robot/envs/__init__.py:1-2`).  The upstream is an old Gym
environment, not a ROS topic/service declaration, so the card's `RosDriver` cannot express its
step/reset interface; the package uses `GymnasiumDriver` and records the deviation in RESULT.json.

The environment is hardware-in-the-loop: `step` writes a `geometry_msgs/Twist` through
`PandaClient.set_ee_velocity` on `/franka_control/target_velocity`
(`src/gym-panda-robot/gym_panda_robot/envs/panda_client.py:320-353`), and `reset` calls
`PandaClient.go_home()` (`src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py:78-81`).
The clone has no simulator or mock; the only executable backend in this package is the analytic
fake in `fake.py`.  A live run would need the Python 2/ROS Melodic deployment, libfranka, MoveIt,
franka_ros, a Franka control computer and the arm; no live or `sim` backend is declared or was run.

## Limits

The driver declares no `Limit`.  The only bound is the `cap.world.step.v1` action space, which the
bridge derives from the fake's `Box(-1, 1)` over three values; those bounds are **placeholders**,
not upstream facts, because the upstream class defines no action space and applies no value bound
or clipping to the three Twist components (`panda_reacher_env.py:38-43,60-61`).  The package does
not set `action_space_ref`; the reference shows the fake as the origin.  `ticks` is bounded by the
bridge's `max_ticks` (10000).  The device is simulated at R0, so no input is `operator_required`.

## Fidelity contract

`driver.py` declares the deployed fake: engine `analytic:pure-Python PandaReacherEnv fake (no ROS,
no arm, no physics)`, level F0, determinism `seeded` with `seed_control` `parameter` (the fake
accepts a seed but has a fixed trajectory), `timestep_ms: 0`, `realtime_factor: 0`, clock
`lockstep`, reset `full`, no snapshot/restore.  The gaps disclose the absent ROS/arm integration,
the placeholder action/start/goal/threshold data, the Python 2/missing-module state of the clone,
the old Gym four-tuple adaptation, and the absent rendering and time limit.

## Safety

The device is simulated at R0 and serves an isolated fake.  There is no native stop and no ROS or
hardware backend.  The e-stop is the runtime's software latch: after it, step, reset and seed are
refused until `mhs.safety.reset` clears the latch, and the last fake state stays readable.  This is
not a robot stop, does not claim physical quiescence and does not lower the risk of a real Panda
binding, which would be at least R2 and would need a human-reviewed deployment and an independent
physical stop.

## Model review (r20)

The environment has no hardware-free path: the README and PandaClient target a real Franka Panda through
franka_ros (README.md:3, 7, 49-65; panda_client.py:169-175), and the clone has no simulator or mock. It also does
not load as shipped: `gym_panda_robot.envs` imports the missing `panda_reacher_manga` module (envs/__init__.py:1-2),
so the registered entry points fail, and `panda_client.py` is Python 2. As for applied-ai-lab/ramp, the package is
blocked (`NO_HARDWARE_FREE_PATH`); the device it describes is an arm (R2), while this fake contract keeps R0. The
only stop-like call, `close()`, publishes an unacknowledged zero Twist; `go_home()` moves the arm.

## Licensing

The pinned clone contains no LICENSE file and the registry/licence fields are `NOASSERTION` /
`unknown`.  This model-authored package is not a publication decision; publication review remains
required and `reviewed_by` stays null.

## Tags

`franka`, `panda`, `ros`, `gym`, `reinforcement-learning`, `simulation`, `fake`
