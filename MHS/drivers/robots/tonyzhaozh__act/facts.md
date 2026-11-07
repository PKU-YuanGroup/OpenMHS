# Facts and tags for gh.tonyzhaozh/act

Every fact cites its source at commit `742c753c0d4a5d87076c8f69e5628c79a8cc5488`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

The package serves the joint-space insertion scene `assets/bimanual_viperx_insertion.xml` (the card's `models[2]`) as
a `MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the model nor its
assets. The end-effector scenes in the card are not served because their arms are driven through mocap bodies
(`ee_sim_env.py:63-74`) and their actuator section has only the four finger actuators
(`assets/bimanual_viperx_ee_insertion.xml:45-50`), which the `MujocoDriver` bridge does not expose.

| fact | source | ref |
|---|---|---|
| The insertion scene is the MJCF file bimanual_viperx_insertion.xml; its root element is <mujoco> and it includes scene.xml and vx300s_dependencies.xml | upstream_code | assets/bimanual_viperx_insertion.xml:1-3 |
| The scene includes the left and right ViperX arm bodies from vx300s_left.xml and vx300s_right.xml | upstream_code | assets/bimanual_viperx_insertion.xml:5-6 |
| The scene adds a free peg body and a free socket body, each with a free joint | upstream_code | assets/bimanual_viperx_insertion.xml:8-23 |
| The actuator section lists a position actuator for the six joints and two finger slides of each arm; the control ranges are waist +-3.14158, shoulder -1.85005 to 1.25664, elbow -1.76278 to 1.6057, forearm_roll +-3.14158, wrist_angle -1.8675 to 2.23402, wrist_rotate +-3.14158, left_finger 0.021 to 0.057 and right_finger -0.057 to -0.021 | upstream_code | assets/bimanual_viperx_insertion.xml:27-44 |
| The keyframe stores 30 qpos values: the 16 arm and finger values, seven for the peg and seven for the socket | upstream_code | assets/bimanual_viperx_insertion.xml:48-49 |
| The upstream joint-space insertion environment loads bimanual_viperx_insertion.xml | upstream_code | sim_env.py:44-46 |
| The upstream control timestep is DT = 0.02 s | upstream_code | constants.py:36 |
| The insertion environment is built with control_timestep=DT and time_limit=20 | upstream_code | sim_env.py:48 |
| The upstream joint-space action is 14 values: six left arm joints, one left gripper, six right arm joints and one right gripper | upstream_code | sim_env.py:23-26 |
| The task expands each normalized gripper action into two finger control values before stepping the model | upstream_code | sim_env.py:67-70 |
| The insertion task initialises qpos[:16] to START_ARM_POSE and copies START_ARM_POSE into data.ctrl | upstream_code | sim_env.py:180-181 |
| START_ARM_POSE has 16 values, eight per arm | upstream_code | constants.py:38 |
| The only <option> in the scene is commented out, so the model sets no active integration timestep | upstream_code | assets/scene.xml:2 |
| The end-effector insertion scene has only the four finger actuators | upstream_code | assets/bimanual_viperx_ee_insertion.xml:45-50 |
| The end-effector task drives the arms through mocap positions and quaternions and writes only four gripper values to data.ctrl | upstream_code | ee_sim_env.py:63-74 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file), so the
driver declares no `Limit` of its own and no `operator_required` bound is needed. The cited actuator lines show every
interval.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the include-expanded
MJCF for the actuator count and control ranges and the joint dimensions, but its integration is a placeholder
first-order motion, it loads no STL mesh, and it resolves no contact, equality or tendon constraint. The model sets no
active `<option timestep>` (`assets/scene.xml:2` is commented out), so the fake uses the MuJoCo library default step
as a placeholder only. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was
compared with the real engine. The gaps are listed in the `fidelity` attribute of `driver.py`; a site that needs
MuJoCo's physics runs the driver with a backend that imports MuJoCo.

The task layer is not served: the bridge exposes the raw 16-value `data.ctrl` and the model's `qpos`/`qvel`, while the
upstream `BimanualViperXTask` takes a 14-value action and expands each gripper to two finger positions
(`sim_env.py:58-71`), initialises `START_ARM_POSE` and `BOX_POSE` (`sim_env.py:180-183`), and adds the reward, camera
images and the 20 s time limit (`sim_env.py:48`).

Tags: act, aloha, bimanual, insertion, manipulation, mujoco, simulation, viperx
