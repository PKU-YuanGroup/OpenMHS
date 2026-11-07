OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of an Anthropic research preview.

# Facts and tags for gh.blackcoffeerobotics/bcr_bot

Every fact cites the pinned clone at commit `58b9220f35870bf8543db12f8b457942fa07cac3`.
`upstream_code` refs name `path/in/clone:LINE`; `vendor_doc` refs name README text.
The same facts are declared in `driver.py`; the reference files are generated from
the driver, not from this page.

## Shape and scope

The repository is a ROS 2 ament package that ships Gazebo, MuJoCo and Isaac Sim
assets for a differential-drive robot. Its MuJoCo path is the external
`mujoco_ros2_control` node, configured by `urdf/mujoco_ros2_control.xacro` to load
`mjcf/small_warehouse.xml`. The clone contains the xacro, launch and controller
configuration but no implementation of `mujoco_ros2_control`; that runtime is
installed separately as a ROS 2 package.

DEVIATION FROM THE CARD: the card names `RosDriver`, but the ROS command and
sensor endpoints in the clone are configurations of that external simulator
runtime, not nodes implemented in the clone. The card's own candidate classes are
`cap.world.step.v1`, `cap.world.reset.v1` and `cap.world.seed.v1`, and its mock
strategy prefers the upstream simulator. This package therefore serves the
shipped MJCF scene through `MujocoDriver`. The production path is the real MuJoCo
engine loading the same file; the package has no Python native class and does not
import or start ROS.

The model is read from the read-only clone in place. It is not copied into the
package and is not modified. Only the configured `small_warehouse.xml` scene is
served; `empty_world.xml` is a second scene, the other Gazebo/Isaac assets and the
ROS 2 control graph are outside this package.

## Facts

| fact | source | ref |
|---|---|---|
| The repository contains Gazebo, MuJoCo and Isaac Sim simulations for a differential-drive robot equipped with an IMU, a depth camera, a stereo camera and a 2D LiDAR. | vendor_doc | README.md:7 |
| The MuJoCo launch starts the robot in the MuJoCo warehouse and enables wheel control, odometry, IMU, 2D LiDAR, the depth camera and stereo cameras. | vendor_doc | README.md:112-118 |
| The MuJoCo ROS 2 control xacro declares the MujocoSystem hardware plugin `mujoco_ros2_control/MujocoSystemInterface` and sets its `mujoco_model` parameter to `$(find bcr_bot)/mjcf/small_warehouse.xml`. | upstream_code | urdf/mujoco_ros2_control.xacro:4-7 |
| The configured scene is `mjcf/small_warehouse.xml`, an MJCF model named `bcr_bot_small_warehouse` that includes `bcr_bot.xml`. | upstream_code | mjcf/small_warehouse.xml:2-3 |
| The included `bcr_bot.xml` model compiles angles in radians, points `meshdir` and `texturedir` at `../meshes`, and sets option timestep 0.002 s with gravity `0 0 -9.81`. | upstream_code | mjcf/bcr_bot.xml:2-5 |
| The robot model starts with a `base_footprint` body carrying a `freejoint` named `base_footprint_joint`. | upstream_code | mjcf/bcr_bot.xml:26-29 |
| The `middle_left_wheel` and `middle_right_wheel` bodies each carry a hinge joint on axis `0 1 0` and a cylinder collision geom of size `0.1 0.025`. | upstream_code | mjcf/bcr_bot.xml:74-88 |
| The actuator block has two `velocity` actuators, one for each middle wheel joint, with `kv=100` and a `forcerange` of `-20000` to `20000`; neither actuator element declares a `ctrlrange`. | upstream_code | mjcf/bcr_bot.xml:148-153 |
| The model declares a `framequat` sensor, a gyro and an accelerometer at `imu_site` and a rangefinder at `two_d_lidar_ray`. | upstream_code | mjcf/bcr_bot.xml:155-160 |
| The MuJoCo launch starts the `mujoco_ros2_control` package's `ros2_control_node` with `config/mujoco_controllers.yaml` as its parameter file. | upstream_code | launch/mujoco.launch.py:33-54 |
| The MuJoCo launch starts the `twist_stamper` package's `twist_stamper` as `bcr_bot_twist_stamper` with `cmd_vel_in` remapped to `/bcr_bot/cmd_vel` and `cmd_vel_out` to `/bcr_bot/cmd_vel_stamped`. | upstream_code | launch/mujoco.launch.py:70-79 |
| The `diff_drive_controller` configuration names the two middle wheel joints and sets `wheel_separation` 0.64, `wheel_radius` 0.11, `publish_rate` 30.0 and `cmd_vel_timeout` 0.5. | upstream_code | config/mujoco_controllers.yaml:19-35 |
| `CMakeLists.txt` installs the `launch`, `meshes`, `models`, `urdf`, `worlds`, `rviz`, `config` and `mjcf` directories into the package share. | upstream_code | CMakeLists.txt:6-7 |
| The `empty_world.xml` scene declares the model `bcr_bot_empty_world` and includes `bcr_bot.xml`. | upstream_code | mjcf/empty_world.xml:2-3 |

## Contract

`cap.world.step.v1` takes `{ticks, action: {ctrl: [<nu numbers>]}}`. The bridge
checks each `ctrl` element against the model's `actuator_ctrlrange` before writing
`data.ctrl`, then runs `mj_step` `ticks` times. The two actuator elements declare
no `ctrlrange`, so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none. `cap.world.reset.v1` restores the model defaults with
`mj_resetData` + `mj_forward`.

The bridge publishes the world state `{time_ms, qpos, qvel, ctrl, tick,
timestep_ms, seed}`. The model's free joint gives `qpos` nine entries and `qvel`
eight entries; the two velocity actuators give `ctrl` two entries. The option
timestep 0.002 s is read from the model.

`cap.world.seed.v1` is not served: the `MujocoBridge` exposes only
`cap.world.step.v1` and `cap.world.reset.v1`. The reset accepts the class's seed
field but MuJoCo's `mj_resetData` does not use a seed.

## Fidelity

The fake backend is a package-local stand-in for the `mujoco` module, not the
MuJoCo engine. It parses the same MJCF and its includes for the model shape,
actuator names and option timestep, then advances a placeholder state. It loads
no mesh, texture, inertia or contact model and resolves no friction, tendon,
equality or force constraint. Its snapshot uses the bridge's basic profile
(time, `qpos`, `qvel`, `act`, `ctrl`) and does not preserve warm-start or derived
quantities. These differences are listed in the driver's `fidelity_by_backend`
fake gaps and in `RESULT.json`.

The real `sim` backend is the official `mujoco` module loading the same file; it
was not run here. No trajectory was compared with the engine and no physical
robot is modelled. The deployed fake is F0; the real engine path is described as
F1 with the model's timestep.

## Safety

The served device is simulated at R0: the only capabilities are `world.step` and
`world.reset`, whose effects are confined to simulated state (MHS-004 SAFE-006).
No mobile-base motion, actuator torque, camera, LiDAR, IMU, physical stop or
hardware command is exposed. The runtime's software e-stop latch blocks further
step and reset calls; it is not a hardware emergency stop and makes no physical
safety claim. The model's free base, contact and actuator force limits are not
validated here.

## Tags

`mujoco`, `mjcf`, `simulation`, `differential-drive`, `mobile-base`, `ros2`
