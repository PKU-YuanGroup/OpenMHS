# Facts and tags for gh.robotis-git/robotis_mujoco_menagerie

Every fact cites its source at commit `d8344c0dbe7a00208d0301111523dde65efc174a`: `vendor_doc` (a text file of the clone such as `README.md`) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's main model, the MJCF scene `robotis_ffw/scene_ffw_bg2.xml` (`models[0]`), as a `MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the model nor its meshes. The other models of the repository (the FFW-SH5 and FFW-SG2 scenes, OMX, OMY, OP3, OpenMANIPULATOR-X and TurtleBot3) are not served: one package serves one device.

| fact | source | ref |
|---|---|---|
| The repository is a collection of models for the MuJoCo physics engine from ROBOTIS | vendor_doc | README.md:2 |
| The models are designed for use with the MuJoCo physics engine | vendor_doc | README.md:32 |
| The card's main model is the MJCF scene robotis_ffw/scene_ffw_bg2.xml, whose root element is `<mujoco model="ffw_bg2 scene">` | upstream_code | robotis_ffw/scene_ffw_bg2.xml:1 |
| The scene includes the robot model ffw_bg2.xml | upstream_code | robotis_ffw/scene_ffw_bg2.xml:2 |
| The robot model's root element is `<mujoco model="ffw_bg2">` | upstream_code | robotis_ffw/ffw_bg2.xml:1 |
| The model compiles with angles in radians and automatic limits | upstream_code | robotis_ffw/ffw_bg2.xml:2 |
| The `<option>` element sets integrator implicitfast, cone elliptic and impratio 10, and sets no timestep | upstream_code | robotis_ffw/ffw_bg2.xml:4 |
| The robot's first body is arm_base_link and its first joint is lift_joint | upstream_code | robotis_ffw/ffw_bg2.xml:142-144 |
| The model has 19 position actuators: one lift slider, two head joints, seven joints per arm and one gripper actuator per hand | upstream_code | robotis_ffw/ffw_bg2.xml:323-348 |
| Every position actuator declares `inheritrange="1"` and names the joint it drives | upstream_code | robotis_ffw/ffw_bg2.xml:325-348 |
| The lift joint is a slide joint with range -0.5 to 0.0 | upstream_code | robotis_ffw/ffw_bg2.xml:38-41 |
| The head joint ranges are -0.2317 to 0.6951 and -0.35 to 0.35 | upstream_code | robotis_ffw/ffw_bg2.xml:49-52 |
| The left arm joint ranges are -3.14 to 3.14, 0 to 3.14, -3.14 to 3.14, -2.9361 to 1.0786, -3.14 to 3.14, -1.57 to 1.57 and -1.8201 to 1.5804 | upstream_code | robotis_ffw/ffw_bg2.xml:60-109 |
| The right arm joint ranges are -3.14 to 3.14, -3.14 to 0, -3.14 to 3.14, -2.9361 to 1.0786, -3.14 to 3.14, -1.57 to 1.57 and -1.5804 to 1.8201 | upstream_code | robotis_ffw/ffw_bg2.xml:66-109 |
| The gripper joint ranges are 0 to 1.1, -1.1 to 0 and 0 to 1.1 | upstream_code | robotis_ffw/ffw_bg2.xml:117-123 |
| The gripper fingers are coupled to the first gripper joint by six equality constraints with polycoef 0 -1 0 0 0 or 0 1 0 0 0 | upstream_code | robotis_ffw/ffw_bg2.xml:375-383 |
| The model references 23 STL mesh files with scale 0.001 | upstream_code | robotis_ffw/ffw_bg2.xml:10-32 |

Limits: the package declares no limit of its own. The bridge derives the `cap.world.step.v1` input `action.ctrl` from the loaded model: one interval per actuator from `actuator_ctrlrange`. For this model each `<position>` actuator has `inheritrange="1"`, so the interval is the range of the joint it drives (the joint ranges in the table above). The source of that interval is the model file itself, not a number in this package, and the fake derives the same intervals from the same lines. No operator overlay is needed, and there is no `site-limits.example.json`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It parses the scene and its include for the joint dimensions and per-actuator control ranges, but its integration is a placeholder first-order motion, and it loads no mesh and resolves no contact, equality, tendon or actuator constraint. The model sets no `<option timestep>`; the stand-in uses a 2 ms placeholder, and MuJoCo's library default was not read or verified here. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was compared with the real engine. The gaps are listed in the `fidelity` attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a backend that imports MuJoCo.

Tags: robotis, ffw-bg2, ai-worker, dual-arm, mobile-manipulator, mujoco, simulation, robot
