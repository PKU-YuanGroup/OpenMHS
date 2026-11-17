# Facts and scope for gh.soltanilara/av-aloha

Facts cite the read-only source at commit `65da5200dda9200ced58bc3dadb5345f4703d017`. The table matches the Fact declarations in driver.py and the generated reference.json.

| Fact | Source | Ref |
|---|---|---|
| The ENVS entry for gym_guided_vision/InsertPeg-3Arms-v0 selects InsertPegEnv with num_arms=3, six cameras and 480x640 observations | upstream_code | `gym_guided_vision/gym_guided_vision/__init__.py:6-12` |
| The registry loop constructs entry points as gym_guided_vision.env followed by the ENVS class name | upstream_code | `gym_guided_vision/gym_guided_vision/__init__.py:88-91` |
| The six camera names are zed_cam_left, zed_cam_right, wrist_cam_left, wrist_cam_right, overhead_cam and worms_eye_cam | upstream_code | `gym_guided_vision/gym_guided_vision/constants.py:8-15` |
| The observation space is a Dict of per-camera Box(480, 640, 3) uint8 pixels and an agent_pos Box of num_joints float64 values | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:36-85` |
| The action space is Box(-inf, inf, (num_joints,), float32) | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:87` |
| num_joints is 21 for three arms and 14 for two arms | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:60-64` |
| The physics timestep is 0.002 s and 20 physics steps make one environment step (SIM_DT 0.04 s) | upstream_code | `gym_guided_vision/gym_guided_vision/constants.py:20-23` |
| step advances the physics by SIM_PHYSICS_ENV_STEP_RATIO physics steps | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:217-218` |
| step applies six left joint targets and the left gripper, six right joint targets and the right gripper, and the seven middle joint targets when num_arms is 3 | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:203-226` |
| The gripper normalization divides by the model's ctrlrange span and the unnormalization multiplies back | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:156-161` |
| step documents the left and right gripper actions as values from 0 to 1 | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:203-207` |
| reset restores the physics, applies the fixed arm poses and open-gripper commands, calls forward and returns the observation with is_success False | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:228-249` |
| The base step always returns terminated=False and truncated=False, and reports success only in info as reward == max_reward | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:222-224` |
| InsertPegEnv sets max_reward to 4 | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:420` |
| InsertPegEnv.get_reward starts at 0, sets 1 for both gripper contacts, 2 for both gripper contacts without either table contact, 3 for peg-hole contact without either table contact, and finally 4 for pin contact | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:425-472` |
| InsertPegEnv.reset draws the peg and hole placements from the global numpy RNG with np.random.uniform after the seeded super().reset | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:474-496` |
| The environments are registered with nondeterministic=True because even seeded rendered observations differ slightly | upstream_code | `gym_guided_vision/gym_guided_vision/__init__.py:88-94` |
| close closes the passive viewer when one was opened | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:400-408` |
| SlotInsertionEnv loads task_slot_insertion.xml and sets max_reward to 4 | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:503-508` |
| SewNeedleEnv loads task_sew_needle.xml and sets max_reward to 5 | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:592-597` |
| TubeTransferEnv loads task_tube_transfer.xml and sets max_reward to 3 | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:693-698` |
| HookPackageEnv loads task_hook_package.xml and sets max_reward to 4 | upstream_code | `gym_guided_vision/gym_guided_vision/env.py:782-787` |
| The separate RealEnv imports InterbotixManipulatorXS, JointSingleCommand and rospy | upstream_code | `data_collection_scripts/real_env.py:28-30` |
| RealEnv.reset reboots gripper motors, opens and closes grippers, then moves all three arms | upstream_code | `data_collection_scripts/real_env.py:176-185` |
| The simulation assets LICENSE names Trossen Robotics and has three redistribution conditions | vendor_doc | `gym_guided_vision/gym_guided_vision/assets/LICENSE:1-16` |

## Served contract and limits

Only InsertPeg-3Arms is served. GuidedVisionEnv is the base; SlotInsertionEnv, SewNeedleEnv, TubeTransferEnv and
HookPackageEnv are separate task classes. The data_collection_scripts/real_env.py RealEnv controls physical arms
through ROS/Interbotix and its reset reboots motors and moves the arms; it is outside this R0 simulation package.

The fake copies the selected environment's 21-value unbounded Box from env.py:87, so no finite action limit is
derived. Gripper elements 6 and 13 are normalized values and the other components are joint-position targets;
the vector has mixed units. No finite device envelope is claimed.

## Fidelity and safety

fidelity_by_backend selects analytic:av-aloha-insert-peg-fake, F0, exact determinism and no seed control for the fake:
it has fixed placeholder arm poses and pixels, no task objects and reward 0. The upstream differs: InsertPegEnv
places objects through the global numpy RNG and its registration marks nondeterministic=True. Accepting a seed
at the bridge does not validate upstream seed reproducibility.

The fake has no rigid-body dynamics, contacts, gravity, constraints or actuator dynamics. Its joints immediately
follow targets. It returns 2x2x3 placeholder images while declaring the upstream's six 480x640x3 cameras; this size
gap is explicit and no rendered observation was compared. The control period is 40 ms, lockstep with no wall-clock
pacing, full reset and no snapshot/restore. The software latch freezes the fake once in-flight work settles and
refuses step, reset and seed until a safety reset; it does not stop the separate physical RealEnv.

The card records NOASSERTION and publish_review: required. The simulation assets carry a separate Trossen
Robotics three-clause redistribution notice; it does not establish a licence for all repository code. Publication
requires an owner licence decision. No upstream simulator, ROS graph or hardware execution was performed.

Tags: av-aloha, aloha, gymnasium, mujoco, manipulation, insert-peg, simulation
