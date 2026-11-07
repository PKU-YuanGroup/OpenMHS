# Facts and tags for gh.chauncygu/safe-multi-agent-robosuite

Every fact cites its source at commit `df9ade0fa8df984bfe6853fda7604edf10440b65`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF document `robosuite/models/assets/robots/baxter/robot.xml`
(`models[0]`), as a `MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the
model nor its mesh assets, and it does not import the upstream Python package. The card's `entry_symbols` were
confirmed in the clone: `MujocoMulti` at `robosuite/multi_agent/multi_robot_panda.py:126` and the environment classes
`Door` (`robosuite/environments/manipulation/door.py:13`), `Lift` (`lift.py:16`), the second `Lift`
(`lift_without_smoothness_constraints.py:16`) and `NutAssemblySingle` (`nut_assembly.py:687`); they construct a whole
robosuite scene and need gym, numpy and robosuite, so the driver serves the bare MJCF robot model that the card's
`models` list names.

| fact | source | ref |
|---|---|---|
| Safe Multi-Agent Robosuite is an extension of Robosuite that splits the control over a robot across multiple controllers of its joints, one or more per controller | vendor_doc | README.md:10 |
| The card's first model is the MJCF document whose root element is '<mujoco model="baxter">' | upstream_code | robosuite/models/assets/robots/baxter/robot.xml:1 |
| The Baxter wrapper loads the same file through xml_path_completion("robots/baxter/robot.xml") | upstream_code | robosuite/models/robots/manipulators/baxter_robot.py:15 |
| The Baxter wrapper describes the robot as a bimanual robot designed by Rethink Robotics | upstream_code | robosuite/models/robots/manipulators/baxter_robot.py:8 |
| The Baxter wrapper reports the arm type as bimanual | upstream_code | robosuite/models/robots/manipulators/baxter_robot.py:77-78 |
| The right arm is a chain of seven hinge joints named right_s0, right_s1, right_e0, right_e1, right_w0, right_w1 and right_w2 with ranges -1.70168..1.70168, -2.147..1.047, -3.05418..3.05418, -0.05..2.618, -3.059..3.059, -1.5708..2.094 and -3.059..3.059 | upstream_code | robosuite/models/assets/robots/baxter/robot.xml:71-103 |
| The left arm is the matching chain of seven hinge joints named left_s0, left_s1, left_e0, left_e1, left_w0, left_w1 and left_w2 with the same joint ranges as the right arm | upstream_code | robosuite/models/assets/robots/baxter/robot.xml:123-155 |
| The actuator section declares fourteen motor actuators, one per joint; the control ranges are shoulder pan -50 to 50, shoulder lift -100 to 100, upper elbow -50 to 50, lower elbow -50 to 50, forearm roll -15 to 15, wrist angle -15 to 15 and wrist rotate -15 to 15, repeated for the right and left arms | upstream_code | robosuite/models/assets/robots/baxter/robot.xml:176-190 |
| The head pan joint is inside an XML comment, so the served model has no head joint | upstream_code | robosuite/models/assets/robots/baxter/robot.xml:59 |
| The model declares eight contact exclusions between the shoulders, elbows, head and torso | upstream_code | robosuite/models/assets/robots/baxter/robot.xml:27-34 |
| The model declares its eleven meshes as STL files under meshes/ | upstream_code | robosuite/models/assets/robots/baxter/robot.xml:2-13 |
| The Baxter wrapper gives both arms the RethinkGripper by default; the gripper is not part of robot.xml | upstream_code | robosuite/models/robots/manipulators/baxter_robot.py:27-31 |

Limits: the package declares none of its own. The bridge derives `cap.world.step.v1`'s `action.ctrl` from the served
model: one interval per actuator, from `actuator_ctrlrange` in the model file (upstream_code, robot.xml:176-190), and
the class source of that derived limit is the model (`mhs.bridge.mujoco`). The served model has no actuator without a
`ctrlrange`; `ticks` is bounded by the catalogue class (1 to `max_ticks`, 10000 by default), not by a device bound.
The device is simulated (R0), so no limit is `operator_required` and no `site-limits.example.json` is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:baxter`, level F1. Determinism is `exact`: MuJoCo
integrates one model deterministically from the reset state and the model has no random element. The bridge reads the
time step from `model.opt.timestep`; the served model sets none (it has no option element), so the fake backend uses a
placeholder library default (fake.py, marked `# placeholder`) and publishes that stand-in value. `realtime_factor` 0,
clock `lockstep`, reset `full`. The fake implements the integration-state snapshot functions, so `snapshot_restore` is
true. The gaps say that the stand-in is not the engine (no mesh, contact, equality, inertia or actuator dynamics),
that the served robot.xml is the bare two-arm torso without the RethinkGripper that the robosuite wrapper attaches,
that the multi-controller split of the benchmark is not part of the bare model, and that no trajectory was compared
with MuJoCo or with a physical Baxter.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the world
state stays readable. No physical Baxter is modelled, and the catalogue classes `cap.world.step.v1` and
`cap.world.reset.v1` are R0.

Tags: baxter, bimanual, manipulation, mujoco, multi-agent, robosuite, robot, simulation
