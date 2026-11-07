# Facts and tags for gh.kscalelabs/mujoco_playground

Every fact cites its source at commit `9762ac537cf8d03197ce8bfeaf116f56687f3c19`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF, Python or packaging file of the clone). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README names the project the K-Scale Mujoco Playground Library | vendor_doc | README.md:14 |
| The setup script names the distribution kscale-mujoco-playground and requires Python 3.12 or newer | upstream_code | setup.py:27-36 |
| The K-Bot flat terrain scene is the MJCF model 'kbot feetonly flat terrain scene' and includes kbot.xml from the same directory | upstream_code | playground/kbot/xmls/scene_mjx_feetonly_flat_terrain.xml:1-2 |
| The included robot model is named k-bot_sim | upstream_code | playground/kbot/xmls/kbot.xml:1 |
| The model compiles joint and actuator angles in radians | upstream_code | playground/kbot/xmls/kbot.xml:30 |
| The robot default class gives every position actuator inheritrange 1, so its control range is the matching joint range | upstream_code | playground/kbot/xmls/kbot.xml:3-4 |
| The motor_00, motor_02, motor_03 and motor_04 default classes set joint armatures of 0.0005, 0.002, 0.005 and 0.007, friction losses of 0.1, 0.1, 0.3 and 0.1, actuator force ranges of -14 to 14, -17 to 17, -60 to 60 and -120 to 120, and position gains of 20, 20, 50 and 100 | upstream_code | playground/kbot/xmls/kbot.xml:5-20 |
| The floating base body is placed at z 1.08006263 and carries the free joint named floating_base | upstream_code | playground/kbot/xmls/kbot.xml:64-65 |
| The left arm hinge ranges are: shoulder pitch 0 to 3.141593 rad, shoulder roll -3.630285 to 0.479966 rad, shoulder yaw -1.570796 to 1.570796 rad, elbow -2.530727 to 0 rad and wrist -3.141593 to 3.141593 rad | upstream_code | playground/kbot/xmls/kbot.xml:68-84 |
| The right arm hinge ranges are: shoulder pitch -3.141593 to 0 rad, shoulder roll -0.479966 to 3.630285 rad, shoulder yaw -1.570796 to 1.570796 rad, elbow 0 to 2.530727 rad and wrist -3.141593 to 3.141593 rad | upstream_code | playground/kbot/xmls/kbot.xml:93-109 |
| The left leg hinge ranges are: hip pitch -1.570796 to 1.570796 rad, hip roll -3.185226 to 0.349066 rad, hip yaw -1.570796 to 1.570796 rad, knee 0 to 2.094395 rad and ankle -0.698132 to 0.698132 rad | upstream_code | playground/kbot/xmls/kbot.xml:118-134 |
| The right leg hinge ranges are: hip pitch -1.570796 to 1.570796 rad, hip roll -0.349066 to 3.185226 rad, hip yaw -1.570796 to 1.570796 rad, knee -2.094395 to 0 rad and ankle -0.698132 to 0.698132 rad | upstream_code | playground/kbot/xmls/kbot.xml:144-160 |
| The actuator section declares 20 position actuators, one for each hinge joint, in the motor_02, motor_03 and motor_04 default classes | upstream_code | playground/kbot/xmls/kbot.xml:175-196 |
| The scene's floor is a plane with friction 0.6 and condim 3 | upstream_code | playground/kbot/xmls/scene_mjx_feetonly_flat_terrain.xml:22-25 |
| The scene's keyframe block is commented out, so the model has no home or standing keyframe | upstream_code | playground/kbot/xmls/scene_mjx_feetonly_flat_terrain.xml:27-30 |
| The model declares an accelerometer, a gyro, a magnetometer and frame sensors at the imu site | upstream_code | playground/kbot/xmls/kbot.xml:198-206 |

## Limits

The driver declares no explicit `Limit`; the served model is the source of the one bound the bridge publishes.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [20 numbers]}}`. Each `ctrl` element is bounded by the matching
`position` actuator's control range. The `robot` default class sets `inheritrange` 1 (`kbot.xml:4`), so each control
range equals the range of the joint the actuator drives: the five left arm ranges at lines 68-84, the five right arm
ranges at lines 93-109, the five left leg ranges at lines 118-134 and the five right leg ranges at lines 144-160.
The bridge derives these per-actuator bounds from the loaded model and publishes them with the model reference; no
number is written into this package. `ticks` is bounded by the family at 1 to 10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:kbot_feetonly_flat_terrain`, level F1 (rigid-body MJCF, no
rendering or sensor publication), determinism `exact` with seed control `none`, timestep 2 ms (the MuJoCo engine
default, because `kbot.xml` declares no `<option timestep>`), `realtime_factor` 0, clock `lockstep`, reset `full`,
snapshot and restore supported through the bridge's integration state. The gaps say that the fake backend is not
the engine, that the 2 ms step is the engine default rather than a value in the model file, that reset does not
apply a keyframe, that nothing paces wall-clock time, that no rendering or sensor stream is served, that the meshes
are not loaded by the stand-in, and that no physical robot is modelled.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable. There is no hardware e-stop, no physical
stop path and no claim of one.

Tags: mujoco, kbot, humanoid, feet-only, flat-terrain, simulation
