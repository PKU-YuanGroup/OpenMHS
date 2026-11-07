"""OpenMHS rosbridge driver for the pinned warehouse_robot_simulation ROS 1 node.

The upstream repository is a C++ ROS 1 / Gazebo demonstration: a
``WarehouseSimulation`` node owns storages, dispatches, a single ``amr`` robot
object and an order queue.  Its only external ROS input is the relative
``warehouse/order/add`` subscription carrying ``std_msgs/String``.  The robot
thread drives the external ``move_base`` action client itself; the driver does
not proxy that action.

The order publication is the primary control.  A rosbridge publication returns
only transmission evidence.  The receipt also reports the string handed to
rosbridge (``sent_order``); that is the transmitted request, not a queue,
parse, motion or stop acknowledgement.

The e-stop is the companion gazebo_ros 2.8.7 service ``/gazebo/pause_physics``
(``World::SetPaused(true)``), confirmed only when ``/gazebo/get_physics_properties``
reads ``pause`` true.  No unpause and no re-enable are declared: a pending
``move_base`` goal and the last ``cmd_vel`` stored by ``gazebo_ros_diff_drive``
resume when the world steps again.  The fake transport is ROS-free; no ROS
graph, Gazebo process, robot or hardware is contacted.

Package facts cite the pinned clone at c8fe89a8501bfbcd97ffb0a0a4bef26e1abffc75.
Companion facts cite the lock clones named in task.json.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: WarehouseSimulation.cpp includes the String message used by the callback.
_ORDER_TYPE_REF = "src/WarehouseSimulation.cpp:13"

#: The relative subscriber name is the only external ROS input in the clone.
_ORDER_REF = "src/WarehouseSimulation.cpp:272"

#: OrderController::AddOrder parses the plain string and queues valid orders.
_ORDER_CALLBACK_REF = "src/OrderController.cpp:30-79"

#: Robot::Move builds a MoveBaseGoal and sends it through the action client.
_ROBOT_MOVE_REF = "src/Robot.cpp:102-132"

#: The node constructs the Robot with the robot name amr and action name move_base.
_ROBOT_CTOR_REF = "src/WarehouseSimulation.cpp:255"

#: The custom SIGINT handler sets isShutdown.
_SIGINT_REF = "src/WarehouseSimulation.cpp:35-42"

#: main calls ros::init with NoSigintHandler.
_INIT_REF = "src/WarehouseSimulation.cpp:223"

#: main registers the custom SIGINT handler.
_SIGNAL_REF = "src/WarehouseSimulation.cpp:274-275"

#: The shutdown path deletes spawned models and calls ros::shutdown.
_SHUTDOWN_REF = "src/WarehouseSimulation.cpp:283-310"

#: The main loop processes callbacks with ros::spinOnce at ros::Rate(10).
_LOOP_REF = "src/WarehouseSimulation.cpp:278-282"

#: The package builds one executable from the listed C++ sources.
_BUILD_REF = "CMakeLists.txt:210-211"

#: The launch starts map_server, amcl and the external move_base node.
_LAUNCH_REF = "launch/amcl.launch:4-59"

# -- Companion sources (task.json companions; user decision 2026-11-05) --
#: gazebo_ros 2.8.7 (ROS 1 Melodic) at 0667c5e5: the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_EMPTY = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
_DIFF = "companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp"
#: Gazebo classic 9.19.0 at e4400ae7: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

_ORDER_ID = "x-cap.rodriguesrenato.order.v1"

#: The e-stop: pause_physics (std_srvs/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _API + ":462-468",
    "type_ref": _API + ":464",
    "state_ref": _API + ":1662-1666",
    "description": "Pause the Gazebo world (gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 500,
}
#: The read-back that confirms it: get_physics_properties reports the paused flag.
_READBACK = {
    "service": "/gazebo/get_physics_properties",
    "type": "gazebo_msgs/GetPhysicsProperties",
    "source_name": "get_physics_properties",
    "source_ref": _API + ":364-370",
    "type_ref": _API + ":366",
    "state_ref": _API + ":1426",
    "description": "Read the world's paused flag back; the e-stop is confirmed only when pause is true",
    "request": {},
    "success": {"path": "pause", "equals": True},
    "timeout_ms": 500,
}

#: A message sent by rosbridge is not an upstream acknowledgement.
_ORDER = {
    "topic": "/warehouse/order/add",
    "type": "std_msgs/String",
    "operation": "publish",
    "source_name": "warehouse/order/add",
    "source_ref": _ORDER_REF,
    "type_ref": _ORDER_TYPE_REF,
    "message": {"data": ""},
    "args": {"data": {"from": "input.order"}},
    "result": {"map": {"submitted": "published", "confirmed": "confirmed"}},
}

_SUBMITTED = Field(
    "boolean",
    description="True when rosbridge accepted the String for publication on the topic",
)
_CONFIRMED = Field(
    "boolean",
    description="Always false: a rosbridge publication carries no queue, parse, motion or stop "
                "acknowledgement",
)
_SENT_ORDER = Field(
    "string",
    description="The order string handed to rosbridge (the transmitted request, not a measured queue "
                "or motion result)",
)


class _SentReceipt:
    """The order receipt also reports the string handed to rosbridge.

    The device resource reads no topic, so the receipt is where a caller sees
    what a publication sent.  It is the transmitted request, not a measurement.
    Every other call, the e-stop and the reset included, goes to the SDK bridge
    unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _ORDER_ID:
            return output
        output = dict(output)
        output["sent_order"] = str(dict(args or {})["order"])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class WarehouseRobotSimulation(RosDriver):
    device_id = "warehouse-robot-simulation"
    device_kind = "world.sim"
    mode = "simulated"
    # The order starts an autonomous mobile-base task in the simulated
    # warehouse.  The effect is confined to simulation, but the binding carries
    # the mobile-base hazard, so it is above the card's R0 floor.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeWarehouseRobotSimulation"}
    tags = ["ros", "ros1", "simulation", "gazebo", "warehouse", "order", "mobile-base"]
    display_name = "Warehouse robot simulation (ROS 1 / Gazebo)"
    vendor = "rodriguesrenato"
    model = "WarehouseSimulation with one amr robot"
    facts = [
        Fact("WarehouseSimulation.cpp includes std_msgs/String.h for the order callback.",
             source="upstream_code", ref=_ORDER_TYPE_REF),
        Fact("The WarehouseSimulation node subscribes to the relative topic warehouse/order/add with "
             "queue size 10 and registers OrderController::AddOrder as its callback.",
             source="upstream_code", ref=_ORDER_REF),
        Fact("The README states that the only way to interact externally with the simulation is to "
             "publish an Order message via ROS topic /warehouse/order/add.",
             source="vendor_doc", ref="README.md:92"),
        Fact("The README defines an Order as a one-line plain string with the pattern "
             "target_dispatch_model_name product product_quantity product_n product_n_quantity.",
             source="vendor_doc", ref="README.md:94"),
        Fact("The README states the project was built and was run on Ubuntu 18.04.5 LTS.",
             source="vendor_doc", ref="README.md:11"),
        Fact("The README lists ROS Melodic among the required dependencies.",
             source="vendor_doc", ref="README.md:16"),
        Fact("The README lists Gazebo 9.17.0 among the required dependencies.",
             source="vendor_doc", ref="README.md:17"),
        Fact("The README says to adjust the following apt-get commands to the ROS version, and the "
             "example commands name ros-noetic packages.",
             source="vendor_doc", ref="README.md:40-49"),
        Fact("OrderController::AddOrder parses the string, skips products with non-positive quantities, "
             "discards the whole order on any parse error, and otherwise appends the order to its queue "
             "when GetProductList().bucket_count() is greater than zero; it returns nothing to the sender.",
             source="upstream_code", ref=_ORDER_CALLBACK_REF),
        Fact("Robot::Move builds a move_base_msgs::MoveBaseGoal, sends it through an actionlib "
             "SimpleActionClient and calls waitForResult() without a timeout.",
             source="upstream_code", ref=_ROBOT_MOVE_REF),
        Fact("WarehouseSimulation constructs the Robot with robot name amr and action name move_base.",
             source="upstream_code", ref=_ROBOT_CTOR_REF),
        Fact("The shipped amcl.launch starts map_server, amcl and move_base, loads the navigation "
             "parameter files, and remaps odom and scan.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("The custom SIGINT handler sets the global isShutdown flag.",
             source="upstream_code", ref=_SIGINT_REF),
        Fact("main calls ros::init with the node name WarehouseSimulation and "
             "ros::init_options::NoSigintHandler.",
             source="upstream_code", ref=_INIT_REF),
        Fact("main calls signal(SIGINT, SigintHandler).",
             source="upstream_code", ref=_SIGNAL_REF),
        Fact("After the main loop ends, main deletes the spawned storages and dispatches and the products "
             "in the robots' cargo bins, sleeps 1 s and calls ros::shutdown.",
             source="upstream_code", ref=_SHUTDOWN_REF),
        Fact("The main loop calls ros::spinOnce and loop_rate.sleep() while ros::ok() is true and "
             "isShutdown is false, with ros::Rate(10).",
             source="upstream_code", ref=_LOOP_REF),
        Fact("The package builds one executable, WarehouseSimulation, from the listed C++ sources.",
             source="upstream_code", ref=_BUILD_REF),
        Fact("The README states that the simulation is ended by pressing CTRL+C in the terminal that "
             "runs the WarehouseSimulation node.",
             source="vendor_doc", ref="README.md:110"),
        Fact("world.launch includes $(find gazebo_ros)/launch/empty_world.launch and sets use_sim_time "
             "true, debug false, gui true and world_name.",
             source="upstream_code", ref="launch/world.launch:9-14"),
        Fact("warehouse.world sets the physics element type to ode.",
             source="upstream_code", ref="worlds/warehouse.world:67"),
        Fact("The delivery robot gazebo file loads the plugin libgazebo_ros_diff_drive.so and sets "
             "commandTopic to cmd_vel.",
             source="upstream_code", ref="models/urdf/delivery_robot.gazebo:121-130"),
        Fact("ModelController::GazeboDelete calls the service gazebo/delete_model.",
             source="upstream_code", ref="src/ModelController.cpp:103"),
        Fact("package.xml declares buildtool_depend catkin.",
             source="upstream_code", ref="package.xml:11"),
        Fact("package.xml declares build_depend gazebo_ros.",
             source="upstream_code", ref="package.xml:14"),
        Fact("The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless "
             "the arguments already name it.",
             source="upstream_code",
             ref="companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24"),
        Fact("empty_world.launch defaults its paused argument to false.",
             source="upstream_code", ref=_EMPTY + ":5"),
        Fact("empty_world.launch defaults its use_sim_time argument to true.",
             source="upstream_code", ref=_EMPTY + ":6"),
        Fact("empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, "
             "with the physics engine argument -e $(arg physics).",
             source="upstream_code", ref=_EMPTY + ":46-48"),
        Fact("empty_world.launch defaults its physics argument to ode.",
             source="upstream_code", ref=_EMPTY + ":15"),
        Fact("empty_world.launch defaults its gui argument to true.",
             source="upstream_code", ref=_EMPTY + ":8"),
        Fact("When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient.",
             source="upstream_code", ref=_EMPTY + ":51-54"),
        Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
             source="upstream_code", ref=_API + ":127-128"),
        Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics "
             "and services there.",
             source="upstream_code", ref=_API + ":147"),
        Fact("The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own "
             "callback queue gazebo_queue_.",
             source="upstream_code", ref=_API + ":462-468"),
        Fact("The API plugin advertises the service get_physics_properties with the "
             "gazebo_msgs::GetPhysicsProperties type on gazebo_queue_.",
             source="upstream_code", ref=_API + ":364-370"),
        Fact("gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the "
             "node handle is ok.",
             source="upstream_code", ref=_API + ":235-242"),
        Fact("pausePhysics calls world_->SetPaused(true) and returns true.",
             source="upstream_code", ref=_API + ":1662-1666"),
        Fact("unpausePhysics calls world_->SetPaused(false) and returns true.",
             source="upstream_code", ref=_API + ":1668-1672"),
        Fact("getPhysicsProperties sets res.pause to world_->IsPaused().",
             source="upstream_code", ref=_API + ":1426"),
        Fact("getPhysicsProperties sets success true only when the physics engine type is ode; for any "
             "other engine it sets success false and returns false.",
             source="upstream_code", ref=_API + ":1433-1465"),
        Fact("The GetPhysicsProperties response field pause is true if the physics engine is paused.",
             source="upstream_code",
             ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4"),
        Fact("Among the world-update begin hooks that its comment says apply forces and publish sim time "
             "on /clock, the API plugin connects publishSimTime.",
             source="upstream_code", ref=_API + ":224-227"),
        Fact("GazeboRosDiffDrive connects UpdateChild to the world-update begin event.",
             source="upstream_code", ref=_DIFF + ":174-175"),
        Fact("GazeboRosDiffDrive::UpdateChild calls getWheelVelocities.",
             source="upstream_code", ref=_DIFF + ":240-270"),
        Fact("GazeboRosDiffDrive::getWheelVelocities reads x_ and rot_.",
             source="upstream_code", ref=_DIFF + ":314-319"),
        Fact("GazeboRosDiffDrive::cmdVelCallback stores cmd_msg->linear.x in x_ and cmd_msg->angular.z in "
             "rot_.",
             source="upstream_code", ref=_DIFF + ":325-329"),
        Fact("GazeboRosDiffDrive::QueueThread calls queue_.callAvailable with ros::WallDuration(timeout).",
             source="upstream_code", ref=_DIFF + ":332-338"),
        Fact("World::Step advances simulation time and calls Update only when the world is not paused, a "
             "step increment is pending or a reset is due; otherwise it adds the step to the pause time.",
             source="upstream_code", ref=_WORLD + ":691-710"),
        Fact("While the world is paused and stepInc is greater than zero, World::Step calls Update and "
             "then decrements stepInc.",
             source="upstream_code", ref=_WORLD + ":691-702"),
        Fact("World::Step holds worldUpdateMutex while it steps the world.",
             source="upstream_code", ref=_WORLD + ":683"),
        Fact("World::SetPaused stores the paused flag under worldUpdateMutex.",
             source="upstream_code", ref=_WORLD + ":1428-1436"),
        Fact("World::IsPaused returns the stored paused flag.",
             source="upstream_code", ref=_WORLD + ":1422-1425"),
        Fact("World::Update fires the worldUpdateBegin event and then updates every model.",
             source="upstream_code", ref=_WORLD + ":776-782"),
        Fact("World::Step calls ProcessMessages after the paused or unpaused branch.",
             source="upstream_code", ref=_WORLD + ":691-718"),
        Fact("A WorldControl message with has_pause calls SetPaused, one with has_step calls OnStep, and "
             "one with has_multi_step calls SetPaused(true) and sets stepInc.",
             source="upstream_code", ref=_WORLD + ":1462-1477"),
        Fact("World::OnStep sets stepInc to 1.",
             source="upstream_code", ref=_WORLD + ":1364-1366"),
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true: it is the paused flag, not a "
        "measured standstill, and no unpause is offered, because a pending move_base goal and the last "
        "diff-drive cmd_vel resume on unpause and on a single-step or multi-step while pause stays true, "
        "including a pending stepInc, and during an outside-MHS unpause then CTRL+C, and the GUI can "
        "unpause or step without MHS watching the flag."
    )
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven rosbridge fake with no physics step, order execution, navigation, "
                     "wall-clock pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in: it records the order publication and answers "
            "the two companion Gazebo services; it runs no Gazebo physics, WarehouseSimulation node, order "
            "queue, move_base action or robot",
            "the order String is recorded and classified by a placeholder parser even while the paused flag "
            "is set; that classification is test data, and the receipt remains transmission-only "
            "(submitted, confirmed false, and the sent string)",
            "the pinned node publishes no status, order, robot or queue feedback topic; the package declares "
            "no reads, and the device resource does not subscribe to /clock, /scan, /odom or /cmd_vel",
            "the stop is the companion gazebo_ros world pause: /gazebo/pause_physics sets a paused flag and "
            "/gazebo/get_physics_properties reports it; the fake runs no Gazebo World::Step",
            "no unpause and no re-enable are offered (SAFE-042): on an unpause, Robot::Move's pending "
            "move_base goal (src/Robot.cpp:119-120, waitForResult with no timeout) and gazebo_ros_diff_drive's "
            "stored x_ and rot_ (companion gazebo_ros_diff_drive.cpp:325-329, applied from the world update "
            "at :270 and :314-319) resume, and a zero Twist does not cancel the goal because move_base "
            "publishes cmd_vel again; the operator recovers outside MHS by unpausing and then sending "
            "CTRL+C / SIGINT, and stored motion resumes during that unpause",
            "a single step, a multi-step, or a stepInc already pending runs while pause stays true: "
            "World::OnStep sets stepInc to 1 (companion World.cc:1364-1366), a WorldControl has_multi_step "
            "calls SetPaused(true) and sets stepInc (:1470-1476), and World::Step calls Update while "
            "IsPaused() is true when stepInc is greater than zero and then decrements stepInc (:691-702); "
            "that update applies the stored x_ and rot_, so stored motion can act without the "
            "get_physics_properties pause flag becoming false, and MHS does not clear a pending stepInc",
            "main calls ros::init with ros::init_options::NoSigintHandler (src/WarehouseSimulation.cpp:223) "
            "and then signal(SIGINT, SigintHandler) (:274-275); the handler only sets isShutdown "
            "(:35-42), and the loop (:278-282) does not observe that flag until ros::Rate(10).sleep() "
            "returns; world.launch sets use_sim_time true (:10) and publishSimTime is connected to the "
            "world update (companion gazebo_ros_api_plugin.cpp:224-227), so while the world is paused the "
            "loop does not parse orders and does not leave for the shutdown deletions until the world steps",
            "world.launch includes empty_world.launch with gui true and does not pass paused "
            "(launch/world.launch:9-14); empty_world.launch defaults paused to false and gui to true "
            "(companion empty_world.launch:5 and :8) and starts gzclient when gui is true (:51-54); any "
            "client, including that GUI, can unpause or step, and MHS does not watch the flag after the e-stop",
            "get_physics_properties returns success false for a non-ODE engine "
            "(companion gazebo_ros_api_plugin.cpp:1433-1465); warehouse.world sets physics type ode "
            "(worlds/warehouse.world:67), and a read-back that is not pause true leaves the e-stop "
            "unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.8.7 (Melodic) and Gazebo 9 the "
            "companion citations name; the README states Gazebo 9.17.0 (README.md:17) and the companion pin "
            "is Gazebo 9.19.0, the same major; the README's apt examples name ros-noetic packages after "
            "saying to adjust them (README.md:40-49); rosbridge cannot read those versions",
            "the external map_server, amcl and move_base nodes started by launch/amcl.launch are not "
            "declared endpoints of this package",
            "the node's ros::Rate(10) loop is a source fact, not this fake's timing",
            "mhs.safety.reset releases the latch only; the world stays paused and no unpause service is called",
            "AddOrder queues an order when GetProductList().bucket_count() is greater than zero, which is not "
            "an emptiness test for the unordered_map it returns (src/Order.h:20), so an order whose products "
            "were all skipped may still be queued",
            "after the loop ends, shutdown deletes spawned storages and dispatches and the products in the "
            "robots' cargo bins through gazebo/delete_model (src/ModelController.cpp:103) and then calls "
            "ros::shutdown (src/WarehouseSimulation.cpp:283-310); that path is not an MHS binding",
        ],
    }

    # The device resource reads no topic.  /clock, wheel odometry and laser scans are produced from the
    # world update, so they are silent while the e-stop holds the world paused.
    commands = {
        _ORDER_ID: _ORDER,
    }
    actions = {
        _ORDER_ID: Action(
            name="submit_order",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one std_msgs/String order on /warehouse/order/add. The receipt reports the "
                "string handed to rosbridge and is transmission evidence only: the upstream callback "
                "has no acknowledgement, and this action does not report queueing, robot motion, "
                "arrival or stopping."
            ),
            input={
                "order": Field(
                    "string",
                    description=(
                        "One-line warehouse order in the upstream pattern: "
                        "target_dispatch_model_name product product_quantity ...; it is sent "
                        "verbatim as the String data field."
                    ),
                ),
            },
            output={"submitted": _SUBMITTED, "confirmed": _CONFIRMED, "sent_order": _SENT_ORDER},
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back.  A failed pause or a read-back
    # other than pause true leaves the e-stop unconfirmed with the latch held.  No reset binding and no
    # re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
