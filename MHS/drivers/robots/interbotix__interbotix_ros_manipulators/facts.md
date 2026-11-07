OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.interbotix/interbotix_ros_manipulators

All citations are at commit `0bb2b0e6d0e619bff02cf74dbd5af5681dcf80c9`, relative to the clone root. The selected profile is the **wx250s** X-Series arm; the repository is a family of XS and UX arm packages and does not select one model itself.

## Facts

| fact | source | ref |
|---|---|---|
| The diagnostic example advertises `interbotix_xs_msgs/JointGroupCommand` on the relative `commands/joint_group` topic and `interbotix_xs_msgs/JointSingleCommand` on the relative `commands/joint_single` topic. | upstream_code | `interbotix_ros_xsarms/examples/interbotix_xsarm_diagnostic_tool/src/xsarm_diagnostic_tool.cpp:26-27` |
| The same example subscribes to the relative `joint_states` topic and hands each sample to a `sensor_msgs/JointState` callback (include at `:5`). | upstream_code | `interbotix_ros_xsarms/examples/interbotix_xsarm_diagnostic_tool/src/xsarm_diagnostic_tool.cpp:16-31` |
| The diagnostic path reads the joint lower and upper limits from the `RobotInfo` service and builds a sinusoidal joint command around 0 radians; the commanded group positions are therefore in radians. | upstream_code | `interbotix_ros_xsarms/examples/interbotix_xsarm_diagnostic_tool/src/xsarm_diagnostic_tool.cpp:63-75` and `:104-106` |
| The wx250s motor config declares the joint order `[waist, shoulder, elbow, forearm_roll, wrist_angle, wrist_rotate, gripper]` and groups the six arm joints as `arm`. | upstream_code | `interbotix_ros_xsarms/interbotix_xsarm_control/config/wx250s.yaml:3-12` |
| The X-Series control launch starts the external `interbotix_xs_sdk` node (or its `xs_sdk_sim` variant) under the `robot_name` namespace; the server implementation is not in this clone. | upstream_code | `interbotix_ros_xsarms/interbotix_xsarm_control/launch/xsarm_control.launch:32-41` |
| The X-Series README says the packages build on the `interbotix_xs_sdk` wrapper in the separate `interbotix_ros_core` repository and directs readers there for implementation details. | vendor_doc | `interbotix_ros_xsarms/README.md:28` |
| The joystick example's torque-off path sets `ArmJoy::TORQUE_OFF`; this is a message field, not an acknowledged stop service or action. | upstream_code | `interbotix_ros_xsarms/examples/interbotix_xsarm_joy/src/xsarm_joy.cpp:92-109` |
| The joystick example advertises `ArmJoy` on the relative `commands/joy_processed` topic. | upstream_code | `interbotix_ros_xsarms/examples/interbotix_xsarm_joy/src/xsarm_joy.cpp:260` |
| The diagnostic example's final motion writes `Profile_Velocity` with `set_motor_registers` and then publishes a `JointGroupCommand` carrying the sleep positions; that is another planned motion, not a stop. | upstream_code | `interbotix_ros_xsarms/examples/interbotix_xsarm_diagnostic_tool/src/xsarm_diagnostic_tool.cpp:130-140` |
| The diagnostic launch runs the tool under `ns="$(arg robot_name)"`, and its bag arguments name the resolved `/$(arg robot_name)/commands/joint_single`, `/$(arg robot_name)/joint_states` and `/$(arg robot_name)/temperatures/joint_group` endpoints. | upstream_code | `interbotix_ros_xsarms/examples/interbotix_xsarm_diagnostic_tool/launch/xsarm_diagnostic_tool.launch:30,40` |

## Selected surface and deployment identity

- The driver binds `/wx250s/commands/joint_group` and `/wx250s/joint_states`; `source_name` records the relative upstream tokens. The operator must run the external `xs_sdk` with `robot_name:=wx250s` (the launch defaults `robot_name` to `robot_model` at `xsarm_control.launch:3-4`). This namespace is a deployment assumption, not an upstream Fact.
- `cap.motion.joint_position.v1` is not exposed: the topic publication returns only `published: true` and `confirmed: false`, so the class's required `reached` output cannot be honestly produced. The package uses `x-cap.interbotix.joint_group.v1` with an inline transmitted-only output schema.
- `x-cap.interbotix.joint_states.v1` exposes only the `name` and `position` arrays one `sensor_msgs/JointState` sample carries. The clone does not state the velocity or effort units for this device, so those arrays are not exposed.
- The gripper's `JointSingleCommand` is not exposed: the clone's only single-command example writes the raw gripper joint position multiplied by two (`interbotix_ros_xsarms/examples/interbotix_xsarm_puppet/src/xsarm_puppet_single.cpp:71-72`), which does not establish the native command scale.
- `cap.motion.stop.v1` is not exposed. A topic publish is not a stop, and no in-clone service or action provides an acknowledged stop.

## Limits and units

- `joint_positions` is a fixed six-element array in radians with `Limit.operator_required`: the wx250s joint order is in the config, but the per-joint travel envelope depends on the selected robot model, its URDF and the deployed site. An operator supplies it in `site-limits.json`; every command is refused `MHS.SAFETY.LIMITS_UNSET` until then.
- No universal numeric bound is copied into a `Limit`. The selected wx250s configuration determines joint identity; installed model, load and site determine the reviewed envelope. No wx250 URDF is substituted for wx250s.
- JointState positions remain raw per-joint values; the arm radians evidence does not establish the gripper scale.

## Safety blocker

- The clone contains no `ros::ServiceServer`, `advertiseService`, `actionlib` server, `std_srvs`, `SetBool` or `Trigger` stop endpoint. A full-text search for those forms finds only the puppet `package.xml` dependency on `std_srvs` (`interbotix_ros_xsarms/examples/interbotix_xsarm_puppet/package.xml:22,31,40`) and no service implementation.
- The only torque-off path is the joystick's `ArmJoy::TORQUE_OFF` topic message. The pinned source preflight warns that disabling torque can drop a gravity-loaded arm, so it is not a safe state.
- The external `interbotix_xs_sdk` server is not in the clone; its callback, stop, reset and lifecycle semantics cannot be cited. No `estop_physical_ref` is claimed, and no `safe_state=True` action is invented.
- The device is at R2 because an arm command can cause collision, pinch or an unrecoverable load drop. The card's R0 floor is not used to lower that assessment.

## Tags

`ros`, `ros1`, `interbotix`, `wx250s`, `x-series`, `arm`, `joint-control`
