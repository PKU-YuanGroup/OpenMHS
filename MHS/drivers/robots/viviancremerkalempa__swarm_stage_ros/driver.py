"""OpenMHS rosbridge driver for the swarm_stage_ros Stage environment.

The pinned repository is a C++ ROS 1 package that generates a Stage world and
a launch file for a swarm of mobile robots, then starts the external
``stage_ros/stageros`` node and the package's ``posctrl`` followers.  This is a
configuration-only :class:`RosDriver`: it declares no Python native class and
starts no ROS node, simulator or rosbridge connection.

The primary runtime control in the clone is the ``turtlesim/Pose`` target
publication that ``PositionController::subCallback`` consumes for one robot.
The generated launch starts ``posctrl`` for ``robot_0`` with that argument, so
this package binds the resolved ``/robot_0`` target topic.  The follower then
publishes ``geometry_msgs/Twist`` on its own ``/robot_0/cmd_vel`` topic.

There is no acknowledged stop: the clone registers no ROS service or action
for stopping, pausing or resetting the simulator, and the follower's loop has
no cancellation check.  A zero-Twist publication and the process-level
``killall stageros`` call are not acknowledged safe-state bindings.  The
package therefore declares no fabricated stop and reports the gap instead of
claiming a safe state.

Every endpoint, type and fact cites the pinned clone at
f365595f5fa947340f64bc8f017820846096661c.  The fake transport is ROS-free.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The generated launch starts posctrl with the node argument robot_0.
_TARGET_REF = "launch/controller.launch:7"

#: MainController builds /robot_<i> and advertises turtlesim::Pose on it.
_TARGET_TYPE_REF = "src/MainController.cpp:29-30"

#: The target publication consumed by PositionController::subCallback.
_TARGET = {
    "topic": "/robot_0",
    "type": "turtlesim/Pose",
    "source_name": "robot_0",
    "source_ref": _TARGET_REF,
    "type_ref": _TARGET_TYPE_REF,
    "operation": "publish",
    "message": {
        "x": 0.0,
        "y": 0.0,
        "theta": 0.0,
        "linear_velocity": 0.0,
        "angular_velocity": 0.0,
    },
    "args": {
        "x": {"from": "input.x"},
        "y": {"from": "input.y"},
    },
    "result": {"map": {"submitted": "published", "confirmed": "confirmed"}},
}

#: The clone derives target poses from runtime formation parameters and states
#: no numeric arena or pose bound, so the operator supplies the site envelope.
_LENGTH_LIMIT = Limit.operator_required(
    "the clone computes target poses from the runtime formation and robot-count parameters and states no "
    "numeric arena or pose bound; the operator supplies the site x/y envelope in site-limits.json"
)

_SUBMITTED = Field(
    "boolean",
    description="True when rosbridge accepted the turtlesim/Pose message for publication",
)
_CONFIRMED = Field(
    "boolean",
    description="Always false: the pinned controller sends no queue, motion or stop acknowledgement",
)


class SwarmStageRos(RosDriver):
    device_id = "swarm-stage-ros"
    device_kind = "world.sim"
    mode = "simulated"
    # The target starts an autonomous mobile-base position controller in the
    # Stage world.  The effect is simulated, but the binding carries the
    # mobile-base hazard, so it is above the card's R0 floor.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeSwarmStageRos"}
    tags = ["ros", "ros1", "simulation", "stage", "swarm", "mobile-base", "position-control"]
    display_name = "swarm_stage_ros Stage swarm environment"
    vendor = "viviancremerkalempa"
    model = "Stage swarm world with posctrl followers"
    facts = [
        Fact("README describes the package as a ROS package that automatically configures a swarm robot "
             "simulator and says the documented start command is roslaunch swarm_stage_ros "
             "swarm_stage.launch.", source="vendor_doc", ref="README.md:3-16"),
        Fact("README says that at the end of processing custom.world and controller.launch are generated, and "
             "that controller.launch starts the environment.", source="vendor_doc", ref="README.md:20-46"),
        Fact("The generated controller.launch starts the external stage_ros/stageros node with custom.world, "
             "one posctrl node per robot, and one controller node with argument 3 in the shipped file.",
             source="upstream_code", ref="launch/controller.launch:6-10"),
        Fact("The shipped swarm.yaml sets formation no, robots 3, position_controller yes, reference global "
             "and run yes; these are operator configuration values, not device bounds.",
             source="upstream_code", ref="yaml/swarm.yaml:1-17"),
        Fact("swarm_stage writes a controller.launch header that starts the ROS master and the stage_ros "
             "stageros node with launch/custom.world and respawn true.",
             source="upstream_code", ref="src/swarm_stage.cpp:66-71"),
        Fact("The shipped controller.launch starts stageros with respawn true.",
             source="upstream_code", ref="launch/controller.launch:6"),
        Fact("When the run parameter is yes, swarm_stage calls system(\" killall stageros\") and then "
             "system(\"roslaunch swarm_stage_ros controller.launch\").",
             source="upstream_code", ref="src/swarm_stage.cpp:421-425"),
        Fact("robot() writes one Stage model line per robot and, when position_controller is yes, writes a "
             "posctrl node with args=\"robot_<number>\".",
             source="upstream_code", ref="src/swarm_stage.cpp:709-712"),
        Fact("MainController::mainControl runs four loops of n/4 robots; each iteration advertises "
             "turtlesim::Pose on /robot_<i> with queue size 1000, sleeps 10 s and publishes that robot's target "
             "pose.",
             source="upstream_code", ref="src/MainController.cpp:28-51"),
        Fact("MainController::setPositions computes the target pose array from the requested robot count; it "
             "does not publish a feedback or stop topic.",
             source="upstream_code", ref="src/MainController.cpp:54-91"),
        Fact("PositionController::setTopics sets the subscription to /<nodeName> and the command publication "
             "to /<nodeName>/cmd_vel.",
             source="upstream_code", ref="src/PositionController.cpp:42-45"),
        Fact("PositionController::mainControl advertises geometry_msgs::Twist on topicPub_ and subscribes to "
             "topicSub_ with queue size 15000.",
             source="upstream_code", ref="src/PositionController.cpp:33-35"),
        Fact("PositionController::subCallback loops while the distance to the target is greater than 0.3 m, "
             "publishes Twist commands, and has no ROS cancellation, pause or stop check inside the loop.",
             source="upstream_code", ref="src/PositionController.cpp:54-75"),
        Fact("PositionController::subCallback reads only msg->x and msg->y and computes the heading with "
             "atan2(msg->y - feedback_.y, msg->x - feedback_.x); it never reads the Pose theta field.",
             source="upstream_code", ref="src/PositionController.cpp:56-57"),
        Fact("robotTransformed looks up the map to <node>/base_link transform and retries every second on a "
             "transform exception while ros::ok().",
             source="upstream_code", ref="src/PositionController.cpp:80-93"),
        Fact("posctrl takes argv[1] as the node name, initialises the ROS node with it and passes it to "
             "setTopics.",
             source="upstream_code", ref="src/posctrl.cpp:10-21"),
        Fact("The generated map include sets quit_time 3600 and paused 1 as static world properties.",
             source="upstream_code", ref="launch/include/map.inc:1-3"),
        Fact("CMakeLists builds the swarm_stage, controller and posctrl executables.",
             source="upstream_code", ref="CMakeLists.txt:204-219"),
    ]
    safe_state = (
        "No acknowledged ROS stop is declared: the clone registers no stop, pause or reset service or "
        "action, so the e-stop fails with the latch held, which only refuses this driver's publications; "
        "Stage keeps running and each posctrl follower keeps publishing Twist commands until it is within "
        "0.3 of its last target. A zero-Twist publication and killall stageros (respawned by the launch) "
        "are not safe-state evidence."
    )
    #: The deployed fake is an event-driven ROS recording transport, not the
    #: Stage simulator: it records the advertise/publish wire messages only.
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no Stage step, posctrl loop, TF lookup or state-hash "
                     "replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it records advertise and publish messages on "
            "/robot_0 and runs no Stage world, stageros, posctrl follower, TF listener or ROS graph",
            "only the /robot_0 target publication is bound; the generated launch also starts posctrl for "
            "robot_1 and robot_2 and the formation controller, which this package does not proxy",
            "the target publication returns only {published: true, confirmed: false}; it is transmission "
            "evidence, not proof that posctrl received the target, computed a command, moved the robot or "
            "stopped it",
            "no acknowledged stop, pause or reset service or action exists in the pinned clone; the "
            "simulator can only be killed by the process-level killall stageros call or by its static "
            "quit_time world property, neither of which is a ROS safe-state binding",
            "Stage's own topics (/odom, /base_scan, /base_pose_ground_truth, /clock) come from the external "
            "stage_ros package and are not declared or cited by this clone, so this package exposes no "
            "odometry, laser or clock observation",
            "the clone states no numeric arena or target-pose bound; x and y are operator_required and no "
            "site-limits.json is supplied here",
            "the Pose theta field is sent as 0.0 and is not an operator input because the follower computes "
            "its heading from the target x/y direction and never reads the message theta",
            "the built-in formation controller publishes only when the requested robot count is at least "
            "four (the four loops divide by four); the shipped robot count 3 therefore publishes no target, "
            "so an operator must publish the target or configure a count that the controller handles",
            "live ROS, rosbridge, stage_ros, catkin_make and hardware are not run or validated here",
        ],
    }

    commands = {
        "x-cap.viviancremerkalempa.target_pose.v1": _TARGET,
    }
    actions = {
        "x-cap.viviancremerkalempa.target_pose.v1": Action(
            name="publish_target_pose",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one turtlesim/Pose x/y target for robot_0 on /robot_0. The pinned follower ignores "
                "the message theta and computes its heading from the target direction. The receipt confirms "
                "only that rosbridge accepted the publication; the follower sends no arrival, motion or stop "
                "acknowledgement."
            ),
            input={
                "x": Field(
                    "number", unit="m",
                    description="Target x coordinate in the map frame",
                    limit=_LENGTH_LIMIT,
                ),
                "y": Field(
                    "number", unit="m",
                    description="Target y coordinate in the map frame",
                    limit=_LENGTH_LIMIT,
                ),
            },
            output={"submitted": _SUBMITTED, "confirmed": _CONFIRMED},
        ),
    }
    # The clone exposes no ROS service or action that could acknowledge a
    # stop.  A zero-Twist publication and the process-level killall stageros
    # call are not safe-state bindings, so no fabricated safety binding is
    # declared; the package reports the missing safe state instead.
    safety_bindings = {}
