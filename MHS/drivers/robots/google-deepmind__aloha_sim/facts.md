# Facts and tags for gh.google-deepmind/aloha_sim

Every fact cites its source at commit `d02904607cca1bf6dfb72f30b522506ac7ca0f91`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

The package serves the card's main model, the MJCF scene `aloha_sim/assets/aloha/aloha_pbr.xml` (`models[0]`), as a
`MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the model nor its assets.

| fact | source | ref |
|---|---|---|
| The card's main model is the MJCF scene aloha_pbr.xml, whose root element is '<mujoco model="aloha">' | upstream_code | aloha_sim/assets/aloha/aloha_pbr.xml:17 |
| The scene_pbr.xml scene includes aloha_pbr.xml | upstream_code | aloha_sim/assets/aloha/scene_pbr.xml:26 |
| aloha_pbr.xml includes the actuator definitions of joint_position_actuators.xml | upstream_code | aloha_sim/assets/aloha/aloha_pbr.xml:304 |
| The model has 14 position actuators, seven per arm: waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate and finger | upstream_code | aloha_sim/assets/aloha/joint_position_actuators.xml:19-33 |
| The control range of an actuator comes from the default class of its element: waist, forearm_roll and wrist_rotate +-3.14158, shoulder -1.85005 to 1.25664, elbow -1.76278 to 1.6057, wrist_angle -1.8675 to 2.23402, finger 0.002 to 0.037 | upstream_code | aloha_sim/assets/aloha/aloha_pbr.xml:50-96 |
| The finger control range 0.002 to 0.037 m is described as the limits the real robot enforces in software on its gripper travel | upstream_code | aloha_sim/assets/aloha/aloha_pbr.xml:75-96 |
| The model sets no option timestep: its <option> element carries only cone and impratio | upstream_code | aloha_sim/assets/aloha/aloha_pbr.xml:20 |
| The two fingers of one gripper are coupled by an equality constraint | upstream_code | aloha_sim/assets/aloha/aloha_pbr.xml:299-301 |
| The model has a neutral_pose keyframe with one qpos value per joint and one ctrl value per actuator | upstream_code | aloha_sim/assets/aloha/joint_position_actuators.xml:36-43 |
| The 16 qpos values are the eight joints of each arm (six hinges and two finger slides); the 14 ctrl values are the seven actuators of each arm | upstream_code | aloha_sim/assets/aloha/joint_position_actuators.xml:37-42 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file), so no
`operator_required` bound is needed. The finger interval is the software limit the model states in its comment
(`aloha_pbr.xml:75-96`).

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file for
the actuator count and control ranges and the number of joints, but its integration is a placeholder first-order
motion, and it resolves no mesh, contact, equality or tendon constraint. MuJoCo was not importable where the gate ran
(no network, no pip), so no trajectory was compared with the real engine. The gaps are listed in the `fidelity`
attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a backend that imports MuJoCo.

Tags: aloha, bimanual, manipulation, mujoco, simulation, robot
