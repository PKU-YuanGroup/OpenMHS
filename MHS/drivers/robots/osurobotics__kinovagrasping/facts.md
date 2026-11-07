# Facts and tags for gh.osurobotics/kinovagrasping

Every fact cites its source at commit `f22af60d3683fdc4ffecf49ccff179fbc6750748`: `vendor_doc` (a text file of
the clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`, as the clone root has it).  The same
facts are declared in `driver.py` and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The action space is a Box whose low is -0.8 and whose high is 0.8 on every element | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:128` |
| The constructor default frame_skip is 15 | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:51` |
| The default hand model declares a timestep of 0.01 s | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_description/j2s7s300_end_effector_v1_mbox.xml:10` |
| The environment sets max_episode_steps to 30 | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:123` |
| The gym registration is kinovagripper-v0 with max_episode_steps 100 | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/__init__.py:3-6` |
| reset takes shape_keys and hand_orientation as positional arguments | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:1310` |
| step returns the observation, reward, done flag and info as a four-tuple | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:1552` |
| seed stores the numpy random generator and returns the seed in a list | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:1487-1489` |
| An action whose length is 4 is padded with two zeros to 6 values | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:1502-1503` |
| The local observation documentation runs from index 0 to index 81 | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:440-454` |
| The object-height target is 0.2 | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:634` |
| The lift reward is 50.0 and done becomes true when the object z is within 0.005 of the target or above it | upstream_code | `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:661-663` |
| Python 3.7 and MuJoCo 1.50 are the documented requirements | vendor_doc | `README.md:7-10` |

The declared observation Box is built at `gym-kinova-gripper/gym_kinova_gripper/envs/kinova_gripper_env.py:211-237`
(minimum and maximum lists and `self.observation_space`).  The registered environment id and its step limit are at
`gym-kinova-gripper/gym_kinova_gripper/__init__.py:3-6`.

Tags (short lowercase keywords): `grasping`, `kinova`, `j2s7s300`, `gym`, `mujoco`,
`reinforcement-learning`, `simulation`.
