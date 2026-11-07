# Facts and tags for gh.rickstaa/panda-gazebo

Every fact cites the pinned clone at commit `113df8afa8de6c4342a99d3eb33b05084da644b9`.
`upstream_code` refs name `path/in/clone:LINE` (a bounded range where the statement
spans adjacent lines); `vendor_doc` refs name a text file of the clone. The same
facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes a ROS Noetic package for a Panda Emika Franka Gazebo simulation that wraps the franka_ros and panda_moveit_config packages. | vendor_doc | README.md:7-11 |
| start_simulation.launch defaults the world to empty.world and control_type to trajectory. | upstream_code | panda_gazebo/launch/start_simulation.launch:7-15 |
| The launch starts a node named panda_control_server and, for trajectory control, loads the arm follow-joint-trajectory action instead of the set_joint_commands service. | upstream_code | panda_gazebo/launch/put_robot_in_world.launch:90-97 |
| PandaControlServer creates a SimpleActionServer of type FollowJointTrajectoryAction on the relative name formed from the last component of its node name and '/panda_arm/follow_joint_trajectory'. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:376-386 |
| The action goal declares trajectory, path_tolerance, goal_tolerance, goal_time_tolerance, create_time_axis, time_axis_step and timeout, whose comment says a timeout of 0 waits indefinitely; the result declares error_code and error_string. | upstream_code | panda_gazebo/action/FollowJointTrajectory.action:5-58 |
| The server connects a SimpleActionClient of type control_msgs FollowJointTrajectoryAction to the relative action name panda_arm_trajectory_controller/follow_joint_trajectory when that server exists. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:341-348 |
| The execute callback sends the converted goal through that client, waits for the result with goal.timeout, and aborts with error_code -6 when the wait does not finish. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:1585-1598 |
| The wrapper succeeds only when its preempt flag is false and the forwarded controller result has error_code SUCCESSFUL; otherwise it aborts with the forwarded result. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:1601-1610 |
| The preempt callback cancels the forwarded controller goal when it is active or preempting and then marks the wrapper goal preempted, without waiting for the controller's terminal result. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:1624-1636 |
| PandaControlServer creates the SetGripperWidth service on the relative name formed from the last component of its node name and '/panda_hand/set_gripper_width' when the gripper is loaded. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:215-223 |
| The gripper callback halves the requested width, clips the result to [0, 0.08], puts it in a GripperCommandGoal's command.position with the request's max_effort (or GRASP_FORCE when that is 0 and grasping is true, else 0), and sends the goal when the gripper client is connected. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:1466-1488 |
| load_panda_joint_limits sets the finger joint limits of panda_finger_joint1 and panda_finger_joint2 to 0.0 and 0.04. | upstream_code | panda_gazebo/src/panda_gazebo/common/helpers.py:613-621 |
| The gripper callback waits for the gripper action result only when wait is true, using the request timeout; otherwise it sets success true after sending the goal; without a connected gripper client it sets success false. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:1486-1509 |
| SetGripperWidth.srv declares width, grasping, max_effort, wait and timeout, and returns success and message. | upstream_code | panda_gazebo/srv/SetGripperWidth.srv:1-12 |
| GRASP_FORCE is 10, and its comment states the Panda continuous force is 70 N and max_force is 140 N. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:73-74 |
| The arm joint names are panda_joint1 through panda_joint7 and the hand names are panda_finger_joint1 and panda_finger_joint2. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:79-90 |
| PandaControlServer subscribes to the relative topic 'joint_states' with JointState messages. | upstream_code | panda_gazebo/src/panda_gazebo/core/control_server.py:317-320 |
| The Gazebo world plugin's SERVICE_NAME constant is the absolute name /lock_unlock_panda_joints. | upstream_code | panda_gazebo/src/panda_joint_locker_world_plugin.cpp:13 |
| The plugin's Load creates a node handle named panda_joint_control_plugin and advertises SERVICE_NAME on it with the LockUnlockJoints callback. | upstream_code | panda_gazebo/src/panda_joint_locker_world_plugin.cpp:47-51 |
| The callback looks up the Gazebo model named by MODEL_NAME and returns success false when it is missing; it returns success false at the first missing joint without restoring the joints it has already handled. | upstream_code | panda_gazebo/src/panda_joint_locker_world_plugin.cpp:73-113 |
| For lock true the callback stores each joint's present lower and upper limits and sets both limits to the joint's current position; for lock false it restores the stored limits when both exist; it then returns success true. It reads no joint velocity. | upstream_code | panda_gazebo/src/panda_joint_locker_world_plugin.cpp:93-117 |
| The plugin's MODEL_NAME constant is panda. | upstream_code | panda_gazebo/src/panda_joint_locker_world_plugin.cpp:12 |
| LockJoints.srv declares joint_names and lock in the request and success and message in the response. | upstream_code | panda_gazebo/srv/LockJoints.srv:1-6 |
| The shipped empty.world loads the panda_joint_locker plugin from libpanda_gazebo.so. | upstream_code | panda_gazebo/resources/worlds/empty.world:20-21 |
| The package declares the MIT licence. | upstream_code | panda_gazebo/package.xml:13 |

## Scope and safety contract

The selected scope is the upstream control server's **trajectory action**, the wrapper **gripper width service**
and the world plugin's **lock service**, plus one `/joint_states` observation. The driver does not bind the
`set_joint_commands` service (loaded only when `control_type` is position or effort), the MoveIt planner
services, the dynamic reconfigure servers or the camera/metadata surfaces. A deployment must use the
launch's default `control_type:=trajectory`; otherwise the wrapper action is not created
(`panda_gazebo/launch/put_robot_in_world.launch:90-97`).

The trajectory action is the primary motion interface: the wrapper forwards the goal to
`panda_arm_trajectory_controller/follow_joint_trajectory`, waits with `goal.timeout`, and succeeds only when
the forwarded controller reports `error_code == SUCCESSFUL` and the wrapper was not preempted
(`control_server.py:1585-1610`). A terminal action result is not a stopped-state measurement.

The preempt callback cancels the forwarded goal and immediately calls
`self._arm_joint_traj_as.set_preempted()` without waiting for the controller's terminal result
(`control_server.py:1624-1636`). That acknowledgement alone is therefore not evidence of quiescence. The
runtime's ROS action bridge instead requires an independent fresh safe-state acknowledgement after a
cancelled terminal result.

The safe state is the Gazebo world plugin's `/lock_unlock_panda_joints` service: it stores each joint's
present lower and upper limit and sets both to the current position (`panda_joint_locker_world_plugin.cpp:73-101`).
It returns success after that limit update, not after a velocity measurement. It is a simulated joint-limit
freeze, not a physical emergency stop, and the runtime software latch is what prevents new MHS commands.

The lock is not undone by this package. It declares no unlock, `mhs.safety.reset` does not unlock, and every
lock request makes the plugin store the joint's present limits as the limits an unlock restores
(`panda_joint_locker_world_plugin.cpp:93-111`). A reviewer probe of the fake showed the runtime sending the lock
twice for an idle e-stop, four times for an e-stop with a trajectory goal in flight and three times for an
ordinary trajectory cancellation; after any of them the upstream unlock restores the locked limits, so the
simulated arm stays frozen until the model is respawned or Gazebo restarts. Gazebo keeps running after the lock,
and MoveIt, the planner server and RViz, which the shipped launch starts by default, are not fenced by the MHS
latch.

## Bounds

The gripper input is the **per-finger** target. The upstream callback receives the total width, halves it and
clips the finger target to `[0, 0.08]` m (`control_server.py:1466-1472`); the binding sends twice the
per-finger input as the total. That clip is an upstream convention error: 0.08 m per finger is twice the finger
joint limit the clone itself states (`0.0` to `0.04` m in `load_panda_joint_limits`, `helpers.py:613-621`), and
franka_gazebo's gripper simulation (in the `franka_ros` submodule, outside the pinned object store) refuses a
per-finger position above 0.04 m while the wrapper with `wait` false still reports success. The reviewer
therefore bounds `finger_width` by the clone's 0.04 m finger limit rather than by the clip. The force bound is the clone's
comment `continuous force: 70N, max_force: 140 N` (`control_server.py:73-74`); the continuous value is
reported in the description but only the stated maximum is used as the hard limit.

No text of the pinned top-level tree states the seven arm joints' travel limits. The package loads them at
runtime from `franka_description/robots/panda/joint_limits.yaml`
(`panda_gazebo/src/panda_gazebo/common/helpers.py:596-623`), but that file belongs to the `franka_ros` submodule and is not present in the
pinned top-level commit's object store. The driver therefore uses `Limit.operator_required` for the
trajectory positions, the automatic time-axis step and the execution timeout; until an operator overlay
supplies them, every call carrying those fields is refused with `MHS.SAFETY.LIMITS_UNSET`.
`site-limits.example.json` is an example overlay only; its values are not device facts and a site must
replace them with the reviewed range of its own cells.

## Fake

`fake.py` is a ROS-free event-driven stand-in, not a recording of captured traffic and not the upstream
Gazebo simulator. It answers the declared actionlib goal/cancel/result topics, the two services and the
`/joint_states` subscription with placeholder values, each marked `# placeholder`. It does not run Gazebo,
`franka_gazebo`, `ros_control`, `franka_gripper`, MoveIt or a ROS graph. The fake completes a trajectory
instantly with a canned `error_code`; it records a lock as a boolean and does not enforce Gazebo joint
limits. The F0 gaps in `driver.py` state these limits and the uncited `joint_limits.yaml` location. The real
`/joint_states` publisher order, controller timing, contact, gravity, collision and every stop latency are
not established here.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `panda`, `franka`, `arm`, `trajectory`, `gripper`
