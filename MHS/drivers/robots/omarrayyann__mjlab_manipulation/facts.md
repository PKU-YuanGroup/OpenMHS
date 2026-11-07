# Facts and tags for gh.omarrayyann/mjlab_manipulation

Every fact cites its source at commit `7564cd633f4e13bb20a11b0c9f2ff187231cef8a`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's primary model, the Droid arm MJCF
`src/mjlab_manipulation/robots/droid/xmls/droid.xml` (`models[0]`), as a `MujocoDriver`. It reads the model file from
the read-only clone; neither the model nor its assets are copied into the package.

| fact | source | ref |
|---|---|---|
| The repository is a collection of manipulation tasks built with mjlab | vendor_doc | README.md:3 |
| The task table lists a Reach task that moves the gripper to a target and a Lift task that lifts a cube (state-based) | vendor_doc | README.md:9-10 |
| The task table also lists a vision-based Lift-RGB task and a Lift-Any-RGB task over 12 objaverse objects | vendor_doc | README.md:17-18 |
| The robot placeholder {Robot} is one of Droid, xArm, Kuka, Gen3 or UR5e | vendor_doc | README.md:26 |
| Each robot is a bare-arm MJCF under robots/<name>/xmls/; no gripper is part of it because a gripper is attached at task time | vendor_doc | README.md:49 |
| Each robot's constants file returns a RobotCfg with the home pose and the tool-attach offset | vendor_doc | README.md:50 |
| The robot MJCF models are sourced from MuJoCo Menagerie | vendor_doc | README.md:55 |
| The project depends on mjlab | upstream_code | pyproject.toml:7-9 |
| The package registers the mjlab.tasks entry point named mjlab_manipulation | upstream_code | pyproject.toml:51-52 |
| The MJCF model is named franka_droid | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:1 |
| The model compiles its angles in radians | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:2 |
| The model uses the implicitfast integrator | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:4 |
| The arm default class gives its joints armature 0.1 and damping 1 and gives its position actuators inheritrange 1 | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:13-15 |
| joint_1 has the range -2.7437 to 2.7437 rad | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:96 |
| joint_2 has the range -1.7837 to 1.7837 rad | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:102 |
| joint_3 has the range -2.9007 to 2.9007 rad | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:108 |
| joint_4 has the range -3.0421 to -0.1518 rad | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:115 |
| joint_5 has the range -2.8065 to 2.8065 rad | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:122 |
| joint_6 has the range 0.5445 to 4.5169 rad | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:130 |
| joint_7 has the range -3.0159 to 3.0159 rad | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:143 |
| The model has seven position actuators named joint_1 to joint_7, with kp 4500 and kv 450 for joint_1 and joint_2, kp 3500 and kv 350 for joint_3 and joint_4, and kp 2000 and kv 200 for joint_5 to joint_7 | upstream_code | src/mjlab_manipulation/robots/droid/xmls/droid.xml:160-167 |
| Droid's ARM_ACTUATORS covers joint_1 to joint_7 | upstream_code | src/mjlab_manipulation/robots/droid/droid_constants.py:19-21 |
| Droid's ARM_HOME places the base at (0, 0, 0.5) and sets joint_2, joint_4 and joint_6 to -1/5*pi, -4/5*pi and 3/5*pi radians | upstream_code | src/mjlab_manipulation/robots/droid/droid_constants.py:23-33 |
| Droid's robot config attaches the tool to link_7 at position (0, 0, 0.107) with quaternion (0.7071068, 0, 0, 0.7071068) | upstream_code | src/mjlab_manipulation/robots/droid/droid_constants.py:54-56 |
| The attached gripper actuator targets the split tendon with a position command | upstream_code | src/mjlab_manipulation/robots/tools.py:12-16 |
| The gripper is attached at the robot's tool-attach frame with the gripper/ prefix | upstream_code | src/mjlab_manipulation/robots/tools.py:39-51 |

Limits: the package declares none. The bridge derives the `cap.world.step.v1` input `action.ctrl` from the model
itself, one interval per actuator (`actuator_ctrlrange`; the bridge's source is `upstream_code` and its reference is
the model file). The Droid model gives every position actuator `inheritrange="1"` in the `arm` default class, so
each control interval follows the target joint range; the runtime refuses an out-of-range element before writing
`data.ctrl`. The model file is the system of record for the control envelope, so no package `Limit` is copied from
it.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the MJCF for the
joint dimensions, the actuator control ranges and the option time step, but its integration is a placeholder motion
of each actuated joint and it resolves no mesh, contact, equality, tendon or actuator constraint. MuJoCo was not
importable where the gate ran (no network, no pip), so no trajectory was compared with the real engine. The gaps are
listed in the `fidelity` attribute of `driver.py`.

The card's other models (`gen3.xml`, `kuka.xml`, `ur5e.xml` and `xarm/hand.xml`, plus `xarm/xarm.xml` and the Robotiq
2f85 gripper) are other robot devices and are not served: one package serves one device, and the driver and fake use
`models[0]`.

Tags: mujoco, simulation, manipulation, robot-arm, droid, franka, mjlab, world-sim
