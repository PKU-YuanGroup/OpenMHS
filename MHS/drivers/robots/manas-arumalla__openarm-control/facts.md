# Facts and tags for gh.manas-arumalla/openarm-control

Every fact cites its source at commit `14ea59faad6706b9add5d7f8d386e43239a6360f`: `vendor_doc` (a text file of the
clone: README.md, docs/*.md or another documentation text) or `upstream_code` (an MJCF, Python or packaging file of
the clone).  The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a control, motion-planning, bimanual-coordination and reinforcement-learning platform for the Enactic OpenArm v2 (7-DOF x 2 plus grippers) in MuJoCo | vendor_doc | README.md:11-13 |
| The package maps the scene name 'unscrew' to v2/openarm_mujoco_v2/unscrew_scene.xml | upstream_code | openarm_control/config.py:38-71 |
| The unscrew scene is the MJCF model openarm_v20_unscrew with a 0.002 s integration timestep | upstream_code | v2/openarm_mujoco_v2/unscrew_scene.xml:14-18 |
| The unscrew scene declares openarm_pedestal.xml as an attachable model asset and attaches model arm_pedestal in its worldbody | upstream_code | v2/openarm_mujoco_v2/unscrew_scene.xml:33-43 |
| The pedestal model declares openarm_v20_bimanual.xml as an attachable model asset and attaches model bimanual at a frame 0.698 m above the pedestal origin | upstream_code | v2/openarm_mujoco_v2/openarm_pedestal.xml:44-54 |
| The bimanual model is the MJCF model openarm_v20_visual with 16 position actuators, eight per arm (seven joints and one finger) | upstream_code | v2/openarm_mujoco_v2/openarm_v20_bimanual.xml:349-365 |
| The left arm control ranges are joint1 -3.49066 to 1.39626 rad, joint2 -3.31613 to 0.174533 rad, joint3 -1.5708 to 1.5708 rad, joint4 0 to 2.44346 rad, joint5 -1.5708 to 1.5708 rad, joint6 -0.785398 to 0.785398 rad, joint7 -1.5708 to 1.5708 rad and the finger 0 to 0.7854 | upstream_code | v2/openarm_mujoco_v2/openarm_v20_bimanual.xml:350-357 |
| The right arm control ranges are joint1 -1.39626 to 3.49066 rad, joint2 -0.174533 to 3.31613 rad, joint3 -1.5708 to 1.5708 rad, joint4 0 to 2.44346 rad, joint5 -1.5708 to 1.5708 rad, joint6 -0.785398 to 0.785398 rad, joint7 -1.5708 to 1.5708 rad and the finger -0.7854 to 0 | upstream_code | v2/openarm_mujoco_v2/openarm_v20_bimanual.xml:358-365 |
| The scene adds the cap_lift_drive position actuator on the cap_lift joint with control range 0 to 0.12 | upstream_code | v2/openarm_mujoco_v2/unscrew_scene.xml:82 |
| The cap has a hinge turn joint and a slide lift joint with a 0 to 0.12 range | upstream_code | v2/openarm_mujoco_v2/unscrew_scene.xml:60-61 |
| The ready keyframe states nq = 20 as left arm coordinates 0-8, right arm coordinates 9-17, cap_turn 18 and cap_lift 19 | upstream_code | v2/openarm_mujoco_v2/unscrew_scene.xml:85-91 |
| Each hand's two finger joints are coupled by a joint equality constraint | upstream_code | v2/openarm_mujoco_v2/openarm_v20_bimanual.xml:345-348 |
| The arm joint classes motor_DM8009, motor_DM4340, motor_DM4310 and motor_DM3507 default to hinge joints, and the finger class defaults to a limited hinge joint | upstream_code | v2/openarm_mujoco_v2/openarm_v20_bimanual.xml:22-40 |
| The package requires Python 3.10 or newer, pins mujoco==3.8.1 and depends on numpy | upstream_code | pyproject.toml:10-23 |
| The unscrew demo loads the scene with mujoco.MjModel.from_xml_path, creates MjData and resets to the ready keyframe | upstream_code | openarm_control/demos/demo_unscrew.py:27-31 |
| The implementation log describes the single-arm unscrew scene as a clamped bottle whose threaded cap has a turn hinge, a lift slide and a lift actuator | vendor_doc | docs/IMPLEMENTATION_LOG.md:1285-1287 |
| The OpenArm v2 MuJoCo model under v2/openarm_mujoco_v2 (meshes and MJCF) is attributed to Enactic, Inc. under Apache-2.0 | vendor_doc | docs/MODELS.md:61-62 |

## Limits

The driver declares no explicit `Limit`; the served model is the source of the one bound the bridge publishes.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [17 numbers]}}`.  Each `ctrl` element is bounded by the matching
actuator's `ctrlrange` in the flattened scene: the left arm ranges at lines 350-357, the right arm ranges at lines
358-365 of `v2/openarm_mujoco_v2/openarm_v20_bimanual.xml`, and the cap lift range `0 0.12` at line 82 of
`v2/openarm_mujoco_v2/unscrew_scene.xml`.  The bridge derives these per-actuator bounds from the loaded model and
publishes them with the model reference; no number is written into this package.  `ticks` is bounded by the family at
1 to 10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:openarm_v20_unscrew`, level F1 (a rigid-body MJCF scene, no rendering
or sensor publication), determinism `exact` with seed control `none`, timestep 2 ms (`unscrew_scene.xml:18`),
`realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore supported through the bridge's integration
state.  The gaps say that the fake backend is not the engine, that it inserts the attached-model actuators before the
scene's own actuator and that the engine's ctrl order was not available to confirm, that the meshes are not loaded,
that reset does not apply the ready keyframe, that nothing paces wall-clock time, that no rendering or camera stream
is served, that the upstream task logic is not served, that the stand-in snapshot is a reduced integration state, and
that no physical arm is modelled.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable.  There is no hardware e-stop, no physical
stop path and no claim of one.  The package is model-authored and unreviewed; no hardware was attached and no
hardware backend was run.

Tags: mujoco, openarm, unscrew, bottle-opening, robot-arm, simulation
