# Facts, interface and coverage for gh.jeongeun980906/lerobot-mujoco-tutorial

Every fact cites its source at commit `931f26f267386a83669bc8b937404824dfa21021`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE` or `path/in/clone:START-END`).  The reference file is
generated from `driver.py`, not from this page.

## Served model

The card's `models[0]` is `asset/robotis_omy/scene.xml`, an MJCF scene that includes `asset/robotis_omy/omy.xml`.
The package serves that scene directly through `MujocoDriver`; the card's `models[1]` (`omy.xml`) is the included robot
model and is not served separately.  The tutorial's example scenes (`asset/example_scene_y.xml`,
`asset/example_scene_y2.xml`) are not served, and they reference `asset/objaverse/plate_11/model_new.xml`, whose
directory is absent until the README's unzip step is run.  The clone is read in place and is never modified.

## Facts

| fact | source | ref |
|---|---|---|
| The README title is 'LeRobot Tutorial with MuJoCo' and it describes minimal examples for collecting demonstration data and training vision-language-action models on custom datasets. | vendor_doc | README.md:1-2 |
| The README tells the user to install the requirements with mujoco version 3.1.6. | vendor_doc | README.md:22-26 |
| The README tells the user to unzip asset/objaverse/plate_11.zip before use. | vendor_doc | README.md:28-32 |
| The served scene is the MJCF model 'open_manipulator_y scene' and it includes omy.xml. | upstream_code | asset/robotis_omy/scene.xml:1-2 |
| The robot model compiles angles in radians with autolimits enabled and sets the implicitfast integrator. | upstream_code | asset/robotis_omy/omy.xml:2-4 |
| Default class Y declares joint range -6.28319 to 6.28319, armature 0.1 and damping 100.0. | upstream_code | asset/robotis_omy/omy.xml:8-10 |
| Default class Y's position actuator has kp 5000, forcerange -2000 to 2000 and ctrlrange -6.28319 to 6.28319. | upstream_code | asset/robotis_omy/omy.xml:10 |
| The arm is a six-joint chain joint1 through joint6, all of default class Y. | upstream_code | asset/robotis_omy/omy.xml:38-58 |
| The gripper has four joints: rh_r1 and rh_l1 have range 0 to 1.1 and rh_r2 and rh_l2 have range 0 to 1, all of default class gripper. | upstream_code | asset/robotis_omy/omy.xml:74-88 |
| Default class gripper's position actuator has kp 1000 and forcerange -100 to 100 but no ctrlrange. | upstream_code | asset/robotis_omy/omy.xml:12-14 |
| The model has ten position actuators: six arm actuators of class Y (actuator_joint1 through actuator_joint6) and four gripper actuators that declare ctrlrange 0 to 1.1, 0 to 1, 0 to 1.1 and 0 to 1. | upstream_code | asset/robotis_omy/omy.xml:106-117 |
| The robot model declares a camera named egocentric. | upstream_code | asset/robotis_omy/omy.xml:67 |
| The served scene's worldbody contains a floor plane and a directional light. | upstream_code | asset/robotis_omy/scene.xml:19-21 |
| The card's entry symbol SimpleEnv is a concrete class in mujoco_env/y_env.py that constructs MuJoCoParserClass from the xml_path argument. | upstream_code | mujoco_env/y_env.py:13-27 |
| SimpleEnv.step for joint_angle takes action[:-1] as the six joint targets, repeats action[-1] four times for the gripper command and scales elements 1 and 3 by 0.8. | upstream_code | mujoco_env/y_env.py:98-137 |
| SimpleEnv.step stores self.q and returns the selected state; SimpleEnv.step_env separately calls self.env.step(self.q). | upstream_code | mujoco_env/y_env.py:139-151 |
| SimpleEnv.get_joint_state returns the six joint angles plus a binary gripper state. | upstream_code | mujoco_env/y_env.py:192-202 |
| SimpleEnv.grab_image reads the agentview, egocentric and sideview camera frames. | upstream_code | mujoco_env/y_env.py:153-168 |
| The card's second entry symbol SimpleEnv2 is a concrete class in mujoco_env/y_env2.py. | upstream_code | mujoco_env/y_env2.py:13 |
| SimpleEnv2.set_instruction chooses the red mug body_obj_mug_5 or the blue mug body_obj_mug_6 from the instruction. | upstream_code | mujoco_env/y_env2.py:110-129 |
| The tutorial's example scene includes the tabletop, mug_5 and plate_11 object models in addition to the OMY robot model. | upstream_code | asset/example_scene_y.xml:23-34 |

## Native interface

| kind | native member / element | ref |
|---|---|---|
| read | MuJoCo integration state `data.time`, `data.qpos`, `data.qvel`, `data.ctrl` through the bridge | `MHS/sdk/src/mhs/bridge/mujoco.py` (SDK, not the clone) |
| read | `data.qpos` length follows the ten hinge joints (`joint1`-`joint6`, `rh_r1`, `rh_r2`, `rh_l1`, `rh_l2`) | asset/robotis_omy/omy.xml:38-58, 74-88 |
| write | `data.ctrl` has one entry per actuator and the bridge checks it against `model.actuator_ctrlrange` before writing | asset/robotis_omy/omy.xml:106-117 |
| action | `mujoco.mj_step(model, data)` once per `ticks` | SDK bridge; the model's option is at asset/robotis_omy/omy.xml:4 |
| action | `mujoco.mj_resetData(model, data)` + `mujoco.mj_forward(model, data)` | SDK bridge; the model's defaults are at asset/robotis_omy/omy.xml:8-14 |

The card's wrappers expose a seven-element joint action (`SimpleEnv.step`, `mujoco_env/y_env.py:98-137`) that maps
`action[:-1]` to the six arm joints and repeats `action[-1]` four times for the gripper joints (with 0.8 on indices 1
and 3).  The MuJoCo family serves the model's own ten-element `action.ctrl`, one level below that wrapper: six position targets in radians and four gripper position targets.
`SimpleEnv.step` stages `self.q` and returns state; `step_env()` integrates separately (`mujoco_env/y_env.py:139-151`).
The bridge combines the control write and integration in one explicit step call, and serves only the robot and floor.  The bridge
rejects a control outside the model's effective `actuator_ctrlrange`; it never clamps.

## Units and ranges

- The arm joint positions and the six arm actuator targets are radians; default class Y bounds both the joint range
  and the actuator ctrlrange to -6.28319 to 6.28319 (`asset/robotis_omy/omy.xml:9-10`).
- The gripper joints `rh_r1` and `rh_l1` range 0 to 1.1 and the gripper actuator ctrlranges are 0 to 1.1; `rh_r2` and
  `rh_l2` range 0 to 1 and their actuator ctrlranges are 0 to 1 (`asset/robotis_omy/omy.xml:74-88, 114-117`).
- The bridge publishes the simulated time in milliseconds, the integration tick count and the applied `ctrl`; it reads
  the timestep from `model.opt.timestep`.

## Stop path

This is a simulated R0 device; it has no hardware backend and no hardware stop.  The OpenMHS endpoint latches an
e-stop in software and refuses every `cap.world.step.v1` and `cap.world.reset.v1` call while latched; the SDK's
MuJoCo bridge also checks cancellation between integration steps.  The simulation state stays readable.  A reset of
the latch only releases the endpoint; it does not start or re-arm any native motion, so no `@reset` hook is declared.
The stop retains `data.ctrl` and the position targets. Releasing the latch changes no integration state; a new
explicit step without an action reuses the stored targets. The package test checks this on the fake backend.

## Coverage gaps

- NOT COVERED: the camera frames of `SimpleEnv.grab_image` (`agentview`, `egocentric`, `sideview`).  The MuJoCo bridge
  publishes `qpos`, `qvel`, `ctrl` and time, not images; the served scene has only the wrist `egocentric` camera.
- NOT COVERED: the reward/termination logic of the tutorial (for example `SimpleEnv.check_success`); the MuJoCo bridge
  has no reward or termination channel for this model.
- NOT COVERED: the language-conditioned scene (`SimpleEnv2`) and the policy deployment notebooks.  One package serves
  one model.
- The fake backend is a stand-in for the `mujoco` library, not MuJoCo, and no real engine, simulator or hardware run is
  claimed.

Tags: `lerobot`, `mujoco`, `mjcf`, `omy`, `open-manipulator`, `simulation`, `tabletop`.
