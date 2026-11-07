# Facts and tags for gh.liuskywalkerjskd/mujoco_iiwa7_r800

Every fact cites its source at commit `bf300255e9b511b6ad43ab40727347033a2619dd`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF or Python file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF file `iiwa7_mjcf/iiwa7_tuned.xml` (`models[0]`), as a
`MujocoDriver`. It reads the model from the read-only clone; the package copies neither the model nor its meshes. The
clone's other two models, `iiwa7_with_gripper.xml` (arm plus Robotiq 2F-85, eight actuators) and `robotiq_2f85.xml`
(standalone gripper), are not served by this package; a site that needs them changes `model_path` and the facts.

| fact | source | ref |
|---|---|---|
| The package's model is the MJCF file iiwa7_mjcf/iiwa7_tuned.xml, whose root element is '<mujoco model="iiwa7_tuned">' | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:1 |
| The model declares angle=radian with autolimits=true, so its joint and control ranges are radians | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:23 |
| The model uses the implicitfast integrator with a timestep of 0.002 s | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:25 |
| The model header describes its tuning as a general actuator with gaintype=fixed, biastype=affine, gainprm=2000 and biasprm '0 -2000 -200' (PD kp=2000 kd=200), per-joint forcerange, armature 0.1 and seven contact excludes | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:14-20 |
| The iiwa default class gives every arm joint the axis 0 0 1, damping 0.5 and armature 0.1, and the default general actuators gaintype=fixed, biastype=affine, gainprm=2000 and biasprm '0 -2000 -200' | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:28-30 |
| The joint1 default class sets the joint range -2.96706 to 2.96706 rad and the matching ctrlrange, with a forcerange of -176 to 176 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:31-34 |
| The joint2 default class sets the joint range -2.09440 to 2.09440 rad and the matching ctrlrange, with a forcerange of -176 to 176 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:35-38 |
| The joint3_mid default class sets the joint range -2.96706 to 2.96706 rad and the matching ctrlrange, with a forcerange of -110 to 110 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:39-42 |
| The joint4_mid default class sets the joint range -2.09440 to 2.09440 rad and ref 1.5708, with the matching ctrlrange and a forcerange of -110 to 110 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:43-46 |
| The joint5_mid default class sets the joint range -2.96706 to 2.96706 rad and the matching ctrlrange, with a forcerange of -110 to 110 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:47-50 |
| The joint6_distal default class sets the joint range -2.09440 to 2.09440 rad and ref -1.5708, with the matching ctrlrange and a forcerange of -40 to 40 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:51-54 |
| The joint7_distal default class sets the joint range -3.05433 to 3.05433 rad and the matching ctrlrange, with a forcerange of -40 to 40 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:55-58 |
| The model has seven joints, iiwa_joint_1 to iiwa_joint_7, on the link bodies iiwa_link_1 to iiwa_link_7 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:102-153 |
| The model has seven general actuators, actuator1 to actuator7, on iiwa_joint_1 to iiwa_joint_7, each naming the matching joint default class so it takes that class's ctrlrange | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:174-182 |
| The arm's tool point is the site attachment_site at 0 0 0.05 on iiwa_link_7, 5 cm along its local +Z | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:147-153 |
| The model excludes seven non-adjacent body pairs from collision, from iiwa_link_0/iiwa_link_1 to iiwa_link_5/iiwa_link_7 | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:164-172 |
| The model has one home keyframe whose qpos and ctrl are all zeros | upstream_code | iiwa7_mjcf/iiwa7_tuned.xml:184-190 |
| iiwa7_tuned.xml is the MuJoCo (MJCF) model of the KUKA LBR iiwa 7 R800, converted from the ROS iiwa_stack URDF and tuned to mujoco_menagerie/kuka_iiwa_14 engineering conventions | vendor_doc | README.md:3-5 |
| The home keyframe matches the real robot's ready pose of J4 = -90 degrees and J6 = +90 degrees, with the other joints at 0 degrees | vendor_doc | README.md:319-322 |
| Because iiwa7.xml sets ref=+1.5708 on J4 and ref=-1.5708 on J6, qpos zero is that home pose; the physical angle is qpos - ref | vendor_doc | README.md:330-337 |
| The pose API takes a 7-vector [x, y, z, qx, qy, qz, qw] in the base frame, in metres and with the quaternion in xyzw order | vendor_doc | README.md:131-141 |
| The controller drives only the seven arm joints: ARM_NV = 7 and ARM_NU = 7, so any gripper channel beyond them stays independent | upstream_code | iiwa7_controller/controller.py:47-50 |
| The tuned model's forcerange is -176 to 176 N m for J1/J2, -110 to 110 N m for J3 to J5 and -40 to 40 N m for J6/J7, from the iiwa7 datasheet | vendor_doc | TUNING_REPORT.md:21 |
| The clone also ships iiwa7_with_gripper.xml (the arm plus a Robotiq 2F-85 on the flange) and robotiq_2f85.xml (the standalone gripper) | vendor_doc | README.md:188-197 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`). `iiwa7_tuned.xml:32`, `:36`, `:40`, `:44`, `:48`, `:52` and `:56` set the seven joint
ranges, and `iiwa7_tuned.xml:33`, `:37`, `:41`, `:45`, `:49`, `:53` and `:57` set the matching `ctrlrange` for the
default classes that actuator1 to actuator7 name. The class source is `upstream_code` and the reference is the model
file, so no driver-declared or `operator_required` bound is needed.

Safe state: the simulation stops advancing on an e-stop; no step or reset is accepted until `mhs.safety.reset`
clears the latch, and the integration state stays readable. There is no hardware e-stop because the device is a
simulated R0 world with no hardware backend.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file for
the joint count, the actuator count and the control ranges, but its integration is a placeholder first-order motion,
and it resolves no mesh, contact, equality or tendon constraint, no inertia, damping, armature, PD gain or forcerange.
MuJoCo was not importable where the gate ran, so no trajectory was compared with the real engine. The gaps are listed
in the `fidelity` attribute of `driver.py`. `cap.world.reset.v1` restores the model defaults (`mj_resetData`); the
model's home keyframe is all zeros, so the reset pose is the home pose under the model's J4/J6 `ref` convention.

Tags: arm, iiwa7, kuka, manipulator, mujoco, robot, simulation
