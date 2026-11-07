# Facts and tags for gh.autorally/autorally

Every fact cites the pinned clone at commit `48bae14fe4b2d56e5ca11fd2fec3d7dfac7a0e75`.
`upstream_code` refs name `path/in/clone:LINE` (a bounded range is used where the
statement spans adjacent lines); `vendor_doc` refs name a text file of the clone.
The same facts are written into `driver.py` (`facts = [...]`); the reference file
is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| RunStop advertises an autorally_msgs/runstop publisher on the relative topic runstop. | upstream_code | autorally_core/src/RunStop/RunStop.cpp:68 |
| RunStop publishes from a timer whose rate parameter defaults to 5.0 Hz. | upstream_code | autorally_core/src/RunStop/RunStop.cpp:62-74 |
| RunStop sets motionEnabled true only for the GREEN serial state; YELLOW and every other state set it false, and one second without serial data also sets it false. | upstream_code | autorally_core/src/RunStop/RunStop.cpp:126-145 |
| The 4-button run-stop box sets motionEnabled false when a red or yellow button is pressed; the green button is required for true. | upstream_code | autorally_core/src/RunStop/RunStop.h:53-55 |
| The Gazebo controller subscribes to the vehicle-prefixed /runstop topic. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:310 |
| The Gazebo controller imports autorally_msgs.msg.chassisState, autorally_msgs.msg.runstop and autorally_msgs.msg.wheelSpeeds. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:129-132 |
| The Gazebo controller's getrunstop ANDs motionEnabled over every received sender and returns true when no sender has published. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:435-440 |
| When runstop motion is disabled, the controller forces throttle to 0 and labels the throttle commander runstop. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:345-348 |
| On the loop branch where delta_t is greater than 0, the controller publishes chassisState and the steering and axle joint commands. The cmd_timeout branch above that branch does not publish them. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:328-412 |
| The controller sets chassisState.runstopMotionEnabled from getrunstop before selecting commands. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:325-327 |
| The Gazebo controller publishes chassisState on the vehicle-prefixed /chassisState topic and wheelSpeeds on the vehicle-prefixed /wheelSpeeds topic. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:299-302 |
| The controller accepts steering and throttle only when the absolute value is at most 1.0 and frontBrake only within [0, 1], and only when the chassisCommand header stamp is less than 0.2 s old; otherwise that component is ignored. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:350-391 |
| The controller documents a cmd_timeout default of 0.5 s and states that vehicle motion is paused until a command is received once the timeout expires. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:80-84 |
| On cmd_timeout expiry the controller commands axle speed 0 through _ctrl_axles(0.0, 0.0, 0.0) and calls _ctrl_steering with the last steering angle and a zero velocity limit. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:328-334 |
| When steer_ang_vel_limit is not greater than 0, _ctrl_steering sets theta to the passed steer_ang and updates _last_steer_ang only when theta differs from it, so the timeout call leaves the steering angle unchanged. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:497-515 |
| The Gazebo controller sorts chassis commander priorities in ascending numeric order, so a lower number is considered first. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:258-259 |
| ConstantSpeedController subscribes to the relative constantSpeedController/speedCommand topic with std_msgs/Float64. | upstream_code | autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:71-72 |
| ConstantSpeedController stores the received Float64 value in m_mostRecentSpeedCommand and sends no acknowledgement. | upstream_code | autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:100-107 |
| On every wheelSpeeds callback ConstantSpeedController publishes constantSpeedController/chassisCommand with header.stamp now, sender constantSpeedController, steering -5.0 and frontBrake 0.0; throttle is clamped to [0, 1]. | upstream_code | autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:109-155 |
| When the stored speed command is not greater than 0.1, ConstantSpeedController sets chassisCommand.throttle to 0. | upstream_code | autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:149-153 |
| ConstantSpeedController initializes m_integralError to 0. | upstream_code | autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:55 |
| m_integralError is updated only while m_mostRecentSpeedCommand.data is greater than 0.1. | upstream_code | autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:120-138 |
| The README documents a /runstop topic of type autorally_msgs/runstop with sender and motionEnabled; motionEnabled true is required for the platform to move. | vendor_doc | README.md:151 |
| The README states the gamepad joystick node publishes runstop false at startup, that a button toggles it, and that runstopMotionEnabled in /chassisState shows the result. | vendor_doc | README.md:141-143 |
| The README documents constantSpeedController/speedCommand as a std_msgs/Float64 target velocity in m/s, states no numeric bound, and tells the operator to run a publisher on that topic at rate 10. | vendor_doc | README.md:165-170 |
| The Gazebo simulation launch starts autorally_controller with the vehicle_prefix parameter taken from the namespace argument and loads the commander priorities from the operator's AR_CONFIG_PATH. | upstream_code | autorally_gazebo/launch/autoRallyTrackGazeboSim.launch:73-79 |
| The simulation launch includes the joystickController launch. | upstream_code | autorally_gazebo/launch/autoRallyTrackGazeboSim.launch:87-88 |
| setupEnvVariables.sh exports AR_CONFIG_PATH to the autorally_util config directory. | upstream_code | autorally_util/setupEnvVariables.sh:31 |
| The shipped chassisCommandPriorities.yaml gives constantSpeedController priority 2 and joystick priority 4. | upstream_code | autorally_util/config/chassisCommandPriorities.yaml:1-6 |
| JoystickControl advertises autorally_msgs/runstop on the relative runstop topic and autorally_msgs/chassisCommand on the relative joystick/chassisCommand topic. | upstream_code | autorally_control/src/joystick/JoystickControl.cpp:47-53 |
| JoystickControl initializes its runstop sender to joystick and motionEnabled to false. | upstream_code | autorally_control/src/joystick/JoystickControl.cpp:55-56 |
| The controller documents wheel diameters in meters. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:64-68 |
| wheelSpeedsCb stamps wheelSpeeds.header.stamp with rospy.Time.now() before assigning the speeds. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:571 |
| wheelSpeedsCb computes each wheel speed as joint velocity times half the configured wheel diameter and publishes the absolute value. | upstream_code | autorally_gazebo/nodes/autorally_controller.py:559-586 |
| The four axle controllers in the Gazebo platform config are effort_controllers/JointEffortController. | upstream_code | autorally_gazebo/config/autoRallyPlatformJointCtrlrParams.yaml:34-48 |
| chassisState carries runstopMotionEnabled, autonomousEnabled, the steering, throttle and frontBrake values and their commander strings. | upstream_code | autorally_msgs/msg/chassisState.msg:1-14 |
| wheelSpeeds carries lfSpeed, rfSpeed, lbSpeed and rbSpeed. | upstream_code | autorally_msgs/msg/wheelSpeeds.msg:1-5 |
| runstop carries a sender string and a motionEnabled boolean. | upstream_code | autorally_msgs/msg/runstop.msg:1-4 |
| The real platform's AutoRallyChassis nodelet advertises chassisState and wheelSpeeds, subscribes to <commander>/chassisCommand for each configured commander and subscribes to /runstop. | upstream_code | autorally_core/src/autorally_chassis/AutoRallyChassis.cpp:64-101 |
| autorally.launch includes the autorally_chassis launch. | upstream_code | autorally_core/launch/autorally.launch:12 |

## Scope

The selected device is the AutoRally Gazebo simulation's ROS 1 control and
telemetry surface, not the physical platform. The package exposes:

- `/constantSpeedController/speedCommand` (`std_msgs/Float64`) as one x-cap
  publication whose input is the documented target velocity in m/s. The
  constant-speed controller nodelet must be running; it stores the value with
  no acknowledgement and publishes `constantSpeedController/chassisCommand` on
  its next wheelSpeeds callback.
- `/runstop` (`autorally_msgs/runstop`) only as the second step of the sensed
  stop (sender `openmhs`, `motionEnabled` false). There is no free-sender
  runstop capability and no re-enable. The Gazebo controller stores the message
  by sender and ANDs every sender's `motionEnabled`; an empty sender set means
  enabled. Sender `openmhs` stays false until the operator publishes it from
  outside MHS.
- `/chassisState` (`autorally_msgs/chassisState`) as fresh resource fields and
  as an explicit read capability. It is not the stop confirmation.
- `/wheelSpeeds` (`autorally_msgs/wheelSpeeds`) as fresh resource fields, as an
  explicit read capability, and as the sensed-stop source. The fake's wheel
  magnitude echoes the absolute stored target while motion is enabled; that
  echo is a placeholder, not the Gazebo plant, and it is what makes two
  different speed commands visible in the resource state.

The direct `chassisCommand` input is deliberately not exposed. The Gazebo
controller ignores any component whose `header.stamp` is 0.2 s old or older
(`autorally_gazebo/nodes/autorally_controller.py:350-391`), and a
configuration-only RosDriver has no ROS clock with which to stamp a publication.
The declared `speedCommand` input has no header and no age check.

The Gazebo controller publishes `/chassisState` from the fresh-command branch
of its loop and `/wheelSpeeds` from the `joint_states` callback. A subscription
waits for a fresh sample; it does not hold or cache an old one. If the
controller or its Gazebo joint feedback is absent, the read waits for its
deadline and fails.

The declaration assumes the controller's default empty `vehicle_prefix` and
root namespace. Multi-vehicle namespaces, remapped topics, and a different
`AR_CONFIG_PATH` priority list are operator deployment choices outside the
pinned facts. `autorally_util/setupEnvVariables.sh:31` exports `AR_CONFIG_PATH`
to the shipped `autorally_util` config directory.

## Safety

The device is simulated at R2 because the speed publication and the runstop
both drive a mobile base, and the real `AutoRallyChassis` nodelet consumes the
same topics (REVIEW.md item 12). The card floor is R0.

The e-stop is a sensed-confirmation stop (SAFE-049, simulated devices only).
It publishes `data` 0 on `constantSpeedController/speedCommand`, then `/runstop`
with sender `openmhs` and `motionEnabled` false. It is achieved only when three
consecutive fresh `/wheelSpeeds` samples, spanning the confirmation window,
have all four absolute wheel speeds at or below the operator's bound. The
thresholds are `Limit.operator_required`. The fake placeholders are in
`fixtures/estop-confirmation.json` and are not device facts. ROS 1 discards the
first sample of a subscription; the source declares no history. Anything else
is `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held.

The zero speedCommand is not a durable clear (SAFE-042, REVIEW.md item 13).
`ConstantSpeedController` stores a Float64 with no acknowledgement
(`ConstantSpeedController.cpp:100-107`) and, on the next wheelSpeeds callback,
publishes throttle 0 when the stored value is not greater than 0.1
(`:149-153`). A false runstop forces throttle 0 without clearing that Float64
(`autorally_controller.py:345-348`). `README.md:170` tells the operator to run
a publisher on `speedCommand` at rate 10, so another node can overwrite the
stop's zero, and a lost zero is not stored. Wheel speeds inside the bound can
therefore pass while the old target remains. This package publishes no
`motionEnabled` true and declares no re-enable. The operator recovers outside
MHS, and only after every other `speedCommand` publisher has stopped.
`m_integralError` is updated only while the stored speed is greater than 0.1
(`:120-138`) and is not cleared by the zero.

The default simulation launch starts the joystick node with runstop false
(`README.md:141`, `JoystickControl.cpp:55-56`). Because `getrunstop()` ANDs
all senders, motion stays disabled while joystick or sender `openmhs` is false.

The four axle controllers are `effort_controllers/JointEffortController`
(`autoRallyPlatformJointCtrlrParams.yaml:34-48`). Effort 0 coasts; the runstop
does not apply a brake. ConstantSpeedController publishes steering -5.0, which
the Gazebo controller rejects, so another commander's steering can still apply.
The shipped priority file lists `constantSpeedController` at 2 and `joystick`
at 4, and the controller sorts ascending
(`autorally_controller.py:258-259`). A paused simulation clock produces no new
wheel-speed stamps and the confirmation fails closed. This package does not
unpause Gazebo.

The real platform's `AutoRallyChassis` nodelet, started by
`autorally_core/launch/autorally.launch`, serves the same `/runstop`,
`/chassisState` and `/wheelSpeeds` contract
(`AutoRallyChassis.cpp:64-101`). Nothing in these bindings tells the simulation
from the real 1:5-scale car. A live deployment against the real platform would
drive real hardware and is out of scope for this simulated card. No physical
emergency stop is claimed. `publish_review` is required (licence
`NOASSERTION`). `reviewed_by` stays null.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS fake (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven with no physics
step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore.
The fake answers the declared subscriptions from placeholder state and records
the publications. Wheel speeds are a placeholder burst on a placeholder clock:
they stay at a coast magnitude while motion is enabled and the stored target is
above 0.1, and they decay after a zero target or a false runstop AND. The decay
is not Gazebo and not a measured coast time. No live ROS graph, rosbridge
connection, Gazebo process or hardware was run.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `autorally`, `runstop`, `speed-command`, `sensed-stop`
