# Facts and tags for gh.uji-ros-pkg/underwater_simulation

Every fact cites the pinned clone at commit `7f4a276c55f34524e418f56a6da401172943f886`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The simulator defaults to data/scenes/cirs.xml and initializes the ROS node as UWSim. | upstream_code | uwsim/src/main.cpp:157-164 |
| The main loop runs at 60 Hz, sets the ROS interface time from ros::Time::now(), spins callbacks, steps physics when enabled and draws a frame every iteration. | upstream_code | uwsim/src/main.cpp:195-244 |
| The default scene declares ROSTwistToPAT for the girona500 vehicle on the absolute /g500/twist topic. | upstream_code | uwsim/data/scenes/cirs.xml:359-362 |
| ROSTwistToPAT subscribes to geometry_msgs/TwistStamped on its configured topic. | upstream_code | uwsim/src/ROSInterface.cpp:150-154 |
| ROSTwistToPAT::processData translates and rotates the vehicle by linear and angular twist times the wall-clock elapsed time since the previous message. | upstream_code | uwsim/src/ROSInterface.cpp:156-190 |
| ROSInterface.h defines MAX_ELAPSED as 1, commented as the maximum time in seconds between two consecutive control references. | upstream_code | uwsim/include/uwsim/ROSInterface.h:64-65 |
| processData uses zero elapsed time for the first message and whenever more than 1 s of wall time passed since the previous message, and applies one translation and rotation of twist times that elapsed time per message. | upstream_code | uwsim/src/ROSInterface.cpp:156-190 |
| The default scene also declares ROSPoseToPAT on /g500/pose for the girona500 vehicle. | upstream_code | uwsim/data/scenes/cirs.xml:368-371 |
| ROSPoseToPAT subscribes to geometry_msgs/Pose and sets position and orientation directly. | upstream_code | uwsim/src/ROSInterface.cpp:212-232 |
| The default scene declares ROSJointStateToArm on /uwsim/joint_state_command for the girona500 vehicle. | upstream_code | uwsim/data/scenes/cirs.xml:350-353 |
| ROSJointStateToArm subscribes to sensor_msgs/JointState and calls setJointPosition or setJointVelocity depending on which array is nonempty. | upstream_code | uwsim/src/ROSInterface.cpp:409-432 |
| The default scene declares ArmToROSJointState on the absolute /uwsim/joint_state topic. | upstream_code | uwsim/data/scenes/cirs.xml:346-349 |
| ArmToROSJointState advertises sensor_msgs/JointState, fills name and position, pushes effort 0 for every joint and leaves velocity empty. | upstream_code | uwsim/src/ROSInterface.cpp:691-714 |
| ROSSceneBuilder advertises the relative SpawnMarker service. | upstream_code | uwsim/src/ROSSceneBuilder.cpp:34 |
| The underwater_vehicle_dynamics dynamics node advertises the /dynamics/reset std_srvs/Empty service. | upstream_code | underwater_vehicle_dynamics/src/dynamics.py:323 |
| The /dynamics/reset callback sets velocity and pose back to their initial values and returns; it does not touch the thruster setpoint u. | upstream_code | underwater_vehicle_dynamics/src/dynamics.py:249-252 |
| UWSim_g500_dynamics.launch starts the g500 dynamics node, uwsim with the cirs.xml scene and keyboard.py publishing to /g500/thrusters_input. | upstream_code | underwater_vehicle_dynamics/launch/UWSim_g500_dynamics.launch:1-12 |
| dynamics.launch passes /<namespace>/pose as the dynamics node's default output topic. | upstream_code | underwater_vehicle_dynamics/launch/dynamics.launch:7-10 |
| The dynamics node publishes the vehicle pose from a rospy.Timer every uwsim_period. | upstream_code | underwater_vehicle_dynamics/src/dynamics.py:314-315 |
| dynamics_g500.yaml sets g500/dynamics/uwsim_period to 0.001. | upstream_code | underwater_vehicle_dynamics/config/dynamics_g500.yaml:5 |
| keyboard.py publishes a five-element thruster array every 0.1 s, zeros unless a key is pressed, and calls /dynamics/reset on the space key. | upstream_code | underwater_vehicle_dynamics/src/keyboard.py:29-66 |
| stopROS calls ros::shutdown while ROS is ok, and stopAll flushes the network simulator log and calls stopROS. | upstream_code | uwsim/src/main.cpp:31-50 |
| The SIGTERM callback calls stopAll. | upstream_code | uwsim/src/main.cpp:206-209 |
| The default scene declares RangeSensorToROSRange on the absolute /uwsim/g500/range topic at rate 10. | upstream_code | uwsim/data/scenes/cirs.xml:363-367 |
| RangeSensorToROSRange advertises sensor_msgs/Range and publishes the measured distance in range and the configured sensor range in max_range. | upstream_code | uwsim/src/ROSInterface.cpp:941-960 |
| The default scene declares ImuToROSImu on the relative g500/imu topic. | upstream_code | uwsim/data/scenes/cirs.xml:372-376 |
| ImuToROSImu advertises sensor_msgs/Imu and fills the orientation quaternion and the orientation covariance diagonal; angular_velocity and linear_acceleration remain the message defaults. | upstream_code | uwsim/src/ROSInterface.cpp:576-600 |
| The default scene declares PressureSensorToROS on the relative g500/pressure topic. | upstream_code | uwsim/data/scenes/cirs.xml:377-381 |
| PressureSensor::getMeasurement returns the z translation in the localized world frame plus Gaussian noise. | upstream_code | uwsim/src/PressureSensor.cpp:18-29 |
| PressureSensorToROS::publish copies getMeasurement() into the pressure field of an underwater_sensor_msgs/Pressure message. | upstream_code | uwsim/src/ROSInterface.cpp:618-631 |
| The default scene declares VirtualCameraToROSImage for camera bowtech1 on /uwsim/camera1 and /uwsim/camera1_info. | upstream_code | uwsim/data/scenes/cirs.xml:354-358 |
| VirtualCameraToROSImage advertises an image_transport image and a sensor_msgs/CameraInfo and sets the image encoding to 32FC1 for a depth camera, mono8 for a black-and-white one and rgb8 otherwise. | upstream_code | uwsim/src/ROSInterface.cpp:755-796 |
| The uwsim package declares the licence GPL. | upstream_code | uwsim/package.xml:15 |
| uwsim/license.txt is the GNU General Public License version 3. | upstream_code | uwsim/license.txt:1-2 |

## Scope

The package binds the default scene's vehicle twist publication
(`/g500/twist`, geometry_msgs/TwistStamped, `uwsim/data/scenes/cirs.xml:359-362`,
`uwsim/src/ROSInterface.cpp:150-154`), the arm joint-state observation
(`/uwsim/joint_state`, sensor_msgs/JointState,
`uwsim/data/scenes/cirs.xml:346-349`, `uwsim/src/ROSInterface.cpp:691-714`), and the
range observation (`/uwsim/g500/range`, sensor_msgs/Range,
`uwsim/data/scenes/cirs.xml:363-367`, `uwsim/src/ROSInterface.cpp:941-960`). The
default scene has no `PATToROSOdom` output, so no vehicle pose or odometry topic is
bound from it.

The IMU and pressure topics are written as relative names (`g500/imu`,
`g500/pressure`) in the scene XML; the package does not invent a resolved absolute
spelling for them. The pressure message is named `pressure`, but
`PressureSensorToROS::publish` fills it from `PressureSensor::getMeasurement`, which returns a
localized z translation plus noise (`uwsim/src/ROSInterface.cpp:618-631`,
`uwsim/src/PressureSensor.cpp:18-29`); it is therefore not bound under a pressure class. The camera image and CameraInfo, range camera, DVL, GPS,
multibeam LaserScan, force, echo, contact, TF and the `/g500/pose` and
`/uwsim/joint_state_command` control inputs are **NOT COVERED**.

## Stop path and safety

uwsim advertises only the relative `SpawnMarker` service
(`uwsim/src/ROSSceneBuilder.cpp:34`); it creates no stop, pause, reset or action
server. The simulator's `stopAll`/`stopROS` path is a process shutdown reached
from the SIGTERM callback or after the viewer loop
(`uwsim/src/main.cpp:31-50`, `uwsim/src/main.cpp:206-208`,
`uwsim/src/main.cpp:246-247`), not a ROS binding.

Model review (2026-11-05): the author's fact that SpawnMarker is "the only advertised ROS service
in the clone" was wrong. The optional `underwater_vehicle_dynamics` node advertises
`/dynamics/reset` (`dynamics.py:323`), whose callback restores pose and velocity but keeps the
thruster setpoint `u` (`dynamics.py:249-252`), so it is a reset, not a stop. Its shipped
`UWSim_g500_dynamics.launch` also starts `keyboard.py`, which publishes thrusters every 0.1 s, and
the dynamics node publishes `/g500/pose` every `uwsim_period` (0.001 s), which `ROSPoseToPAT`
applies directly, so in that deployment the pose stream competes with `/g500/twist`.
`ROSTwistToPAT::processData` moves the vehicle once per message by its twist times the wall time
since the previous message, zero for the first message and after a gap above 1 s
(`uwsim/src/ROSInterface.cpp:156-190`): the vehicle does not keep a velocity, isolated MHS
publications more than 1 s apart move nothing, and after the latch no MHS message moves it, but
nothing acknowledges that and other publishers are not fenced. No acknowledged stop is
declared, so the package is blocked on the control surface rather than claiming a
safe state. The fake latches in software when the server's e-stop is used, but the
latch cannot stop the simulator and the e-stop receipt reports the missing native
stop.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS recording fake (no
physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, and no snapshot/restore. The joint names, joint positions and range
value are placeholders. The twist publication is transmission only. The fake runs
no UWSim, OSG, Bullet physics, scene or wall-clock loop; a live run must receive the
observations from the operator's simulator.

## Tags

`ros`, `ros1`, `simulation`, `underwater`, `uwsim`, `twist`, `joint_state`, `range`
