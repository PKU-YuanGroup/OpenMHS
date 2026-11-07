# Facts and tags for gh.isri-aist/mujocorosutils

Every fact cites the pinned clone at commit `7fc0bc03a3d33db627bada456b5304922d849747`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where
the statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from
this page.

## Facts

| fact | source | ref |
|---|---|---|
| The pinned branch is the ROS 2 branch of MujocoRosUtils. | vendor_doc | README.md:1 |
| The README's feature list states that the plugins retrieve body poses and camera images, send commands to actuators and apply external forces through ROS interfaces. | vendor_doc | README.md:13 |
| ClockPublisher defaults `topic_name_` to the absolute `/clock` when the MJCF plugin config is empty. | upstream_code | plugin/ClockPublisher.cpp:124-126 |
| ClockPublisher creates a `rosgraph_msgs::msg::Clock` publisher on `topic_name_`. | upstream_code | plugin/ClockPublisher.cpp:138 |
| PosePublisher defaults the pose topic to `mujoco/<body name>/pose` and the velocity topic to `mujoco/<body name>/vel`; the sample explicitly sets them to `/pose` and `/vel`. | upstream_code | plugin/PosePublisher.cpp:173-180 |
| PosePublisher creates a `geometry_msgs::msg::PoseStamped` publisher and a `geometry_msgs::msg::TwistStamped` publisher. | upstream_code | plugin/PosePublisher.cpp:201-202 |
| ActuatorCommand defaults an empty `topic_name` to `mujoco/<actuator name>`; the sample overrides it with `/camera_pan`. | upstream_code | plugin/ActuatorCommand.cpp:112-115 |
| ActuatorCommand creates a `std_msgs::msg::Float64` subscription on `topic_name`. | upstream_code | plugin/ActuatorCommand.cpp:127-128 |
| ActuatorCommand::compute spins its own executor once and, when `ctrl_` is not NaN, writes it into `d->ctrl[actuator_id_]` and sets `ctrl_` to NaN; while `ctrl_` is NaN it leaves `d->ctrl` unchanged. | upstream_code | plugin/ActuatorCommand.cpp:145-153 |
| ActuatorCommand::reset has an empty body. | upstream_code | plugin/ActuatorCommand.cpp:134-138 |
| SensorPublisher maps a one-dimensional sensor to `MsgScalar` and creates a `mujoco_ros_utils::msg::ScalarStamped` publisher for it. | upstream_code | plugin/SensorPublisher.cpp:94-118 |
| SensorPublisher creates the concrete `mujoco_ros_utils::msg::ScalarStamped` publisher on `topic_name_` for scalar sensors. | upstream_code | plugin/SensorPublisher.cpp:183-185 |
| The sample MJCF attaches ActuatorCommand to the `camera_pan` actuator and configures the topic `/camera_pan`. | upstream_code | xml/sample_mujoco_ros_utils.xml:66-69 |
| The sample MJCF configures PosePublisher's `pose_topic_name` and `vel_topic_name` as `/pose` and `/vel`. | upstream_code | xml/sample_mujoco_ros_utils.xml:73-80 |
| The sample MJCF declares a `box_rangefinder` sensor and configures SensorPublisher's `topic_name` as `/box_rangefinder`. | upstream_code | xml/sample_mujoco_ros_utils.xml:101-106 |
| `ScalarStamped` carries a `std_msgs/Header` and one `std_msgs/Float64` value. | upstream_code | msg/ScalarStamped.msg:1-2 |
| ImagePublisher publishes a `sensor_msgs::msg::Image` with encoding `rgb8` for color and `32FC1` for depth; this package does not expose the camera plugin. | upstream_code | plugin/ImagePublisher.cpp:316-339 |
| ExternalForce subscribes to `mujoco_ros_utils::msg::ExternalForce`; this package does not expose the force plugin. | upstream_code | plugin/ExternalForce.cpp:133-134 |

## Scope

The package binds the sample MJCF's concrete endpoints: `/clock` as an explicit
read-only observation, `/pose` and `/vel` as body pose and velocity
observations, `/box_rangefinder` as a scalar sensor observation, and
`/camera_pan` as the ActuatorCommand subscription. The pose and velocity
publishers are configured with `output_tf: false` in the sample
(`xml/sample_mujoco_ros_utils.xml:78`), so the pose and velocity topics are the
observed representation; the optional TF broadcaster is not exposed.

The endpoint names are MJCF plugin configuration, not fixed node names. The
sample sets `/clock`, `/pose`, `/vel`, `/box_rangefinder` and `/camera_pan`;
another deployment can choose different names, and the operator must configure
the resolved endpoints before use. These deployment assumptions are not facts
about the upstream code.

`publish_skip_` is derived from the configured publish rate and the model
timestep (`plugin/PosePublisher.cpp:165`), so the effective rate depends on the
deployed MJCF; this package claims no rate.

The value of `/box_rangefinder` is raw MuJoCo `sensordata`; the clone does not
state a unit, so the output declares unit `1` and the caller must apply the
model's physical convention.

## Control and stop

The only command interface this package binds is the `std_msgs/msg/Float64` subscription created by
ActuatorCommand. Its callback stores the value, and `compute` copies it into
`d->ctrl[actuator_id_]` once before resetting the cache to NaN; while the cache
is NaN the plugin leaves `d->ctrl` unchanged, so a published value stays the
actuator's control input until the next message (the author's text said it
applies for one step; corrected by the model review of 2026-11-05). In the
sample, `camera_pan` is a position actuator on a hinge joint with range -90 90
(`xml/sample_mujoco_ros_utils.xml:50-63`), so the camera keeps driving toward
the last commanded position. There is no feedback, acknowledgement or
command-completion topic in the clone. A publication therefore proves
transmission only; it does not prove that the target was reached or that the
actuator stopped.

The plugin topics publish only while MuJoCo steps the model. While the
simulate application is paused or not stepping, the four resource reads fail
`NOT_READY` at their 2000 ms timeout, and every command still publishes but
completes only after those reads (reviewer probe on the fake).

The plugin's internal `reset` callback is empty and is not reachable through a
ROS service or action. The clone creates no ROS service or action server at all:
the plugin sources contain only publisher and subscription creation. A Float64
publication is not an acknowledged stop, so this package declares no
`safety_bindings` and does not claim a safe state it cannot confirm. This is the
recorded `HELPER_MISSING` blocker, not a missing fake feature.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS fake (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven canned state),
`realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. The
clock, pose, twist and rangefinder samples are placeholders and do not advance
with a MuJoCo simulation. The gaps name the unexposed camera, force, TF and
sensor variants.

## Safety

The device is simulated at R0. There is no e-stop binding because the upstream
surface has no acknowledged stop endpoint; the runtime's software latch does not
prove that an external ROS client cannot keep publishing. No hardware run,
rosbridge connection or MuJoCo process was used. `driver.lock.json` keeps
`reviewed_by: null`; this model-authored package is not hardware-reviewed.

## Tags

`ros`, `ros2`, `mujoco`, `simulation`, `clock`, `pose`, `rangefinder`, `actuator`
