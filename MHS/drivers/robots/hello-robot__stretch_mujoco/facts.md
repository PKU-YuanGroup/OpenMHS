# Facts and tags for gh.hello-robot/stretch_mujoco

Every fact cites its source at commit `c78d6a1cd79bb5ead1b679610299563c1a91124a`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE` or an MJCF path with a line range). The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, `stretch_mujoco/models/scene.xml` (`models[0]`), as a `MujocoDriver`. The
scene includes the robot model `stretch.xml` and the docking station `docking_station.xml` (scene.xml:2-3), so the
loaded world contains the robot, the docking station and the scene's table and free objects. The model files are read
from the read-only clone; neither the models nor their assets are copied into this package and the clone is never
imported.

| fact | source | ref |
|---|---|---|
| The repository provides a MuJoCo simulation stack for Stretch with position control for the arm, head and gripper joints, velocity control for the mobile base, RGB and depth camera imagery and 2D lidar scans | vendor_doc | README.md:11 |
| The StretchMujocoSimulator class is documented to start the simulation, position-control the robot's ranged joints, velocity-control its mobile base, and read joint states and camera imagery | vendor_doc | README.md:101-107 |
| The upstream default scene is models/scene.xml and the default robot model is models/stretch.xml | upstream_code | stretch_mujoco/utils.py:33-34 |
| The upstream URDF model name defaults to SE3 | upstream_code | stretch_mujoco/utils.py:37 |
| The simulator loads the scene MJCF with MjModel.from_xml_path(scene_xml_path) and creates the MjData from that model | upstream_code | stretch_mujoco/mujoco_server.py:248-258 |
| The upstream reads every joint's range from mjmodel.jnt_range for njnt joints and records it as a joint limit | upstream_code | stretch_mujoco/mujoco_server.py:281-291 |
| The upstream writes a move_to command to data.actuator(name).ctrl and a keyframe command to mjmodel.keyframe(name).ctrl | upstream_code | stretch_mujoco/mujoco_server.py:539-574 |
| The scene includes stretch.xml and docking_station.xml | upstream_code | stretch_mujoco/models/scene.xml:2-3 |
| The Stretch body is a free base: base_link carries <freejoint/> | upstream_code | stretch_mujoco/models/stretch.xml:228-230 |
| The actuator defaults set the wheel control range to -6 to 6 and the lift control range to 0 to 1.1 | upstream_code | stretch_mujoco/models/stretch.xml:16-22 |
| The actuator defaults set the telescope control range to 0 to 0.52, head_pan to -4.04 to 1.73 and head_tilt to -1.53 to 0.79 | upstream_code | stretch_mujoco/models/stretch.xml:24-37 |
| The actuator defaults set wrist_yaw to -1.39 to 4.42, wrist_pitch to -1.57 to 0.56, wrist_roll to -3.14 to 3.14 and the gripper slide to -0.02 to 0.04 | upstream_code | stretch_mujoco/models/stretch.xml:44-62 |
| The actuator block declares ten actuators: two velocity actuators for the wheels and eight position actuators for lift, arm, wrist_yaw, wrist_pitch, wrist_roll, gripper, head_pan and head_tilt | upstream_code | stretch_mujoco/models/stretch.xml:524-535 |
| The arm position actuator drives the fixed tendon extend, which sums the four arm slide joints joint_arm_l0, joint_arm_l1, joint_arm_l2 and joint_arm_l3 | upstream_code | stretch_mujoco/models/stretch.xml:507-514 |
| The robot declares two wheel hinge joints, a lift slide joint and four arm telescope slide joints | upstream_code | stretch_mujoco/models/stretch.xml:284-339 |
| The head declares pan and tilt hinge joints and a nav-camera hinge joint | upstream_code | stretch_mujoco/models/stretch.xml:448-465 |
| The model declares the cameras d405_rgb and d405_depth, d435i_camera_rgb and d435i_camera_depth, and nav_camera_rgb | upstream_code | stretch_mujoco/models/stretch.xml:383-468 |
| The model declares a gyro, an accelerometer and a rangefinder lidar sensor on base_imu and lidar sites | upstream_code | stretch_mujoco/models/stretch.xml:537-541 |
| The model declares home and stow keyframes, each with a ten-element ctrl vector | upstream_code | stretch_mujoco/models/stretch.xml:543-546 |
| The model sets no option timestep: its option element carries integrator implicitfast, impratio 20 and cone elliptic | upstream_code | stretch_mujoco/models/stretch.xml:7-9 |
| A second Stretch robot model, stretch_mj_3.3.0.xml, declares the same ten actuators | upstream_code | stretch_mujoco/models/stretch_mj_3.3.0.xml:519-530 |
| The docking station is a free body: link_docking_station carries <freejoint/> | upstream_code | stretch_mujoco/models/docking_station.xml:43-45 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the loaded model itself, one interval per
actuator (`actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file). The package
declares no limit of its own and no `operator_required` bound, because the model file is the system of record for the
control envelope. The runtime refuses an out-of-range element before writing `data.ctrl`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the model file for
the actuator count, the control ranges, the joint dimensions and the option time step, but its integration is a
placeholder motion toward each control value and it resolves no mesh, contact, equality, tendon or actuator
constraint. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was compared with the
real engine. The gaps are listed in the `fidelity` attribute of `driver.py`.

Tags: stretch, hello-robot, mobile-manipulator, mujoco, simulation, robot
