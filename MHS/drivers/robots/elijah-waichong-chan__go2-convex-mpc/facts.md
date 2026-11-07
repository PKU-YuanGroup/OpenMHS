# Facts and tags for gh.elijah-waichong-chan/go2-convex-mpc

Every fact cites its source at commit `1c63c6a762779887ab0431fd60db681dede6cb32`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF, Python or packaging file of the clone).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository implements a convex model predictive controller for the Unitree Go2 quadruped, including contact-force optimization, centroidal linearized dynamics, Raibert-style foot planning, swing-leg path generation and MuJoCo simulation | vendor_doc | README.md:1-2 |
| The upstream MuJoCo model class resolves models/MJCF/go2/scene.xml and loads it with mujoco.MjModel.from_xml_path, then creates its data with mujoco.MjData | upstream_code | src/convex_mpc/mujoco_model.py:14-21 |
| The primary scene is the MJCF model 'go2 scene' and includes go2.xml from the same directory | upstream_code | models/MJCF/go2/scene.xml:1-2 |
| The scene adds a floor plane, two low boxes and a rising row of boxes along the x axis | upstream_code | models/MJCF/go2/scene.xml:19-31 |
| The robot model is named go2, is compiled in radians with meshdir assets and autolimits, and sets the elliptic friction cone with impratio 100 | upstream_code | models/MJCF/go2/go2.xml:1-4 |
| The quadruped root body base_link is at z=0.445 m and is attached to the world by a freejoint | upstream_code | models/MJCF/go2/go2.xml:63-68 |
| The go2 default class gives its motor elements the control range -23.7 to 23.7 | upstream_code | models/MJCF/go2/go2.xml:10 |
| The knee default class overrides the motor control range to -45.43 to 45.43 | upstream_code | models/MJCF/go2/go2.xml:22-25 |
| The joint ranges are abduction -1.0472 to 1.0472 rad, front hip -1.5708 to 3.4907 rad, back hip -0.5236 to 4.5379 rad and knee -2.7227 to -0.83776 rad | upstream_code | models/MJCF/go2/go2.xml:9-24 |
| The actuator block declares 12 motor actuators, one hip, thigh and calf per leg, named in FR, FL, RR and RL order | upstream_code | models/MJCF/go2/go2.xml:222-235 |
| The model provides a home keyframe with 19 qpos values (a floating base plus 12 joints) and 12 ctrl values | upstream_code | models/MJCF/go2/go2.xml:285-288 |
| The sensor section declares joint position, velocity and actuator force sensors for all 12 joints, plus IMU orientation, gyroscope, accelerometer, position and linear velocity at the imu site | upstream_code | models/MJCF/go2/go2.xml:237-283 |
| The demos run the simulation at SIM_HZ 1000 with SIM_DT 1/1000 s | upstream_code | examples/ex00_demo.py:83-85 |
| The demos assign SIM_DT to model.opt.timestep before the simulation loop | upstream_code | examples/ex00_demo.py:185-186 |
| The demo loop advances each physics step with mj_step1, writes the held joint torques through set_joint_torque, then calls mj_step2 | upstream_code | examples/ex00_demo.py:311-314 |
| The model wrapper looks up each leg's hip, thigh and calf actuator ids by name and writes torque[0], torque[1] and torque[2] to data.ctrl | upstream_code | src/convex_mpc/mujoco_model.py:30-39 |
| set_joint_torque assigns the 12-value torque vector in FL, FR, RL, RR leg order | upstream_code | src/convex_mpc/mujoco_model.py:41-46 |
| The second scene, scene_terrain.xml, includes go2.xml and adds two height fields and obstacle geometry; this package serves the primary scene.xml | upstream_code | models/MJCF/go2/scene_terrain.xml:1-16 |
| The package requires Python 3.10 or newer below 3.11 | upstream_code | pyproject.toml:8 |
| The README recommends Linux for the project and states that other operating systems were not tested | vendor_doc | README.md:67-68 |

## Limits

The driver declares no explicit `Limit`; the served model is the source of the one bound the bridge publishes.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [12 numbers]}}`.  Each `ctrl` element is bounded by the matching
actuator's `ctrlrange` in `models/MJCF/go2/go2.xml`: the eight hip and thigh motors inherit `-23.7` to `23.7` from
the `go2` default class at line 10, and the four knee motors inherit `-45.43` to `45.43` from the `knee` default
class at lines 22-25.  The bridge derives these per-actuator bounds from the loaded model and publishes them with
the model reference; no number is written into this package as a Limit.  `ticks` is bounded by the family at 1 to
10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:go2 scene`, level F1 (rigid-body MJCF with contacts, no actuator or
sensor fidelity claim), determinism `exact` with seed control `none` (a reset restores the model defaults and the
bridge's seed does not select a different state), timestep 2 ms, `realtime_factor` 0, clock `lockstep`, reset
`full`, snapshot and restore supported through the bridge's integration state.  The gaps say that the fake backend
is not the engine, that the model states no `<option timestep>` and the 2 ms value is the fake's fallback for the
MuJoCo library default while the upstream demos set 1 ms, that the bridge's ctrl order is the model order
FR, FL, RR, RL while the upstream torque vector is FL, FR, RL, RR, that reset does not apply the home keyframe,
that no mesh, texture, contact, friction, sensor or actuator model is resolved by the stand-in, that nothing paces
wall-clock time and no rendering or sensor stream is served, that only the primary scene is served, and that no
physical Go2 is modelled or validated.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable.  There is no hardware e-stop, no physical
stop path and no claim of one.  The package never drives a real robot; the clone's controller stack is not served.

Tags: mujoco, unitree, go2, quadruped, locomotion, mpc, simulation, robot
