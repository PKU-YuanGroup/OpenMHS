# Facts and tags for gh.arise-initiative/robosuite_models

Every fact cites its source at commit `2d63a6b4319bda772420daf10594ce0de5bd793d`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF document `robosuite_models/assets/robots/aloha/robot.xml`
(`models[0]`), as a `MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the
model nor its mesh assets, and it does not import the upstream Python package.

| fact | source | ref |
|---|---|---|
| The repository is a collection of robot models tailored to robosuite | vendor_doc | README.md:3 |
| The card's first model is the MJCF document whose root element is '<mujoco model="aloha">' | upstream_code | robosuite_models/assets/robots/aloha/robot.xml:1 |
| The Aloha wrapper loads the same file through robosuite_model_path_completion("robots/aloha/robot.xml") | upstream_code | robosuite_models/robots/manipulators/aloha_robot.py:20 |
| The Aloha wrapper describes the robot as bimanual with two arms and lists the arms right and left | upstream_code | robosuite_models/robots/manipulators/aloha_robot.py:11-17 |
| The right arm is a chain of six hinge joints named right/waist, right/shoulder, right/elbow, right/forearm_roll, right/wrist_angle and right/wrist_rotate | upstream_code | robosuite_models/assets/robots/aloha/robot.xml:92-116 |
| The left arm is the matching chain of six hinge joints named left/waist, left/shoulder, left/elbow, left/forearm_roll, left/wrist_angle and left/wrist_rotate | upstream_code | robosuite_models/assets/robots/aloha/robot.xml:139-164 |
| The actuator section declares twelve motor actuators, one per joint; the control ranges are waist -5 to 5, shoulder -50 to 50, elbow -50 to 50, forearm_roll -5 to 5, wrist_angle -1 to 1 and wrist_rotate -1 to 1, repeated for the left arm | upstream_code | robosuite_models/assets/robots/aloha/robot.xml:188-201 |
| The model sets no option timestep: the compiler and option elements are inside an XML comment at lines 2-4, so no <option timestep> element is active | upstream_code | robosuite_models/assets/robots/aloha/robot.xml:2-4 |
| The finger default classes, with a slide joint range and a position ctrlrange, are inside an XML comment at lines 34-43, so those finger defaults are not active in this model | upstream_code | robosuite_models/assets/robots/aloha/robot.xml:34-43 |
| The Aloha wrapper attaches the AlohaGripper to the right and left arms by default; the gripper is not part of robot.xml | upstream_code | robosuite_models/robots/manipulators/aloha_robot.py:26-35 |
| The model declares its six visual meshes as STL files with a 0.001 scale under meshes/ | upstream_code | robosuite_models/assets/robots/aloha/robot.xml:60-65 |

Limits: the package declares none of its own. The bridge derives `cap.world.step.v1`'s `action.ctrl` from the
served model: one interval per actuator, from `actuator_ctrlrange` in the model file (upstream_code), and the class
source of that derived limit is the model (`mhs.bridge.mujoco`). The served model has no actuator without a
`ctrlrange`; `ticks` is bounded by the catalogue class (1 to `max_ticks`, 10000 by default), not by a device bound.
The device is simulated (R0), so no limit is `operator_required` and no `site-limits.example.json` is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:aloha`, level F1. Determinism is `exact`: MuJoCo
integrates one model deterministically from the reset state and the model has no random element. The bridge reads the
time step from `model.opt.timestep`; the served model sets none, so the fake backend uses a placeholder library
default (fake.py) and publishes that stand-in value. `realtime_factor` 0, clock `lockstep`, reset `full`.
The fake implements the integration-state snapshot functions, so `snapshot_restore` is true. The gaps say that the
stand-in is not the engine (no mesh, contact, equality, inertia or actuator dynamics), that the served robot.xml is
the bare two-arm model without the AlohaGripper that the robosuite wrapper attaches, and that no trajectory was
compared with MuJoCo or with a physical Aloha.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the world
state stays readable.

Tags: aloha, bimanual, manipulation, mujoco, robosuite, robot, simulation
