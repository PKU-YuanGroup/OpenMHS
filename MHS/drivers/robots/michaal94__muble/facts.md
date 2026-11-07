# Facts and tags for gh.michaal94/muble

Every fact cites its source at commit `84f1109110aeca0063b0d062d87096cc53cc0f71`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (an MJCF or Python file of the clone). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF gripper `conda/robotiq_gripper_85.xml` (`models[0]`), as a
`MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the model nor its assets.
The card's `entry_symbols` names `environment.tabletop_env:TabletopEnv` (`environment/tabletop_env.py:20`), the
robosuite environment that uses this gripper; that class is not the model the MuJoCo family serves.

| fact | source | ref |
|---|---|---|
| The served model is the MJCF gripper model conda/robotiq_gripper_85.xml, whose root element is '<mujoco model="robotiq_gripper_85_model">' | upstream_code | conda/robotiq_gripper_85.xml:1 |
| The model declares two <position> actuators, finger_1 on joint finger_joint and finger_2 on joint right_outer_knuckle_joint, each with ctrllimited true and ctrlrange 0 0.85 | upstream_code | conda/robotiq_gripper_85.xml:32-33 |
| finger_joint is a hinge with range 0 to 0.872664626 rad | upstream_code | conda/robotiq_gripper_85.xml:53 |
| left_inner_finger_joint is a hinge with range -0.8757 to 0.8757 rad | upstream_code | conda/robotiq_gripper_85.xml:60 |
| left_inner_knuckle_joint is a hinge with range 0 to 0.8757 rad | upstream_code | conda/robotiq_gripper_85.xml:70 |
| right_outer_knuckle_joint is a hinge with range 0 to 0.872664626 rad | upstream_code | conda/robotiq_gripper_85.xml:76 |
| right_inner_finger_joint is a hinge with range -0.8757 to 0.8757 rad | upstream_code | conda/robotiq_gripper_85.xml:83 |
| right_inner_knuckle_joint is a hinge with range 0 to 0.8757 rad | upstream_code | conda/robotiq_gripper_85.xml:93 |
| Two fixed tendons couple finger_joint with the left inner joints and right_outer_knuckle_joint with the right inner joints, with coefficients 1, -3 and 1 | upstream_code | conda/robotiq_gripper_85.xml:17-28 |
| The model declares a force sensor and a torque sensor at the site ft_frame | upstream_code | conda/robotiq_gripper_85.xml:99-102 |
| The model's <asset> block declares the STL meshes of the gripper under meshes/robotiq_85_gripper/ | upstream_code | conda/robotiq_gripper_85.xml:3-12 |
| The conda gripper class loads the MJCF through robosuite's xml_path_completion('grippers/robotiq_gripper_85.xml') | upstream_code | conda/robotiq_85_gripper.py:18 |
| The conda setup copies robotiq_gripper_85.xml into robosuite's models/assets/grippers directory | upstream_code | conda/robosuite_elements.sh:6 |
| The binary gripper variant maps a continuous action to binary output: -1 means open and 1 means closed | upstream_code | conda/robotiq_85_gripper.py:59 |
| The binary gripper variant clips current_action to -1.0 to 1.0 | upstream_code | conda/robotiq_85_gripper.py:68 |
| TabletopEnv is located in environment/tabletop_env.py and inherits robosuite's SingleArmEnv | vendor_doc | docs/muble/environment.md:15 |
| The documented primitive actions of the environment include open_gripper and close_gripper | vendor_doc | docs/muble/environment.md:30-31 |
| The environment starts the gripper at current_action [-1.0] (open) | upstream_code | environment/tabletop_env.py:311 |
| The environment reports the gripper closed when current_action exceeds 0.9 | upstream_code | environment/tabletop_env.py:373 |
| MuBlE is a MuJoCo and Blender simulation environment for task planning in robotics manipulation | vendor_doc | README.md:1 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`). `conda/robotiq_gripper_85.xml:32-33` declares the two position actuators with
`ctrllimited="true"` and `ctrlrange="0 0.85"`, so the two intervals are 0 to 0.85. The class source is
`upstream_code` and the reference is the model file; the runtime enforces the interval before writing `data.ctrl`, so
no driver-declared or `operator_required` bound is needed.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file for the
joint count, the actuator count and the control ranges, but its integration is a placeholder first-order motion, and
it resolves no mesh, contact, equality or tendon constraint. MuJoCo was not importable where the gate ran, so no
trajectory was compared with the real engine. The gaps are listed in the `fidelity` attribute of `driver.py`; a site
that needs MuJoCo's physics runs the driver with a backend that imports MuJoCo.

Tags: gripper, manipulation, muble, mujoco, robotiq, simulation, two-finger
