# Facts and scope for gh.disaster-robotics-proalertas/usv_sim_lsa

Every fact cites the pinned clone at commit `61e8f4a5f78f18c01dac0d4eea7f4c3c416e6cb8`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`; the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The spawn_diffboat launch defaults the model namespace to diffboat and runs diff_control_heading.py inside that namespace. | upstream_code | usv_sim/launch/models/spawn_diffboat.launch:6-25 |
| diff_control_heading.py publishes thruster_command (sensor_msgs/JointState) and move_usv/result (std_msgs/Float64), and subscribes to state and move_usv/goal as nav_msgs/Odometry. | upstream_code | usv_base_ctrl/scripts/diff_control_heading.py:87-94 |
| thruster_ctrl_msg names the two thruster entries fwd_left and fwd_right and sets their JointState positions to rudder_ctrl() + 100 and -rudder_ctrl() + 100, clamping only values below zero. | upstream_code | usv_base_ctrl/scripts/diff_control_heading.py:43-58 |
| verify_result updates only result.data from the target_distance and desired_distance comparison; the thruster message is built separately in thruster_ctrl_msg. | upstream_code | usv_base_ctrl/scripts/diff_control_heading.py:38-67 |
| The heading controller loop runs at rate_value 10 Hz and publishes both topics every iteration until ROS shutdown. | upstream_code | usv_base_ctrl/scripts/diff_control_heading.py:83-100 |
| The diffboat controller configuration selects the thruster body control type, the state body-state topic and the body_command command topic. | upstream_code | usv_sim/config/diffboat.yaml:2-7 |
| The patrol script creates std_srvs/Empty service proxies for /gazebo/unpause_physics, /gazebo/pause_physics and /gazebo/reset_simulation. | upstream_code | usv_navigation/scripts/patrol_pid_scene1.py:38-43 |
| The patrol script calls pause, then resetSimulation, then unpause as separate service calls. | upstream_code | usv_navigation/scripts/patrol_pid_scene1.py:63-71 |
| The diffboat scenario launch runs the patrol node in namespace diffboat. | upstream_code | usv_sim/launch/scenarios_launchs/diffboat_scenario1.launch:30 |
| The patrol node publishes move_usv/goal as nav_msgs/Odometry and subscribes to move_usv/result as std_msgs/Float64. | upstream_code | usv_navigation/scripts/patrol_pid_scene1.py:34-37 |
| The shipped diffboat_scenario1 scene places the diffboat at x=240, y=95, z=1. | upstream_code | usv_sim/scenes/diffboat_scenario1.xml:63-72 |
| The patrol script builds its goal Odometry with header.frame_id 'world' and position z=0. | upstream_code | usv_navigation/scripts/patrol_pid_scene1.py:21-25 |
| The control documentation describes the forward-propulsion distance thresholds in meters and applies the same condition set to the differential boat. | vendor_doc | docs/control.md:13-23 |

## Scope

The selected device is the differential boat's heading controller and the Gazebo world it commands. The controller
and the patrol script use relative names inside the `diffboat` namespace; the driver records those upstream tokens
as `source_name` and configures the resolved endpoints `/diffboat/state`, `/diffboat/move_usv/goal`,
`/diffboat/move_usv/result` and `/diffboat/thruster_command`. A deployment with a different namespace must expose or
remap those endpoints; the driver does not discover the ROS graph.

The goal input is a single `nav_msgs/Odometry` publication. The controller consumes only
`pose.pose.position.x` and `pose.pose.position.y`, and the driver sets `header.frame_id` to `world` and
`pose.pose.position.z` to zero as the pinned patrol script does. A publication receipt is transmission evidence only:
the controller publishes the two thruster entries and a distance flag, but no ROS acknowledgement of motion, arrival
or stopping. The driver therefore exposes the state, result and thruster topics as explicit observations rather than
an automatic resource snapshot.

The heading controller subscribes to relative `state` as `nav_msgs/Odometry`; the launch runs it in the
`diffboat` namespace, so the driver observes `/diffboat/state`. The `/diffboat/thruster_command` topic is the heading
controller output (`sensor_msgs/JointState`); the driver observes it and does not publish thruster commands, so it
does not compete with the heading controller for the actuator topic. The simulator-side publisher and the
freefloating_gazebo plugin are in a git submodule that is not part of the pinned parent tree, so they are not cited
as facts and their callback bodies are not verified here.

## Safety

The device is simulated. The acknowledged stop is the Gazebo `/gazebo/pause_physics` service (`std_srvs/Empty`),
declared as the native e-stop binding and as an input-free `safe_state=True` action. The scenario script in the clone
creates that service proxy, calls it, then calls `/gazebo/reset_simulation` and `/gazebo/unpause_physics` separately;
the driver binds the reset service as the safety reset and exposes unpause only as an ordinary command that is refused
while the e-stop latch is engaged. Reset therefore does not bypass the latch. Clearing the latch also resets the
simulated world through `/gazebo/reset_simulation`; the clone shows only that the script calls unpause separately,
not the reset callback, so whether reset leaves physics paused is a gazebo_ros property (model review 2026-11-04).

Pausing physics is a simulator stop, not a physical emergency stop. The service implementation is in `gazebo_ros`,
outside the pinned clone; the clone proves the client endpoints and their separate use, not the callback body. The
pause service does not terminate the heading controller or clear its retained goal, so unpausing can resume motion
toward that target. The fake's service acknowledgement is not sensed quiescence and no hardware run is claimed.

The goal x/y bounds are `Limit.operator_required`: the valid area is defined by the loaded scenario and Gazebo world,
not by the heading controller. `site-limits.example.json` admits only the shipped scenario start point and is an
example only; the operator must supply the deployment's bounds.

## Fidelity

The fake is an analytic ROS-free recording stand-in at F0 with no physics step or pacing. It answers the declared
topics and services with placeholder values and does not replay captured traffic. It runs no Gazebo/UWSim world,
waves, wind, water current, buoyancy, thruster or boat dynamics, and its state, result and thruster samples do not
establish a trajectory or state-hash replay. The real `/diffboat/state` publisher belongs to the simulator
deployment and may produce no fresh sample while physics is paused; the fake still answers placeholder samples. Laser scan, camera, TF, water-current and wind-current surfaces are out of scope.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `uwsim`, `usv`, `marine`, `heading-control`
