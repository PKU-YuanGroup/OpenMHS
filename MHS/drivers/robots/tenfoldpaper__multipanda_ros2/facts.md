# Facts and tags for gh.tenfoldpaper/multipanda_ros2

Every fact cites its source at commit `9a30ca04b4d72e832934f19b35f540931874ec7e`:
`vendor_doc` for a text file of the clone (`README.md`, `docs/`) and `upstream_code`
for a model or launch text (`path/in/clone:LINE`). The same facts are in
`driver.py`; the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The project integrates multi-arm MuJoCo simulation designed as a plugin to `mujoco_ros_pkg`. | vendor_doc | README.md:10-11 |
| The README's tested configuration lists Ubuntu 22.04, ROS 2 Humble, Panda 4.2.2 and 4.2.1, libfranka 0.9.2 and MuJoCo 3.2.0. | vendor_doc | README.md:94 |
| The dual-arm simulator launch selects `dual_scene.xml` when the gripper is loaded and resolves it below `franka_description/mujoco/franka`. | upstream_code | franka_bringup/launch/sim/dual_franka_sim.launch.py:65-71 |
| The dual-arm simulator launch includes `launch_mujoco_ros_server.launch` and passes the selected scene to it as its `modelfile` argument. | upstream_code | franka_bringup/launch/sim/dual_franka_sim.launch.py:144-149 |
| The dual-arm documentation says `dual_scene.xml` is loaded for the dual-arm simulation. | vendor_doc | docs/chapters/franka_bringup.md:32 |
| The MuJoCo files are under `mujoco/franka`, and each robot body carries `gravcomp=1` for gravity compensation. | vendor_doc | docs/chapters/franka_description.md:50 |
| For the multi-arm case the documentation defines all arms in a single XML file, like `mj_dual`. | vendor_doc | docs/chapters/franka_description.md:54 |
| Additional objects can be included in the scene by including a separate file such as `objects.xml`. | vendor_doc | docs/chapters/franka_description.md:60 |
| The scene model is named `panda scene` and includes `mj_dual.xml` and `objects.xml`. | upstream_code | franka_description/mujoco/franka/dual_scene.xml:1-5 |
| `mj_dual` sets the option timestep to 0.002 s. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:4 |
| The scene has two arm trees rooted at `mj_left_link0` and `mj_right_link0`, at y +0.26 and -0.26. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:126-277 |
| The left arm has seven hinge joints with ranges -2.7437 to 2.7437, -1.7837 to 1.7837, -2.9007 to 2.9007, -3.0421 to -0.1518, -2.8065 to 2.8065, 0.5445 to 4.5169 and -3.0159 to 3.0159. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:145-213 |
| The right arm has the same seven hinge-joint ranges as the left arm. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:296-364 |
| The finger default class declares a slide joint with range 0 to 0.04 m. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:13-14 |
| Each hand carries two joints of class `finger`: `mj_left_finger_joint1/2` and `mj_right_finger_joint1/2`. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:241-405 |
| The finger joints are coupled by fixed tendons with coefficient 0.5 and by joint equality constraints. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:435-450 |
| `mj_dual.xml`'s actuator block has, per arm, seven torque motors with `ctrllimited` true (ctrlrange -87 87 for joints 1 to 4 and -12 12 for joints 5 to 7), seven position servos (kp 10) and seven velocity servos (kv 1) that declare no ctrlrange, and a general gripper channel of class `panda` with ctrlrange 0 255: 44 channels in all. | upstream_code | franka_description/mujoco/franka/mj_dual.xml:452-506 |
| `objects.xml` adds a free-joint box (`obj_box_01`) and a mocap sphere (`sphere_01`). | upstream_code | franka_description/mujoco/franka/objects.xml:4-9 |
| The simulation interface handles n >= 1 Panda robots and exposes the same ROS 2 interfaces as the real robot. | vendor_doc | docs/chapters/franka_hardware.md:9-12 |
| The documentation says the real-robot interface `FrankaMultiHardwareInterface` wraps libfranka to connect to the robot, its control callbacks implement no logic of their own, and all safety features and command calculation must be handled by the controller. | vendor_doc | docs/chapters/franka_hardware.md:14 |
| `.gitmodules` declares `mujoco_ros_pkgs` as a git submodule from github.com/tenfoldpaper/mujoco_ros_pkgs, branch `wip_ros_control_humble`. | upstream_code | .gitmodules:1-4 |
| The MuJoCo hardware plugin initialises every arm's torque, position and velocity actuators to off: torque flag 0 and servo gains 0. | upstream_code | franka_hardware/src/sim/franka_mj_hardware_system.cpp:141-146 |
| When a mode switch is pending, `perform_command_mode_switch` turns on only the actuator set of the arm's control mode (torque flag 1, position-servo kp 100 or velocity-servo kv 10) and zeroes the other two sets; mode `None` zeroes all three. | upstream_code | franka_hardware/src/sim/franka_mj_hardware_system.cpp:508-547 |
| `write` returns an error for a non-finite effort, position or velocity command and writes `data.ctrl` only for the actuator set of the arm's control mode, plus the gripper channel when the arm has a gripper. | upstream_code | franka_hardware/src/sim/franka_mj_hardware_system.cpp:259-299 |
| The multi-mode controller's Panda limits give the maximum joint velocity as 2.1750 rad/s for joints 1 to 4 and 2.6100 rad/s for joints 5 to 7. | upstream_code | franka_multi_mode_controller/multi_mode_controller/include/multi_mode_controller/utils/panda_limits.h:14-16 |

## Scope and deviation from the card

The task card proposes a `RosDriver`, but its device plan is a `world.sim`
resource backed by the upstream simulation, and the concrete simulation entry
is the MuJoCo scene `franka_description/mujoco/franka/dual_scene.xml` (the
dual-arm launch passes it to the MuJoCo server). The ROS packages of the pinned
parent tree are the `ros2_control` framework, the MuJoCo hardware plugin and
the gripper action layer. The MuJoCo server's world services (pause, reset and
a step action) are in the `mujoco_ros_pkgs` git submodule, which the pinned
parent commit records only as a gitlink, so no line of the pinned tree shows
them (model review correction: the author wrote that the repository exposes no
world step/reset service). This package therefore uses the SDK's
`MujocoDriver` over the card's first model, preserving `cap.world.step.v1` and
`cap.world.reset.v1`. **DEVIATION FROM THE CARD: helper `RosDriver` replaced by
`MujocoDriver` for the `world.sim` device plan.** `cap.world.seed.v1` is not
served: the MuJoCo bridge has no RNG seed control (`mj_resetData` restores the
model defaults), and this package does not invent one.

The model is read from the pinned read-only clone in place. It is never copied
into the package or imported. The model has 44 actuator channels, and both the
real `sim` backend and, since the model review, the fake report all 44 in
document order (the author's fake reported only the 16 channels with a declared
`ctrlrange`, in another order). The upstream `ros2_control` plugin turns the
unused arm actuator sets (torque, position, velocity) off by gain switching
(`franka_mj_hardware_system.cpp:141-146, 508-547`); the bare model has all
three sets active, and that controller layer is not part of this world driver.

## Limits

The driver declares no limit of its own. The MuJoCo bridge derives the
`cap.world.step.v1` envelope from the model at run time, one rule per control
channel (`action.ctrl[N]`): `franka_description/mujoco/franka/mj_dual.xml:452-506`.
Fourteen torque motors carry `-87 87` (joints 1 to 4) or `-12 12` (joints 5 to
7) per arm, and the two general gripper channels carry `0 255`, each
`upstream_code` with the ref
`franka_description/mujoco/franka/dual_scene.xml:actuator_ctrlrange`. The fourteen
position and fourteen velocity servo channels (7 to 20 and 29 to 42) declare no
`ctrlrange`, so MuJoCo leaves their control unclamped and the bridge publishes
them `operator_required`: the endpoint refuses every step that sets them
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's
`site-limits.json` bounds each one. A step without `action` keeps the controls
as they are.

`site-limits.example.json` is the operator example the gate serves: a position
servo bounded by the joint range `mj_dual.xml` gives its joint, a velocity servo
by the Panda joint velocity limit of
`franka_multi_mode_controller/multi_mode_controller/include/multi_mode_controller/utils/panda_limits.h:14-16`
(2.175 rad/s for joints 1 to 4, 2.61 rad/s for joints 5 to 7). These are
operator data, not bounds the model states; a deployment replaces them. Note
that a zero position target lies outside the example ranges of joints 4 and 6.

(Model review history: until the SDK change of 2026-11-05 the bridge published
the 28 servo channels as -/+1.7976931348623157e308; the gate's envelope probe
could not exceed those values and the package was blocked SDK_BUG.)

## Fidelity and mock path

The common fidelity describes the real-MuJoCo `sim` backend: engine
`mujoco:dual_scene`, level F1, and gaps about the unexposed controller layer,
rendering and hardware. The deployed fake overrides it: engine
`analytic:fake-mjcf-parser`, level F0, timestep 2 ms (the model's
`mj_dual.xml:4`), determinism `none`, clock `lockstep`, reset `full`, snapshot
restore through the bridge's basic profile, all 44 control channels, qpos0 on
reset, and the gaps listed in `driver.py`.

The card prefers the upstream simulator. The upstream simulator is the C++
`mujoco_ros_pkg` plugin with the `ros2_control` layer, which requires ROS 2,
MuJoCo and the repository's colcon build. Neither MuJoCo nor ROS is installed
where the gate runs, and the clone is never imported. `fake.py` is therefore a
package-local stand-in for the Python `mujoco` module: it parses the same MJCF
and its includes for the actuator ranges, joint dimensions and timestep, but
its integrator is a placeholder and its dynamics are not MuJoCo's. The real
`sim` backend would import the official `mujoco` module and load the same
file; it was not run here. No ROS graph, simulator or hardware was contacted.

## Safety

The device is simulated at R0: `cap.world.step.v1` and `cap.world.reset.v1` are
isolated simulation stepping. The runtime latches in software on an e-stop and
refuses step and reset until `mhs.safety.reset` clears the latch; the last
integration state stays readable. This is a software latch on a simulation, not
a physical emergency stop, and the driver claims no hardware safety.

## Tags

`ros2`, `multipanda`, `franka`, `panda`, `mujoco`, `simulation`, `robot-arm`, `dual-arm`
