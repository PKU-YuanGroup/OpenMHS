# Facts and tags for gh.vikashplus/unitree_sim

Every fact cites its source at commit `21b5524e7c5586565de5e789e94bb69efd36db69`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (an MJCF/XML file path below the clone root, with a line or
line range). The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

The package serves the card's main model, the MJCF scene `a1.xml` (`models[0]`), as a `MujocoDriver`. It reads the
model file from the read-only clone; the package copies neither the model nor its meshes. The repository also has
`aliengo.xml` and `laikago.xml`; one package per repository serves one model, so those are named here and not served
(the driver's fidelity `gaps` say so).

| fact | source | ref |
|---|---|---|
| The repository describes itself as 'MuJoCo models for Unitree Robots' | vendor_doc | README.md:2 |
| The card's main model is the MJCF scene a1.xml, whose root element is '<mujoco model="unitree_a1">' | upstream_code | a1.xml:10 |
| The model uses radian angles (<compiler angle="radian"/>) and sets size njmax 500 and nconmax 100 | upstream_code | a1.xml:11-12 |
| The model header states that it is under the Apache License, Version 2.0 | upstream_code | a1.xml:7 |
| The torso body a1_torso has a free joint (<freejoint/>), so the model has a floating base | upstream_code | a1.xml:36-42 |
| The robot has 12 hinge joints, three per leg (hip, thigh and calf): FR_hip, FR_thigh, FR_calf, then the same for FL, RR and RL | upstream_code | a1.xml:43-123 |
| The joint ranges are hip -0.802851 to 0.802851, thigh -1.0472 to 4.18879 and calf -2.69653 to -0.916298 | upstream_code | a1.xml:45-55 |
| The model has 12 position actuators, one per hinge joint, with kp 60 on hip and thigh and kp 93.3 on calf | upstream_code | a1.xml:126-139 |
| Every actuator sets ctrlrange to its joint range | upstream_code | a1.xml:127-138 |
| The unitree default class sets ctrllimited true for position actuators | upstream_code | a1.xml:26 |
| a1.xml includes basic_scene.xml | upstream_code | a1.xml:33 |
| basic_scene.xml has a <mujocoinclude> root | upstream_code | basic_scene.xml:1 |
| basic_scene.xml defines a ground plane geom of size 5 5 10 | upstream_code | basic_scene.xml:20 |
| The five mesh assets are STL files under meshes/a1 | upstream_code | a1.xml:14-18 |
| The repository also contains aliengo.xml, whose root is '<mujoco model="unitree_aliengo">' | upstream_code | aliengo.xml:9 |
| The repository also contains laikago.xml, whose root is '<mujoco model="unitree_laikago">' | upstream_code | laikago.xml:9 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`; the limit source is `upstream_code` and the derived reference is the model name plus
`actuator_ctrlrange`, as the simulator family is allowed to do). The values are the joint ranges in radians on
`a1.xml:127-138`. No `operator_required` bound is needed and no bound is declared in `driver.py`.

Fidelity: the model has no `<option timestep>`, so the stand-in uses MuJoCo's library default 2 ms as a placeholder
for `timestep_ms`; a real MuJoCo load would use that same default. The fake backend (fake.py) is a stand-in for the
MuJoCo library, not MuJoCo: it reads the model file for the actuator count and control ranges, the joint dimensions
(19 qpos and 18 qvel: 7/6 for the free base plus 1/1 per hinge) and the free-joint start pose, but its integration is
a placeholder first-order motion, it does not integrate the free base, and it resolves no mesh, contact, actuator,
equality or tendon constraint. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was
compared with the real engine. The gaps are listed in the `fidelity` attribute of `driver.py`; a site that needs
MuJoCo's physics runs the driver with a backend that imports MuJoCo.

Tags: unitree, a1, quadruped, mujoco, simulation, robot
