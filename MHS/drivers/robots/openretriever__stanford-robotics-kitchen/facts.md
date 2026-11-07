# Facts and tags for gh.openretriever/stanford-robotics-kitchen

Every fact cites its source at commit `546fd4b108f093f776a1a7c5919547233945dc88`: `vendor_doc` (a text file of the
clone such as README.md or the scene metadata JSON) or `upstream_code` (the MJCF model or a Python source file).
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.

The package serves the card's primary model, the MJCF robot `src/retriever_src_kitchen/_scene/output/robots/panda.xml`
(`models[0]`), as a `MujocoDriver`. The model file is read from the read-only clone in place; neither the model nor
its assets are copied into the package. The card's other two robot models (`tiago.xml` and `ur5e.xml`) and the
kitchen scene files are not served: one package serves one device.

| fact | source | ref |
|---|---|---|
| The repository is an installable reconstruction of the Stanford Robotics Center kitchen for MuJoCo and Retriever, with the scene, portable robot assets, scripted simulation tasks and a five-Flow Retriever pipeline | vendor_doc | README.md:3-5 |
| The reconstruction is an estimated visual reconstruction, not a surveyed digital twin | vendor_doc | README.md:9 |
| The controllable robot is a Franka Panda; the Mobile ALOHA is visual-only staging | vendor_doc | README.md:13 |
| The scene metadata names Panda as the controlled robot | vendor_doc | src/retriever_src_kitchen/_scene/scene.json:9 |
| The scene metadata records that the scene has no hardware access | vendor_doc | src/retriever_src_kitchen/_scene/scene.json:14 |
| The Panda manifest entry names panda.xml as its MJCF file | vendor_doc | src/retriever_src_kitchen/_scene/output/robots/manifest.json:2-4 |
| panda.xml is an MJCF model named "panda" and interprets angles in radians | upstream_code | src/retriever_src_kitchen/_scene/output/robots/panda.xml:1-2 |
| panda.xml declares seven torque motor actuators for the seven arm joints: joints 1 to 5 have ctrlrange -80 to 80 and joints 6 and 7 have ctrlrange -12 to 12 | upstream_code | src/retriever_src_kitchen/_scene/output/robots/panda.xml:3-10 |
| panda.xml declares two position actuators for the gripper fingers: one ctrlrange is 0 to 0.04 and the other is -0.04 to 0 | upstream_code | src/retriever_src_kitchen/_scene/output/robots/panda.xml:11-12 |
| The seven arm joints are hinges with ranges joint1 +-2.8973, joint2 +-1.7628, joint3 +-2.8973, joint4 -3.0718 to -0.0698, joint5 +-2.8973, joint6 -0.0175 to 3.7525 and joint7 +-2.8973 | upstream_code | src/retriever_src_kitchen/_scene/output/robots/panda.xml:151-205 |
| The two gripper finger joints are slides with ranges 0 to 0.04 and -0.04 to 0 | upstream_code | src/retriever_src_kitchen/_scene/output/robots/panda.xml:232-242 |
| create_scene constructs native MuJoCo state but starts no clock, policy or server | vendor_doc | README.md:85-86 |
| The tested stack pins MuJoCo 3.3.1 and Retriever Core 0.0.4 | vendor_doc | README.md:112-113 |
| The repository documents no real-device or hardware access and no implicit simulator, viewer, socket or network startup during import | vendor_doc | README.md:104-106 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself, one interval per
actuator (`actuator_ctrlrange`; the bridge's source is `upstream_code` and its reference is the model file). The
package declares no limit of its own and no `operator_required` bound, because the model file is the system of
record for the control envelope. The runtime refuses an out-of-range element before writing `data.ctrl`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the model for the
actuator count, the control ranges and the joint dimensions, but its integration is a placeholder velocity
proportional to each control value and it resolves no mesh, contact, equality, tendon or actuator constraint. The
model sets no `<option timestep>`; the stand-in uses 2 ms, MuJoCo's library default, as a placeholder and the package
did not verify the engine default because the engine was never imported. MuJoCo was not importable where the gate
ran (no network, no pip), so no trajectory was compared with the real engine. The gaps are listed in the `fidelity`
attribute of `driver.py`.

The served model is fixed-base: it has nine hinge and slide joints and nine actuators, no free joint and no
equality constraints. The card's other robot models and the kitchen scene are other devices and are not served.

Tags: stanford, kitchen, panda, franka, mujoco, simulation, robot
