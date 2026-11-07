# Facts and tags for gh.muhammad-mahad/dlo-routing-workcell

Every fact cites its source at commit `2c4c322ad14edf521deceba3048e3844e0bf61d5`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`; an MJCF model file is the clone's model code). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's main model, the MJCF scene `scene.xml` (`models[0]`), as a `MujocoDriver`. It reads the
model file from the read-only clone; the package copies neither the model nor its assets.

| fact | source | ref |
|---|---|---|
| The card's main model is the MJCF scene scene.xml, whose root element is `<mujoco model="dlo_workcell_template">` | upstream_code | scene.xml:16 |
| The scene compiler reads angles in radians and resolves mesh files under meshes/ | upstream_code | scene.xml:17 |
| The scene's `<option>` element sets impratio, the implicitfast integrator and the elliptic cone, and sets no timestep | upstream_code | scene.xml:19 |
| The actuator section lists 19 actuators: paL_actuator1 through paL_actuator8, paR_actuator1 through paR_actuator8, panda_L_rail_pos, panda_R_rail_pos and slider_pos | upstream_code | scene.xml:1470-1489 |
| The Panda actuator default class sets ctrlrange -2.8973 to 2.8973 and forcerange -87 to 87 | upstream_code | scene.xml:48-52 |
| The joint2, joint4, joint6 and gripper actuators of each arm override the default control range with -1.7628 to 1.7628, -3.0718 to -0.0698, -0.0175 to 3.7525 and 0 to 255 | upstream_code | scene.xml:1472-1486 |
| Each arm has seven arm-joint position servos plus one gripper actuator, and each wrist carries a 6-axis force/torque sensor | vendor_doc | README.md:173-176 |
| The two rail actuators accept ctrlrange -0.6 to 0.6 and the obstacle slider accepts -0.4 to 0.4 | upstream_code | scene.xml:1487-1489 |
| The cable is a capsule chain named cableB_first to cableB_last: 120 segments, 3.5 m total, about 29 mm per segment | vendor_doc | README.md:379 |
| The cable's first body is held to the tension anchor by an equality connect constraint named cable_to_tension_anchor | upstream_code | scene.xml:1456 |
| The scene declares the mujoco.elasticity.wire plugin with an instance named compositecable | upstream_code | scene.xml:113-119 |
| The Chen wire DER cable plugin requires a patched MuJoCo 3.3.2 build, and stock MuJoCo wheels do not include these plugins | vendor_doc | README.md:93 |
| The wire plugin build recipe is documented for a patched MuJoCo 3.3.2 and is not part of a stock wheel | vendor_doc | README.md:93 |
| The Franka Panda model and the clip and peg STL meshes are fetched, not shipped with the repository | vendor_doc | README.md:121-122 |
| Two Franka Emika Panda arms ride linear rails, one on each long edge of the board, and each rail translates along the board's long axis by +-0.60 m | vendor_doc | README.md:153-166 |
| Force and torque sensors are registered at the left and right wrist sites ft_L_site and ft_R_site | upstream_code | scene.xml:1493-1496 |
| The model stores the home and pre_route keyframes with one qpos vector each | upstream_code | scene.xml:1499-1501 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file), so no
`operator_required` bound is needed. The model sets no timestep (`scene.xml:19`); the bridge reports the time step of
the loaded model, and the stand-in uses MuJoCo's library default as a placeholder.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file for the
actuator count, control ranges and joint dimensions, but its integration is a placeholder first-order motion and it
loads no mesh, contact, equality, tendon or plugin constraint; the cable's ball joints stay at zero. The scene needs
a patched MuJoCo 3.3.2 build with the wire plugin (`README.md:93`) and fetched assets (`README.md:121-122`), and
MuJoCo was not importable where the gate ran, so no trajectory was compared with the real engine. The gaps are listed
in the `fidelity` attribute of `driver.py`; a site with the patched engine runs the driver with a backend that imports
MuJoCo.

Tags: mujoco, simulation, deformable-linear-object, cable-routing, dual-arm, franka-panda
