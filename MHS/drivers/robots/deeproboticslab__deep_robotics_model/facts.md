# Facts and tags for gh.deeproboticslab/deep_robotics_model

Every fact cites its source at commit `75824b516ecc8fa3f8f7ce5d6577e1e86d6b614f`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF file or packaging file of the clone).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository holds 3D models for eight Deep Robotics robots (Lite3, M20, M20S, X30, M20_Piper, DR02 Pro, DR02 Standard and S10) in MJCF, URDF and, where available, USD formats | vendor_doc | README.md:3 |
| The bundled models are low-resolution; high-resolution models are distributed separately | vendor_doc | README.md:5 |
| The Lite3 model is an MJCF document whose root element is `<mujoco model="Lite3">` | upstream_code | Lite3/mjcf/Lite3.xml:1 |
| The model's compiler settings declare radian angles and autolimits | upstream_code | Lite3/mjcf/Lite3.xml:18-19 |
| The torso is a body at 0 0 1 m with childclass robot and a freejoint named floating_base | upstream_code | Lite3/mjcf/Lite3.xml:48-49 |
| The torso inertial has mass 5.6056 kg | upstream_code | Lite3/mjcf/Lite3.xml:51 |
| The front-left leg's HipX, HipY and Knee hinges have ranges -0.523 to 0.523, -2.67 to 0.314 and 0.524 to 2.792 rad | upstream_code | Lite3/mjcf/Lite3.xml:55-65 |
| The other three legs declare the same three joint ranges, so the model has four legs with three hinge joints each | upstream_code | Lite3/mjcf/Lite3.xml:78-146 |
| The actuator section declares 12 motor actuators, three per leg, named `<leg>_<joint>_ctrl` | upstream_code | Lite3/mjcf/Lite3.xml:153-166 |
| Every Lite3 actuator has gear 1 and ctrlrange -30 to 30 | upstream_code | Lite3/mjcf/Lite3.xml:154-165 |
| The model references STL meshes for the torso, hip, thigh and shank from its meshes directory | upstream_code | Lite3/mjcf/Lite3.xml:27-39 |
| The model excludes contacts between the torso and each hip and between each leg's adjacent bodies | upstream_code | Lite3/mjcf/Lite3.xml:168-185 |
| The model declares two track cameras, front_camera and side_camera | upstream_code | Lite3/mjcf/Lite3.xml:148-149 |
| The sensor section declares framepos, framequat, framelinvel, frameangvel, velocimeter, accelerometer and gyro sensors | upstream_code | Lite3/mjcf/Lite3.xml:187-195 |

## Limits

The driver declares no explicit `Limit`.  The served model is the source of the one bound the bridge publishes:
`cap.world.step.v1` takes `{ticks, action: {ctrl: [12 numbers]}}`, and every `ctrl` element is bounded by the
matching actuator's `ctrlrange` of `Lite3/mjcf/Lite3.xml:154-165` (`-30` to `30`, all 12 motors).  The bridge derives
these per-actuator bounds from the loaded model and publishes them with the model reference; no number is written
into this package.  `ticks` is bounded by the family at 1 to 10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:Lite3`, level F1 (rigid-body MJCF, no rendering or sensor publication),
determinism `exact` with seed control `none`, `realtime_factor` 0, clock `lockstep`, reset `full`.  The integration
step and the snapshot support are derived by the bridge from the loaded model; the Lite3 MJCF states no `<option
timestep>` (`Lite3.xml:18-19` are compiler settings), so the 2 ms value is MuJoCo's library default, published from
the stand-in.  The gaps say that the fake backend is not the engine, that the STL meshes are not loaded, that reset
does not apply a keyframe, that nothing paces wall-clock time, that no rendering or sensor stream is served, that one
package serves one model of the eight in the clone, and that no physical Lite3 is modelled.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable.  There is no hardware e-stop, no physical
stop path and no claim of one.

Tags: mujoco, lite3, deep-robotics, quadruped, robot, simulation
