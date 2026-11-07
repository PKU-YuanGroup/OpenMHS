OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.stdr-simulator-ros-pkg/stdr_simulator

Every fact cites the pinned clone at commit `1bcdec7b79c9e4a2960f7fcf9c150c67485ecab4`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| Server::Server constructs the spawn and delete action servers on the public node handle with the relative names stdr_server/spawn_robot and stdr_server/delete_robot. | upstream_code | stdr_server/src/stdr_server.cpp:31-38 |
| stdr_server.h includes the generated stdr_msgs/SpawnRobotAction and stdr_msgs/DeleteRobotAction headers. | upstream_code | stdr_server/include/stdr_server/stdr_server.h:35-36 |
| stdr_server.h aliases SpawnRobotServer and DeleteRobotServer to actionlib::SimpleActionServer over stdr_msgs::SpawnRobotAction and stdr_msgs::DeleteRobotAction. | upstream_code | stdr_server/include/stdr_server/stdr_server.h:70-77 |
| activateActionServers starts the spawn, register and delete action servers. | upstream_code | stdr_server/src/stdr_server.cpp:601-605 |
| The constructor starts the action servers only when it receives a map path as argv, or after load_static_map/load_static_map_external constructs a MapServer; without a map it skips activation. | upstream_code | stdr_server/src/stdr_server.cpp:50-63 |
| spawnRobotCallback aborts a goal whose sensor frame_id values repeat, otherwise calls addNewRobot; on success it sets the goal succeeded and publishes the active robot list. | upstream_code | stdr_server/src/stdr_server.cpp:514-537 |
| addNewRobot defaults an empty kinematicModel.type to ideal, assigns the name robot<N> from a monotonically increasing server counter, loads a stdr_robot/Robot nodelet, and waits up to 5.0 s for the robot to register. | upstream_code | stdr_server/src/stdr_server.cpp:621-638 |
| addNewRobot returns a nonempty message when the robot does not register within the 5.0 s wait; spawnRobotCallback then aborts the goal. | upstream_code | stdr_server/src/stdr_server.cpp:636-650 |
| deleteRobotCallback calls deleteRobot; on success it publishes the active robot list and sets the goal succeeded, and it aborts the goal otherwise. | upstream_code | stdr_server/src/stdr_server.cpp:545-566 |
| deleteRobot erases a robot only when the unload nodelet service returns success and reports that same boolean in the action result. | upstream_code | stdr_server/src/stdr_server.cpp:664-682 |
| The server advertises the latched stdr_msgs::RobotIndexedVectorMsg active robot list on the relative topic stdr_server/active_robots with queue size 10. | upstream_code | stdr_server/src/stdr_server.cpp:83-85 |
| stdr_msgs/RobotIndexedMsg carries the assigned robot name and the stdr_msgs/RobotMsg description. | upstream_code | stdr_msgs/msg/RobotIndexedMsg.msg:1-2 |
| stdr_msgs/RobotIndexedVectorMsg carries an array of stdr_msgs/RobotIndexedMsg entries. | upstream_code | stdr_msgs/msg/RobotIndexedVectorMsg.msg:1 |
| SpawnRobot.action defines a stdr_msgs/RobotMsg description goal and a RobotIndexedMsg indexedDescription plus string message result. | upstream_code | stdr_msgs/action/SpawnRobot.action:1-6 |
| DeleteRobot.action defines a string name goal and a bool success result. | upstream_code | stdr_msgs/action/DeleteRobot.action:1-5 |
| stdr_server advertises the load_static_map/load_static_map_external and add/delete source services and activates only the spawn, register and delete action servers; no pause, resume, reset or stop service or action is advertised. | upstream_code | stdr_server/src/stdr_server.cpp:58-140 |
| The robot nodelet advertises the relative <name>/replace MoveRobot service. | upstream_code | stdr_robot/src/stdr_robot.cpp:60-61 |
| Robot::moveRobotCallback rejects a colliding or unknown-occupancy pose and otherwise sets the current pose; it is not a stop. | upstream_code | stdr_robot/src/stdr_robot.cpp:194-209 |
| The upstream functional test drives the relative names stdr_server/spawn_robot, stdr_server/delete_robot and stdr_server/active_robots with SpawnRobotAction, DeleteRobotAction and RobotIndexedVectorMsg. | upstream_code | stdr_server/test/functional/interfaces_test.py:48-59 |
| The upstream functional test builds a RobotMsg with only footprint.radius and initialPose, spawns it, reads indexedDescription.name and checks the same entry on the active robot list. | upstream_code | stdr_server/test/functional/interfaces_test.py:83-114 |

## Scope and deployment

The package exposes the simulator's environment interface only:
`/stdr_server/spawn_robot` (actionlib `stdr_msgs/SpawnRobotAction`) and a
latched `/stdr_server/active_robots` observation of
`stdr_msgs/RobotIndexedVectorMsg`. The same latched list is the read-only
`robots` resource field so a caller can compare simulator state before and
after a spawn. `spawnRobotCallback` publishes the new list after a
successful spawn (`stdr_server/src/stdr_server.cpp:525-533`).

`/stdr_server/delete_robot` is described by the source facts but is not
bound. The server advertises no pause, resume, reset or stop service or
action (`stdr_server/src/stdr_server.cpp:58-140`), and the robot's only
advertised service, `<name>/replace`, sets a pose rather than stopping
anything (`stdr_robot/src/stdr_robot.cpp:60-61` and `stdr_robot/src/stdr_robot.cpp:194-209`). The RosDriver
bridge reports `safe_state.achieved=false` for an effectful command with no
stop binding, so every e-stop fails with
`MHS.SAFETY.SAFE_STATE_UNREACHED`; no fabricated safe-state action is
declared.

The spawn action is not started until the operator's node has a map: the
constructor activates the servers only when a map path is supplied as argv or
one of the load-map callbacks succeeds (`stdr_server/src/stdr_server.cpp:50-63` and `stdr_server/src/stdr_server.cpp:467-505`).
That precondition, the node/container namespace and the rosbridge endpoint are
deployment configuration, not package facts.

No robot velocity, physics step, pause, world reset, map load or sensor
capability is bound. The spawn goal accepts the complete `stdr_msgs/RobotMsg`
as an open object because the message has many optional nested sensor arrays;
the driver does not narrow or re-encode it.

## Fidelity contract

`driver.py` describes the fake actually deployed: engine
`analytic:ROS recording fake (no physics)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, no reset and no snapshot/restore.
The fake answers the declared spawn and active-robot endpoints, keeps a
placeholder robot registry and runs no STDR server, nodelet, map,
kinematics, collision, sensor or wall-clock loop. Its generated names and
descriptions are test data, not upstream state. The upstream 5.0 s
nodelet-registration wait is recorded as a source fact and is not timed or
exercised by the fake.

## Safety

The device is simulated at R0 and has no physical effect: spawn changes
only the operator's STDR process state, and the observation is a topic
read. No independent stop is claimed; the fake runs no physics and the
package binds no stop service. A missing map or a stopped `stdr_server` makes
an action time out as an unknown/failed ROS outcome rather than a fabricated
success.

## Tags

`ros`, `ros1`, `simulation`, `stdr`, `actionlib`, `spawn`, `delete`, `robots`
