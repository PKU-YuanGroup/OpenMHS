# Facts and tags for gh.qiangwang-academic/ur5e_robot_gym_env_real_and_sim

Every fact cites its source at commit `513acb7e235ab940fd03c3038208678e285690f3`: `vendor_doc` (a text file of
the clone) or `upstream_code` (`path/in/clone:LINE`).  The same facts are in `facts = [...]` in `driver.py`;
the reference is generated from the driver, not from this page.

Tags: `ur5`, `coppeliasim`, `gym`, `reaching`, `robot-arm`, `simulation`.

## Facts

| fact | source | ref |
|---|---|---|
| Simulation/README.MD names CoppeliaSim_UR5_gym_v0.py and CoppeliaSim_UR5_gym_v3.py as the environment code and says its format is gym format | vendor_doc | Simulation/README.MD:14-15 |
| The v3 entry class is CoppeliaSim_UR5_gym_v3, a subclass of CoppeliaSim_UR5_base and gym.Env | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:54 |
| The action_low and action_high lists are [-5, -5, -5, -5] and [5, 5, 5, 5] | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:45-46 |
| action_space is spaces.Box(low_action, high_action, dtype=np.float32) | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:93-97 |
| The observation space is a Box of shape (128,128,3) with float32 values from 0 to 255 | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:78-89 |
| The reset target joint vector init_joints_pos is [0.0, 0.0, 0.0, 0.0, pi/2, 0.0] | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:99 |
| DELTA is pi/180.0 rad and MOVE_UNIT is 2*DELTA | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:21-33 |
| apply_action multiplies action[0..3] by MOVE_UNIT and adds it to current_joint_pos[0..3] | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:210-218 |
| REACH_THRESHOLD is 0.08 | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:22 |
| check_done reports step_end_status 1 when current_dis is at most REACH_THRESHOLD | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:237-239 |
| The tip safety box is x [-0.72, 0.72], y [-1.025, 0.275], z [0.66, 1.8] | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:30-32 |
| check_done reports step_end_status 2 when the tip leaves the safety box | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:247-265 |
| The joint limits are joint1 [-pi, pi], joint2 [-pi/2, pi/2], joint3 [-pi, pi] and joint4 [-pi, pi] | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:38-41 |
| check_done reports step_end_status 2 when a joint reaches its limit | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:269-297 |
| STAY_THRESHOLD is 0.1 and STAY_FLAG is 30 | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:26-27 |
| check_stay returns step_end_status 3 when at least 25 of the last 30 tip positions are within STAY_THRESHOLD of the current one | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:321-329 |
| step rewards (last_dis - current_dis) * 100, pays -150 when step_end_status is 2, and adds 2000 / tra_num_step on reaching the target | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:164-207 |
| target_range_low is [-0.343, -0.737, 0.685] and target_range_high is [0.041, -0.003, 0.685] | upstream_code | Simulation/CoppeliaSim_UR5_base.py:26-27 |
| random_gen_one_target_pos draws the next target uniformly between target_range_low and target_range_high | upstream_code | Simulation/CoppeliaSim_UR5_base.py:111-113 |
| seed() fills self.np_random with gym.utils.seeding.np_random | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:154-156 |
| step returns the legacy four-value tuple (next_state, reward, done, info) | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:207 |
| get_state returns the Side_camera1 image from the simulator | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:158-162 |
| MAX_STEP is 200 | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:35 |
| reset sets num_step to 0 and tra_num_step to -1 | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:118-119 |
| check_done compares num_step with MAX_STEP | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:241 |
| apply_action increments tra_num_step, not num_step | upstream_code | Simulation/CoppeliaSim_UR5_gym_v3.py:231 |
| The environment opens CoppeliaSim's legacy remote API at 127.0.0.1:19998 before it can run | upstream_code | Simulation/CoppeliaSim_env.py:44 |
| The recorded environment pins gym 0.18.3, the legacy four-value step API | vendor_doc | Simulation/requirement_reach.txt:41 |

The seed fact is the reason the fake adds seed control of its own target draw: the upstream `seed()` fills
`self.np_random`, but `random_gen_one_target_pos` uses numpy's global `np.random.uniform`, so the upstream
simulator is not reproducible from that seed.  The driver's fidelity notes disclose the difference.

## Native interface

The driver declares no reads, writes or actions of its own: the Gymnasium family bridge serves the environment
through the three `cap.world.*` classes derived from the environment's spaces.

| direction | upstream member | kind | unit / range |
|---|---|---|---|
| read | `get_state()` | camera image | 128 x 128 x 3 float32 pixels, 0 to 255 (v3:78-89, 158-162) |
| reset | `reset()` | scene recovery + target draw + move to `init_joints_pos` | six joint angles in rad (v3:99, 105-124) |
| action | `step(action)` | four joint increments, legacy four-value return | each increment -5 to 5; joint delta = increment * 2*pi/180 rad (v3:45-46, 210-218) |
| seed | `seed(seed)` | fills `self.np_random`; the target draw uses global `np.random` | non-negative integer or `None` (v3:154-156) |
| stop | not defined by the environment | the runtime's software latch stops accepting step and reset; there is no hardware stop and no hardware backend | simulated, R0 |

The only bound the contract derives is the action `Box` over four joints, low -5 and high 5 per element
(v3:45-46 and 93-97).  The bridge derives it from `fake.py`'s action space; no operator-required bound is
declared because the simulated device has no physical effect.

## Stop path

There is no hardware.  `safe_state` is the runtime's e-stop latch: after `client.estop(...)` the runtime refuses
`cap.world.step.v1` and `cap.world.reset.v1` with `MHS.SAFETY.ESTOP_ENGAGED` until `mhs.safety.reset`, and the
world state stays readable.  The upstream class has no stop method of its own; the CoppeliaSim connection is
part of the simulator, not a device stop.

## Mock path

The card's `mock_strategy.preferred` is `upstream-sim`, but the upstream simulator is not usable under the
acceptance gate: its constructor opens the legacy remote API at 127.0.0.1:19998 (CoppeliaSim_env.py:44), loads a
`reach_task.ttt` scene and reads a camera.  The package therefore ships `fake.py`, a pure Python stand-in for the
`CoppeliaSim_UR5_gym_v3` class surface.  It is kinematic (fidelity F0), returns a 4x4x3 test image instead of the
128x128x3 camera image, and was never compared with the simulator or a real UR5; the fidelity `gaps` list every
difference.

## Units and ranges

- Joint angles are radians; `init_joints_pos` is `[0, 0, 0, 0, pi/2, 0]` (v3:99).
- Action increments are dimensionless factors in [-5, 5] (v3:45-46); one unit adds `2*pi/180` rad to a joint (v3:21, 33, 211-214).
- Distances are metres: reach threshold 0.08 (v3:22), stay threshold 0.1 (v3:26), target range and safety box in the same frame as `UR5_global_position` (base:23-27, v3:30-32).
- Reward is dimensionless: `(last_dis - current_dis) * 100`, -150 on `step_end_status` 2, and `2000 / tra_num_step` on reaching (v3:164-207).
