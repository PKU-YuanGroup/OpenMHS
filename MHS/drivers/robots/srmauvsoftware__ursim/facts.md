OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and is not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.srmauvsoftware/ursim

Every fact cites the pinned clone at commit `feb7d257e61f192067209de5456965d7d0a3a612`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| DepthPublisher declares the absolute /depth topic with std_msgs/Float64. | upstream_code | unity/Assets/Publishers/DepthPublisher.cs:9-13 |
| AUV.SendDepth publishes vehicle.transform.position.y as a Float64Msg on the depth topic. | upstream_code | unity/Assets/Scripts/AUV.cs:78-84 |
| HeadingPublisher declares the absolute /imu/HeadingTrue_degree topic with std_msgs/Float64. | upstream_code | unity/Assets/Publishers/HeadingPublisher.cs:10-16 |
| AUV.SendHeading publishes vehicle.transform.rotation.eulerAngles.y as a Float64Msg on the heading topic. | upstream_code | unity/Assets/Scripts/AUV.cs:114-123 |
| imuPublisher declares the absolute /imu/data topic with sensor_msgs/Imu. | upstream_code | unity/Assets/Publishers/imuPublisher.cs:9-13 |
| AUV.Start leaves the ros.AddPublisher(typeof(imuPublisher)) registration commented out. | upstream_code | unity/Assets/Scripts/AUV.cs:28 |
| ImuSubscriberCallback subscribes to the absolute /imu/data topic with sensor_msgs/Imu. | upstream_code | unity/Assets/Subscribers/ImuSubscriberCallback.cs:9-14 |
| ImuSubscriberCallback.CallBack sets the Capsule's transform.rotation from the received IMU quaternion. | upstream_code | unity/Assets/Subscribers/ImuSubscriberCallback.cs:21-33 |
| AUV.Start opens a ROSBridgeWebSocketConnection to ws://192.168.0.100 on port 9090. | upstream_code | unity/Assets/Scripts/AUV.cs:25 |
| The vendored SimpleJSON.cs carries the MIT License, Copyright (c) 2012-2017 Markus Göbel. | upstream_code | unity/Assets/Libraries/ROSBridgeLib/SimpleJSON.cs:57-59 |
| AUV.SendImu builds sensor_msgs/Imu with the vehicle quaternion, zero angular-velocity and linear-acceleration vectors, covariance arrays and a header. | upstream_code | unity/Assets/Scripts/AUV.cs:87-111 |
| CompressedImagePublisher declares the absolute /image/compressed topic with sensor_msgs/CompressedImage. | upstream_code | unity/Assets/Publishers/CompressedImagePublisher.cs:9-13 |
| AUV.SendImage reads a 640x480 RGB24 texture, encodes JPEG, sets the format string 'jpeg' and publishes a CompressedImageMsg on the compressed-image topic. | upstream_code | unity/Assets/Scripts/AUV.cs:54-75 |
| AUV.Start registers the CompressedImage, Depth and Heading publishers plus the Thruster and Imu subscriber callbacks. | upstream_code | unity/Assets/Scripts/AUV.cs:24-32 |
| AUV.Update has every StartCoroutine call for image, depth, IMU and heading commented out. | upstream_code | unity/Assets/Scripts/AUV.cs:40-47 |
| ThrusterCallback declares the absolute /thruster topic with type thrusters/ThrusterMsg. | upstream_code | unity/Assets/Subscribers/ThrusterCallback.cs:20-25 |
| ThrusterCallback subtracts 290 from each field and calls AddForceAtPosition on the capsule Rigidbody. | upstream_code | unity/Assets/Subscribers/ThrusterCallback.cs:52-73 |
| The ROS thruster node imports thrusterMsg from control.msg but passes thruster, which these lines do not define, as the rospy.Publisher message class. | upstream_code | ros/src/control/scripts/thruster.py:4-10 |
| control/thruster.msg defines eight uint16 thruster fields. | upstream_code | ros/src/control/msg/thruster.msg:1-8 |
| The control CMake action list contains heave, pitch, sway, yaw, roll and surge only; no stop, pause or reset action is generated. | upstream_code | ros/src/control/CMakeLists.txt:58-68 |
| heave.action carries only a float32 final value in its result, with no success or failure field. | upstream_code | ros/src/control/action/heave.action:4-5 |
| The heave action server uses an undefined Float64 name, reads self.heave before assignment, references an undefined successt name and an undefined req name, and has no set_aborted path. | upstream_code | ros/src/control/servers/heave.py:1-47 |
| The roll server imports a control.srv roll type and creates a rospy.Service on roll_service. | upstream_code | ros/src/control/servers/roll.py:2-11 |

## Scope

The package is a configuration-only ROS 1 `RosDriver` over rosbridge, mode `simulated`,
device kind `world.sim`, risk R0. It exposes three explicit fresh-subscription
observations: `/depth` (`std_msgs/Float64`), `/imu/HeadingTrue_degree`
(`std_msgs/Float64`) and `/imu/data` (`sensor_msgs/Imu`). The topics and types are the
absolute names declared by the Unity publisher classes (and, for `/imu/data`, by the
`ImuSubscriberCallback` that the pinned scene registers), not relative ROS names. The
operator runs Unity, the ROS nodes and rosbridge separately; this package starts none
of them. The scene connects to a hard-coded rosbridge at `ws://192.168.0.100:9090`.

The control surface is **NOT COVERED**. `ThrusterCallback` accepts eight forces on
`/thruster` as `thrusters/ThrusterMsg`, but the ROS `thruster.py` publisher is broken
(undefined `thruster` name at line 10 and an invalid `thrusterMsg` import at line 4).
The six action definitions have no success field in their results, and the heave
server contains undefined names and no abort path. The roll server is a service, not
an action server. There is no stop, pause, reset or step service or action in the
pinned ROS package. A neutral `/thruster` publication is transmission-only, not an
acknowledged stop, so a control profile would not satisfy the RosDriver e-stop
contract. The package therefore binds only the observation profile and makes no
motion or stop claim. The `/image/compressed` topic is **NOT COVERED**:
`CompressedImagePublisher.cs` declares a 640x480 RGB24 JPEG stream, but its
`StartCoroutine` is commented out in `AUV.cs:40-47`, `cap.sensing.image.v1` binds a
`sensor.camera` resource rather than this `world.sim` device, and the SDK image
artifact path is restricted to that class id. No image artifact, frame size, codec
behavior or exposure is claimed.

## Publisher state

`AUV.Update` leaves all four telemetry coroutines commented out, so the pinned scene
declares the publishers but starts no stream. `/imu/data` is not simulator output at all
in the pinned scene: `AUV.Start` leaves the IMU publisher registration commented out and
registers `ImuSubscriberCallback`, which sets the simulated vehicle's rotation from every
received sample, and no ROS node in the clone publishes the topic (the `sensor` package is
empty). The IMU observation therefore returns another client's sample, which also rotates
the simulated vehicle; enabling `SendImu` as well would feed the scene's own rotation back
into it. The fake answers each subscription with
one placeholder sample; it establishes no sample age, publisher rate or frame. A live
deployment must start a publisher or enable the coroutines. A silent topic makes the
observation fail at its deadline; it does not return a held sample.

## Limits and safety

No numeric input is declared: every capability is a read-only subscription, so no
`Limit` and no `site-limits.example.json` are needed. The package commands no
actuation. A stock e-stop is the runtime software latch (`estop: software_only`);
no native stop, simulator pause or physical e-stop is declared or claimed. The
observation extension capabilities remain latched after an e-stop because the server
does not treat an extension's read verb as a safety exemption.

## Fidelity

`driver.py` describes the deployed fake: engine `canned:ROS-free topic stand-in (no
physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, no snapshot/restore. The fake is not the Unity simulator: it runs no
scene, physics, buoyancy, collision, ROS graph, image stream or wall-clock pacing.
Every canned value is test data, not a measurement.

## Tags

`ros`, `ros1`, `simulation`, `underwater`, `auv`, `ursim`, `depth`, `heading`, `imu`
