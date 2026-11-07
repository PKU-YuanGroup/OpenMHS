# Facts and tags for gh.tatp-233/discoverse

Every fact cites its source at commit `d67f47c084aba0e0cf422a8725235f8b9238655a`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF, Python or packaging file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's `models[1]`, the MMK2 floor scene `models/mjcf/mmk2_floor.xml`, as a `MujocoDriver`.
The card's `models[0]`, `models/mjcf/leaphand_sensor_env.xml`, is not used: its keyframe element at line 37 has no
whitespace between the `name` and `qpos` attributes (`<key name="4"qpos=...>`), so a standard XML parser rejects the
file. The package reads the served scene and its includes from the read-only clone in place; it copies neither the
model nor its meshes. The card's five entry symbols are confirmed real-robot policy classes
(`AIRBOTMMK2Env` / `AIRBOTPlayWithCameraEnv`); they are not imported or run, and this family serves the MJCF scene.

| fact | source | ref |
|---|---|---|
| The core installation includes MuJoCo, OpenCV and NumPy | vendor_doc | README.md:64 |
| The project requires Python 3.8 or newer | upstream_code | pyproject.toml:10 |
| The package declares mujoco 3.2.0 or newer as a core dependency | upstream_code | pyproject.toml:40 |
| MMK2Cfg names the MJCF scene mjcf/mmk2_floor.xml | upstream_code | discoverse/robots_env/mmk2_base.py:8 |
| MMK2Cfg sets the timestep to 0.0025 s and the decimation to 4 | upstream_code | discoverse/robots_env/mmk2_base.py:9-10 |
| MMK2Base declares 28 qpos and 19 control values for the scene | upstream_code | discoverse/robots_env/mmk2_base.py:60-61 |
| MMK2Cfg's init_state gives the base position and orientation and zero positions for the slide, head, arm and gripper joints | upstream_code | discoverse/robots_env/mmk2_base.py:18-27 |
| SimulatorBase copies config.timestep onto model.opt.timestep after loading the model | upstream_code | discoverse/envs/simulator.py:220 |
| SimulatorBase sets delta_t to the model timestep times the decimation | upstream_code | discoverse/envs/simulator.py:88-89 |
| SimulatorBase.step runs updateControl and mj_step decimation times per call | upstream_code | discoverse/envs/simulator.py:639-642 |
| The scene is the MJCF model named mmk2 | upstream_code | models/mjcf/mmk2_floor.xml:1 |
| The scene includes mmk2_options.xml and mmk2_dependencies.xml | upstream_code | models/mjcf/mmk2_floor.xml:3-4 |
| The scene adds a plane geom named floor | upstream_code | models/mjcf/mmk2_floor.xml:22 |
| The scene attaches a body named mmk2 to the world with an unnamed free joint | upstream_code | models/mjcf/mmk2_floor.xml:23-24 |
| The scene includes mobile_chassis/mmk2/mmk2.xml inside that body | upstream_code | models/mjcf/mmk2_floor.xml:25 |
| The scene's actuator section includes mmk2_control.xml | upstream_code | models/mjcf/mmk2_floor.xml:29-30 |
| The scene's sensor section includes mmk2_sensor.xml | upstream_code | models/mjcf/mmk2_floor.xml:33-34 |
| The scene has a home keyframe with 28 qpos values | upstream_code | models/mjcf/mmk2_floor.xml:37-38 |
| The included options set the RK4 integrator and the Newton solver and state no timestep | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_options.xml:2 |
| The dependencies include the Airbot Play dependency file | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_dependencies.xml:3 |
| The slide_joint default gives the lift the joint range -0.04 to 0.87 m and the position actuator the same ctrlrange with kp 50000 | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_dependencies.xml:6-8 |
| The head yaw joint range is -0.5 to 0.5 rad and the head pitch joint range is -1.18 to 0.16 rad, with matching position ctrlranges | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_dependencies.xml:10-16 |
| The wheel default gives both wheel motors the ctrlrange and forcerange -35 to 35 | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_dependencies.xml:18-20 |
| The control fragment declares two wheel motors, the lift, head yaw and head pitch, and seven position actuators per arm | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_control.xml:3-24 |
| The two gripper position actuators have the ctrlrange 0 to 1 | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_control.xml:16-24 |
| The Airbot Play joint ctrlranges are joint1 -3.151 to 2.089, joint2 -2.963 to 0.181, joint3 -0.094 to 3.161, joint4 -3.012 to 3.012, joint5 -1.859 to 1.859 and joint6 -3.017 to 3.017 rad | upstream_code | models/mjcf/manipulator/airbot_play/airbot_play_dependencies.xml:11-33 |
| The sensor fragment publishes joint positions, tendon positions, joint velocities and tendon velocities for the controlled joints | upstream_code | models/mjcf/mobile_chassis/mmk2/mmk2_sensor.xml:3-40 |

## Limits

The driver declares no explicit `Limit`. The bridge loads the served model and derives the one bound of
`cap.world.step.v1` from it: `action.ctrl` is a 19-element array, and each element is bounded by the matching
actuator's control range. The ranges are the wheel motors -35 to 35
(`models/mjcf/mobile_chassis/mmk2/mmk2_dependencies.xml:19-20`), the lift -0.04 to 0.87 m (`:7-8`), head yaw -0.5
to 0.5 rad and head pitch -1.18 to 0.16 rad (`:11-16`), both arms joint1 -3.151 to 2.089, joint2 -2.963 to 0.181,
joint3 -0.094 to 3.161, joint4 -3.012 to 3.012, joint5 -1.859 to 1.859 and joint6 -3.017 to 3.017 rad
(`models/mjcf/manipulator/airbot_play/airbot_play_dependencies.xml:11-33`), and the two grippers 0 to 1
(`models/mjcf/mobile_chassis/mmk2/mmk2_control.xml:16,24`). The bridge publishes these per-actuator bounds with the
model reference; no bound is written into this package. `ticks` is bounded by the MuJoCo family at 1 to 10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:mmk2`, level F1 (a rigid-body MJCF, with no rendering or sensor
publication), determinism `exact` with seed control `none`, `realtime_factor` 0, clock `lockstep`, reset `full`,
snapshot and restore offered through the bridge. The model states no `<option timestep>`
(`models/mjcf/mobile_chassis/mmk2/mmk2_options.xml:2`); MMK2Cfg sets 0.0025 s and `SimulatorBase` copies it onto the
model (`discoverse/robots_env/mmk2_base.py:9`, `discoverse/envs/simulator.py:220`), but this package loads the model
file directly. The reference's `timestep_ms` (2.0) is the library default supplied by the stand-in's placeholder
fallback, not a value stated by the model.

The gaps say that the fake is not the engine, that the meshes and textures are not loaded, that the timestep is not
the upstream configuration, that reset does not apply the upstream `init_state` or the home keyframe, that the
upstream step runs four decimation substeps while a bridge tick is one `mj_step`, that the upstream clips a control
where the bridge refuses one, that no wall-clock time is paced, that the cameras and 19 joint sensors are not
published, and that no physical robot is modelled.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable. There is no hardware e-stop, no physical
stop path and no claim of one.

Tags: mujoco, discoverse, mmk2, mobile manipulator, dual arm, simulation
