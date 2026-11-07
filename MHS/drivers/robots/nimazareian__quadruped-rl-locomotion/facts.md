# Facts and tags for gh.nimazareian/quadruped-rl-locomotion

Every fact cites its source at commit `99763acae393e7d686d006d53310b7b5eaca53e4` in the read-only clone
`robots/nimazareian/quadruped-rl-locomotion`: `vendor_doc` is text of the clone and `upstream_code` is code or a
comment of the clone. The list is generated into `driver.py` `facts`; both copies say the same thing.

| fact | source | ref |
|---|---|---|
| The repository is a custom Gymnasium environment for training quadruped locomotion with reinforcement learning in the MuJoCo simulator, set up for the Unitree Go1 robot | vendor_doc | `README.md:3` |
| The repository provides two MJCF models for the Go1: one tuned for position control with a proportional controller and one that directly takes torque values | vendor_doc | `README.md:5` |
| The environment imports MujocoEnv from gymnasium.envs.mujoco | upstream_code | `go1_mujoco_env.py:2` |
| The class Go1MujocoEnv subclasses that MujocoEnv | upstream_code | `go1_mujoco_env.py:21` |
| The Go1MujocoEnv constructor defaults ctrl_type to 'torque' and builds ./unitree_go1/scene_{ctrl_type}.xml, so its default model is unitree_go1/scene_torque.xml | upstream_code | `go1_mujoco_env.py:32-33` |
| The environment performs an action every 10 frames and its comment states dt 0.002 s, so one action covers 0.02 s (50 Hz) | upstream_code | `go1_mujoco_env.py:37` |
| The environment limits an episode to 15.0 s | upstream_code | `go1_mujoco_env.py:53` |
| The desired velocity is vx 0.5 m/s, vy 0 and wz 0 rad/s | upstream_code | `go1_mujoco_env.py:80-82` |
| An episode is healthy while the trunk height is between 0.22 and 0.65 m | upstream_code | `go1_mujoco_env.py:93` |
| The healthy roll and pitch ranges are +-10 degrees | upstream_code | `go1_mujoco_env.py:94-95` |
| The action is 12 torque values | upstream_code | `go1_mujoco_env.py:119` |
| The scene root is '<mujoco model="go1 scene">' and it includes go1_torque.xml | upstream_code | `unitree_go1/scene_torque.xml:1-2` |
| The robot model declares '<compiler angle="radian" meshdir="assets" autolimits="true"/>', so its joint ranges are radians and its meshes are resolved from assets/ | upstream_code | `unitree_go1/go1_torque.xml:2` |
| The model selects an elliptic friction cone with impratio 100 | upstream_code | `unitree_go1/go1_torque.xml:4` |
| The global default sets a motor with ctrllimited true and ctrlrange -1.0 to 1.0 | upstream_code | `unitree_go1/go1_torque.xml:7` |
| The robot trunk is a body at 0 0 0.445 with a free joint and mass 5.204 kg | upstream_code | `unitree_go1/go1_torque.xml:83-88` |
| The joint default classes give the abduction joints range -0.863 to 0.863, the hip joints -0.686 to 4.501 and the knee joints -2.818 to -0.888 rad | upstream_code | `unitree_go1/go1_torque.xml:14-23` |
| The actuator block has 12 <motor> elements, one per leg joint; the hip and thigh motors state gear 23 and the calf motors gear 35 | upstream_code | `unitree_go1/go1_torque.xml:212-228` |
| The home keyframe states qpos '0 0 0.30 1 0 0 0 0 0.9 -1.8 0 0.9 -1.8 0 0.9 -1.8 0 0.9 -1.8' and ctrl all zeros | upstream_code | `unitree_go1/go1_torque.xml:230-233` |
| The scene adds a plane geom named floor with a checker groundplane material | upstream_code | `unitree_go1/scene_torque.xml:14-21` |
| The MJCF description is a simplified robot description of the Go1 derived from the publicly available Unitree URDF description | vendor_doc | `unitree_go1/README.md:7-11` |
| The model package requires MuJoCo 2.2.2 or later and is released under a BSD-3-Clause License | vendor_doc | `unitree_go1/README.md:3-27` |

The scene's model shape is not copied into a Limit: the bridge derives the step envelope from the loaded model's
`actuator_ctrlrange`, so the control bound is the MJCF's `-1.0 1.0` (go1_torque.xml:7) and not a number of this
package.

Tags (short lowercase keywords): `go1`, `mujoco`, `quadruped`, `reinforcement-learning`, `robot`, `simulation`,
`unitree`.
