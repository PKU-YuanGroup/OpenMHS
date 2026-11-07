"""OpenMHS rosbridge driver for the STDR 2-D multi-robot simulator.

The upstream package is a ROS 1 simulator: ``stdr_server`` is a C++ node that
owns the robot registry and exposes actionlib servers for spawning and
deleting robots, and a latched ``stdr_msgs/RobotIndexedVectorMsg`` list of the
active robots.  This package is a configuration-only ``RosDriver`` over
rosbridge; it declares no Python native class and does not start ROS, a
world, a robot nodelet or the operator's simulator.

The scope is the simulator's environment interface: spawn a robot from a
``stdr_msgs/RobotMsg`` description and observe the active robot list.  The
upstream server starts its action servers only after it has a map (a launch
argument or one of the load-map services); the operator runs that server and
rosbridge separately.  Nothing here commands a robot velocity, steps physics,
resets the world or contacts hardware.

The upstream ``/stdr_server/delete_robot`` action is not bound: the server
advertises no pause, resume, reset or stop service/action, so an in-flight
spawn or delete goal has no acknowledged stop for the RosDriver e-stop
contract.  That missing stop is recorded as the package blocker, not hidden
behind a fabricated safe-state action.

Every endpoint, type and fact cites the pinned clone at
1bcdec7b79c9e4a2960f7fcf9c150c67485ecab4.  The fake transport is ROS-free;
no ROS graph, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: Server::Server constructs the spawn action server on the public node handle
#: with the relative name "stdr_server/spawn_robot" (it resolves under the
#: stdr_server node name to /stdr_server/spawn_robot).
_SPAWN_REF = "stdr_server/src/stdr_server.cpp:31"

#: stdr_server.h aliases SpawnRobotServer to an actionlib SimpleActionServer
#: over stdr_msgs::SpawnRobotAction, which proves the ROS 1 action type.
_SPAWN_TYPE_REF = "stdr_server/include/stdr_server/stdr_server.h:70-71"

#: The server advertises the relative latched active-robot list
#: "stdr_server/active_robots" as stdr_msgs::RobotIndexedVectorMsg.
_ACTIVE_REF = "stdr_server/src/stdr_server.cpp:83-85"
_ACTIVE_TYPE_REF = "stdr_server/include/stdr_server/stdr_server.h:38"

#: The observation returns the whole RobotIndexedVectorMsg.robots array.  The
#: element shape is stdr_msgs/RobotIndexedMsg {name, robot}.
_ROBOTS = Field(
    "array",
    description="Active robots as stdr_msgs/RobotIndexedMsg entries (name and RobotMsg)",
    items=Field("object", description="One stdr_msgs/RobotIndexedMsg: name string and robot RobotMsg"),
)

#: A spawn goal carries one stdr_msgs/RobotMsg.  The schema is intentionally
#: open because the upstream message has many optional sensor arrays; the
#: operator supplies the complete message object exactly as ROS would encode it.
_DESCRIPTION = Field(
    "object",
    description="Complete stdr_msgs/RobotMsg robot description (initialPose, footprint, sensors, kinematicModel)",
)

#: SpawnRobotResult has no boolean success field.  The callback leaves message
#: empty on success (setSucceeded) and fills it on every abort path
#: (stdr_server.cpp:517 and 647-648), so the empty message is the application
#: success predicate in addition to the actionlib SUCCEEDED terminal status.
_SPAWN = {
    "action": "/stdr_server/spawn_robot",
    "type": "stdr_msgs/SpawnRobotAction",
    "profile": "ros1-actionlib",
    "source_name": "stdr_server/spawn_robot",
    "source_ref": _SPAWN_REF,
    "type_ref": _SPAWN_TYPE_REF,
    "args": {"description": {"from": "input.description"}},
    "result": {"map": {"name": "indexedDescription.name",
                       "robot": "indexedDescription.robot"}},
    "success": {"path": "message", "equals": ""},
}

#: The active-robot list is a latched topic observation, not a resource
#: snapshot: each read opens a fresh subscription and waits for one sample.
_ACTIVE = {
    "topic": "/stdr_server/active_robots",
    "type": "stdr_msgs/RobotIndexedVectorMsg",
    "source_name": "stdr_server/active_robots",
    "source_ref": _ACTIVE_REF,
    "type_ref": _ACTIVE_TYPE_REF,
    "operation": "subscribe",
    "path": "robots",
    "result": {"map": {"robots": "output.$"}},
}


class StdrSimulator(RosDriver):
    device_id = "stdr-simulator"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeStdrSimulator"}
    tags = ["ros", "ros1", "simulation", "stdr", "actionlib", "spawn", "delete", "robots"]
    display_name = "STDR 2-D multi-robot simulator"
    vendor = "stdr-simulator-ros-pkg"
    facts = [
        Fact("Server::Server constructs the spawn and delete action servers on the public node handle "
             "with the relative names stdr_server/spawn_robot and stdr_server/delete_robot.",
             source="upstream_code", ref="stdr_server/src/stdr_server.cpp:31-38"),
        Fact("stdr_server.h includes the generated stdr_msgs/SpawnRobotAction and "
             "stdr_msgs/DeleteRobotAction headers.",
             source="upstream_code", ref="stdr_server/include/stdr_server/stdr_server.h:35-36"),
        Fact("stdr_server.h aliases SpawnRobotServer and DeleteRobotServer to "
             "actionlib::SimpleActionServer over stdr_msgs::SpawnRobotAction and "
             "stdr_msgs::DeleteRobotAction.",
             source="upstream_code", ref="stdr_server/include/stdr_server/stdr_server.h:70-77"),
        Fact("activateActionServers starts the spawn, register and delete action servers.",
             source="upstream_code", ref="stdr_server/src/stdr_server.cpp:601-605"),
        Fact("The constructor starts the action servers only when it receives a map path as argv, or after "
             "load_static_map/load_static_map_external constructs a MapServer; without a map it skips "
             "activation.", source="upstream_code", ref="stdr_server/src/stdr_server.cpp:50-63"),
        Fact("spawnRobotCallback aborts a goal whose sensor frame_id values repeat, otherwise calls "
             "addNewRobot; on success it sets the goal succeeded and publishes the active robot list.",
             source="upstream_code", ref="stdr_server/src/stdr_server.cpp:514-537"),
        Fact("addNewRobot defaults an empty kinematicModel.type to ideal, assigns the name robot<N> from a "
             "monotonically increasing server counter, loads a stdr_robot/Robot nodelet, and waits up to "
             "5.0 s for the robot to register.", source="upstream_code",
             ref="stdr_server/src/stdr_server.cpp:621-638"),
        Fact("addNewRobot returns a nonempty message when the robot does not register within the 5.0 s wait; "
             "spawnRobotCallback then aborts the goal.", source="upstream_code",
             ref="stdr_server/src/stdr_server.cpp:636-650"),
        Fact("deleteRobotCallback calls deleteRobot; on success it publishes the active robot list and sets "
             "the goal succeeded, and it aborts the goal otherwise.", source="upstream_code",
             ref="stdr_server/src/stdr_server.cpp:545-566"),
        Fact("deleteRobot erases a robot only when the unload nodelet service returns success and reports that "
             "same boolean in the action result.", source="upstream_code",
             ref="stdr_server/src/stdr_server.cpp:664-682"),
        Fact("The server advertises the latched stdr_msgs::RobotIndexedVectorMsg active robot list on the "
             "relative topic stdr_server/active_robots with queue size 10.",
             source="upstream_code", ref="stdr_server/src/stdr_server.cpp:83-85"),
        Fact("stdr_msgs/RobotIndexedMsg carries the assigned robot name and the stdr_msgs/RobotMsg "
             "description.", source="upstream_code", ref="stdr_msgs/msg/RobotIndexedMsg.msg:1-2"),
        Fact("stdr_msgs/RobotIndexedVectorMsg carries an array of stdr_msgs/RobotIndexedMsg entries.",
             source="upstream_code", ref="stdr_msgs/msg/RobotIndexedVectorMsg.msg:1"),
        Fact("SpawnRobot.action defines a stdr_msgs/RobotMsg description goal and a RobotIndexedMsg "
             "indexedDescription plus string message result.", source="upstream_code",
             ref="stdr_msgs/action/SpawnRobot.action:1-6"),
        Fact("DeleteRobot.action defines a string name goal and a bool success result.",
             source="upstream_code", ref="stdr_msgs/action/DeleteRobot.action:1-5"),
        Fact("The upstream functional test drives the relative names stdr_server/spawn_robot, "
             "stdr_server/delete_robot and stdr_server/active_robots with SpawnRobotAction, "
             "DeleteRobotAction and RobotIndexedVectorMsg.", source="upstream_code",
             ref="stdr_server/test/functional/interfaces_test.py:48-59"),
        Fact("stdr_server advertises the load_static_map/load_static_map_external and add/delete source "
             "services and activates only the spawn, register and delete action servers; no pause, resume, "
             "reset or stop service or action is advertised.", source="upstream_code",
             ref="stdr_server/src/stdr_server.cpp:58-140"),
        Fact("The robot nodelet advertises the relative <name>/replace MoveRobot service.",
             source="upstream_code", ref="stdr_robot/src/stdr_robot.cpp:60-61"),
        Fact("Robot::moveRobotCallback rejects a colliding or unknown-occupancy pose and otherwise sets the "
             "current pose; it is not a stop.", source="upstream_code",
             ref="stdr_robot/src/stdr_robot.cpp:194-209"),
        Fact("The upstream functional test builds a RobotMsg with only footprint.radius and initialPose, "
             "spawns it, reads indexedDescription.name and checks the same entry on the active robot list.",
             source="upstream_code", ref="stdr_server/test/functional/interfaces_test.py:83-114"),
    ]
    #: The fake is a ROS-free recording stand-in for the actionlib traffic.
    #: It runs no STDR world, nodelet, map, physics, sensors or collision.
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned action/server replies; placeholder robot names and descriptions "
                     "do not establish world state, trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared spawn and active_robots "
            "endpoints and runs no stdr_server, nodelet manager, map, robot, sensor, kinematics, collision "
            "or physics loop",
            "the fake maintains a placeholder robot registry whose names and entries are test data; a live "
            "run must reach the operator's stdr_server with a loaded map",
            "the upstream action servers start only after a map is supplied or one of the load-map services "
            "succeeds; the fake does not model that precondition",
            "the upstream spawn waits up to 5.0 s for the robot nodelet to register; the fake answers "
            "immediately and performs no nodelet lifecycle action",
            "the package exposes no step, pause, reset, map load, velocity or sensor capability beyond the "
            "active robot list; delete_robot is also unbound because the server advertises no acknowledged "
            "stop for the actions",
        ],
    }

    #: The registered robot list is the simulator's observable environment
    #: state.  It is a read-only resource field bound to the same latched
    #: topic; a spawn therefore changes a resource state hash, and callers
    #: can also read it through the explicit observation capability.
    parameters = {"robots": _ROBOTS}
    reads = {
        "robots": {
            "topic": "/stdr_server/active_robots",
            "type": "stdr_msgs/RobotIndexedVectorMsg",
            "source_name": "stdr_server/active_robots",
            "source_ref": _ACTIVE_REF,
            "type_ref": _ACTIVE_TYPE_REF,
            "operation": "subscribe",
            "path": "robots",
        },
    }
    commands = {
        "x-cap.stdr-simulator-ros-pkg.active-robots.v1": dict(_ACTIVE),
        "x-cap.stdr-simulator-ros-pkg.spawn-robot.v1": dict(_SPAWN),
    }
    actions = {
        "x-cap.stdr-simulator-ros-pkg.active-robots.v1": Action(
            name="read_active_robots",
            verb="read",
            description="Read one latched active-robot list sample from stdr_server",
            output={"robots": _ROBOTS},
        ),
        "x-cap.stdr-simulator-ros-pkg.spawn-robot.v1": Action(
            name="spawn_robot",
            description="Spawn a robot into the STDR simulator from a stdr_msgs/RobotMsg description",
            input={"description": _DESCRIPTION},
            output={
                "name": Field("string", description="Assigned robot name (robot<N>)"),
                "robot": Field("object", description="Echoed stdr_msgs/RobotMsg description assigned to the robot"),
            },
        ),
    }
