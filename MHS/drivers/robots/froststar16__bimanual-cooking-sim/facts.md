# Facts and tags for gh.froststar16/bimanual-cooking-sim

Every fact cites its source at commit `6ca8f1c83378d1e3fe39a4cc9083eefe6540c5ec`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF, Python or packaging file of the clone).  The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a two-armed robot cooking simulation built in MuJoCo | vendor_doc | README.md:5-8 |
| Two 7-DOF arms are driven by the same operational-space impedance controller | vendor_doc | README.md:10-14 |
| The README lists kitchen_scene.xml as the stir stage with two arms, a pot and a spoon | vendor_doc | README.md:178 |
| The kitchen scene is the MJCF model 'bimanual_kitchen' | upstream_code | models/kitchen_scene.xml:1 |
| The scene is self-contained: it is built from primitives, needs no external meshes and carries the two 7-DOF arms and a rigidly attached spoon | upstream_code | models/kitchen_scene.xml:2-6 |
| The scene compiles with the radian angle unit and automatic limits | upstream_code | models/kitchen_scene.xml:8 |
| The scene sets the integration step to 0.002 s with the implicitfast integrator and gravity -9.81 m/s^2 | upstream_code | models/kitchen_scene.xml:9 |
| The arm default class gives every arm joint hinge damping 2.0, armature 0.1 and frictionloss 0.2 | upstream_code | models/kitchen_scene.xml:20 |
| The nested arm_actuator default class sets each motor's control range to -80 to 80 with gear 1 | upstream_code | models/kitchen_scene.xml:23-24 |
| The right arm has seven hinge joints r_j1 to r_j7 with the ranges -2.9 to 2.9, -1.8 to 1.8, -2.5 to 2.5, -2.9 to 2.9, -2.0 to 2.0, -2.9 to 2.9 and -2.0 to 2.0 rad | upstream_code | models/kitchen_scene.xml:67-85 |
| The left arm has seven hinge joints l_j1 to l_j7 with the same ranges as the right arm's | upstream_code | models/kitchen_scene.xml:114-132 |
| The actuator section declares 14 motors, r_m1 to r_m7 and l_m1 to l_m7, one for each arm joint | upstream_code | models/kitchen_scene.xml:145-159 |
| The stir task loads models/kitchen_scene.xml with mujoco.MjModel.from_xml_path and creates an MjData | upstream_code | sim/runner.py:117-118 |
| The runner advances the model with mujoco.mj_step | upstream_code | sim/runner.py:414 |
| The required Python packages are mujoco 3.0 or newer, numpy, imageio and pillow | upstream_code | requirements.txt:1-4 |

## Limits

The driver declares no explicit `Limit`; the served model is the source of the one bound the bridge publishes.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [14 numbers]}}`.  Each `ctrl` element is bounded by the matching
actuator's `ctrlrange` of `models/kitchen_scene.xml`: all fourteen motors inherit `-80` to `80` from the nested
`arm_actuator` default class at lines 23-24.  The bridge derives these per-actuator bounds from the loaded model and
publishes them with the model reference; no number is written into this package.  `ticks` is bounded by the family
at 1 to 10000.  The reset input `seed` is accepted for the class contract; `mj_resetData` does not use it.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:bimanual_kitchen`, level F1 (rigid-body MJCF, no rendering or sensor
publication), determinism `exact` with seed control `none`, timestep 2 ms (`models/kitchen_scene.xml:9`),
`realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore supported through the bridge's integration
state.  The gaps say that the fake backend is not the engine, that only the kitchen scene is served, that the scene
has no keyframe, that nothing paces wall-clock time, that no rendering or sensor stream is served, that snapshot and
restore are not exercised by the gate, and that no physical device is modelled.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable.  There is no hardware e-stop, no physical
stop path and no claim of one.

Tags: mujoco, bimanual, robot arm, cooking, manipulation, simulation
