OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.frankarobotics/franka_ros

Every fact cites the pinned clone at commit `ddd2fffd9de44b02ad15b4bbb2bfa2cec4d60d98`: `upstream_code`
(an implementation file) or `vendor_doc` (a text file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The launch file names the franka_gripper_node process franka_gripper and loads config/franka_gripper_node.yaml through rosparam. | upstream_code | franka_gripper/launch/franka_gripper.launch:6-13 |
| The example node config sets publish_rate 30 Hz, default_speed 0.1 m/s and default_grasp_epsilon inner/outer 0.005 m; they are configurable ROS parameters, not device bounds. | upstream_code | franka_gripper/config/franka_gripper_node.yaml:1-5 |
| The node constructs SimpleActionServer<StopAction> on the relative name "stop". | upstream_code | franka_gripper/src/franka_gripper_node.cpp:101-105 |
| The node constructs SimpleActionServer<GraspAction> on the relative name "grasp". | upstream_code | franka_gripper/src/franka_gripper_node.cpp:117-122 |
| The node constructs SimpleActionServer<MoveAction> on the relative name "move". | upstream_code | franka_gripper/src/franka_gripper_node.cpp:109-113 |
| The node constructs SimpleActionServer<HomingAction> on the relative name "homing". | upstream_code | franka_gripper/src/franka_gripper_node.cpp:92-96 |
| The stop handler calls gripper.stop() and the homing handler calls gripper.homing(). | upstream_code | franka_gripper/src/franka_gripper.cpp:86-92 |
| The move handler calls gripper.move(goal->width, goal->speed). | upstream_code | franka_gripper/src/franka_gripper.cpp:82-84 |
| The grasp handler calls gripper.grasp(goal->width, goal->speed, goal->force, goal->epsilon.inner, goal->epsilon.outer). | upstream_code | franka_gripper/src/franka_gripper.cpp:94-96 |
| The node publishes sensor_msgs/JointState on the relative name "joint_states". | upstream_code | franka_gripper/src/franka_gripper_node.cpp:174-175 |
| The node fills each of the two finger positions from gripper_state.width * 0.5, so each value is half of the total opening width. | upstream_code | franka_gripper/src/franka_gripper_node.cpp:185-186 |
| The node obtains robot_ip, default_speed and default_grasp_epsilon from ROS parameters. | upstream_code | franka_gripper/src/franka_gripper_node.cpp:57-88 |
| The node obtains publish_rate, joint_names and stop_at_shutdown from ROS parameters. | upstream_code | franka_gripper/src/franka_gripper_node.cpp:139-159 |
| The gripper documentation says StopAction aborts a running action and can be used to stop applying forces after grasping. | vendor_doc | franka_gripper/doc/index.rst:16-18 |
| The gripper documentation says GraspAction succeeds when the finger distance is within the inner and outer epsilon around the requested width. | vendor_doc | franka_gripper/doc/index.rst:10-14 |
| Grasp.action declares width in metres, speed in metres per second and force in newtons, and returns success and error. | upstream_code | franka_gripper/action/Grasp.action:1-7 |
| Move.action declares width in metres and speed in metres per second, and returns success and error. | upstream_code | franka_gripper/action/Move.action:1-6 |
| Stop.action declares no goal fields and returns success and error. | upstream_code | franka_gripper/action/Stop.action:1-3 |
| The franka_gazebo plugin advertises the relative "franka_control/set_user_stop" std_srvs/SetBool service to simulate the user stop. | upstream_code | franka_gazebo/src/franka_hw_sim.cpp:405-411 |
| The franka_gazebo documentation calls set_user_stop a special service only available in franka_gazebo for simulating the user stop; it is not a hardware stop service. | vendor_doc | franka_gazebo/doc/index.rst:230-234 |

## Scope and safety contract

The selected scope is the **Franka Hand gripper**, preserving grasp, move, homing, stop and joint-state
observation. It does not claim seven-axis arm integration or bind the additional GripperCommandAction
alias. The separate StopAction calls gripper.stop() and must return both a matching successful action
terminal and success=true. It is a software native stop, not an independent physical e-stop.

The action safety helper retains any older pending/unknown native goal. An early successful stop cannot
confirm safety while such work may still start or finish; terminal reconciliation and a fresh stop are
required before reset. The pinned move/grasp/homing callbacks do not check action cancellation, so a cancel
frame is never fabricated into a terminal result. Native stop interruption of homing and physical stop
latency remain unverified. Reset never performs homing, motion or re-arm. Stopping grasp force may release
a load; this is a deployment safety decision, not a universal safe-load guarantee.

The optional catalogue approach input is excluded from the closed grasp binding: the native gripper has
no approach-motion goal. A native nonexceptional failed grasp is ROS SUCCEEDED with success=false
(franka_gripper_node.cpp:20-33), represented as completed grasped=false. Move receipts expose
requested_speed_m_s only after successful native terminal confirmation. This is the submitted request
parameter, not measured speed; the source JointState velocity fields are fixed zeros (node.cpp:187-190).

This package requires the ROS action-safety helper. RESULT.json records integration and review status;
a passing software contract does not certify a deployed graph or device.
Hardware requires the existing human-review rule; reviewed_by remains null. No hardware run is claimed.

## Bounds

No line of the clone states a maximum finger opening, a grasp-force bound or a speed bound. The native GripperCommand alias checks
`GripperState.max_width`, but the selected JointState route does not publish that limit; `default_speed` / `default_grasp_epsilon` are
configurable ROS parameters (`franka_gripper/config/franka_gripper_node.yaml:1-5`), not device limits. The
driver therefore uses `Limit.operator_required` for the grasp width, grasp force, move width and move speed;
until an operator overlay supplies them every call carrying those fields is refused with
`MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example overlay only; its values are not
device facts and a site must replace them with the range of its own gripper.

## Fake

`fake.py` is a ROS-free analytic stand-in, not a recording of a real gripper and not the upstream Gazebo
plugin. It answers the four selected actionlib wire endpoints and the `JointState` subscription with placeholder
values, each marked `# placeholder`. It does not replay captured traffic, run Gazebo, model contact
physics or establish an MHS-Device level. The source node defaults to 30 Hz state publication, but the fake answers subscriptions on demand and
does not model cadence. Numeric positions, force and goal IDs are test data only. Controlled production
tests separately retain pending native-shaped goals; their cancellation alone never completes them.

## Tags

`ros`, `ros1`, `franka`, `panda`, `gripper`, `grasp`, `homing`, `stop`
