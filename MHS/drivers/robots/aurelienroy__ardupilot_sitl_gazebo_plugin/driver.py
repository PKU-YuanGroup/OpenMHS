"""OpenMHS rosbridge driver for the ArduPilot SITL Gazebo plugin.

The pinned repository is a ROS 1 / Gazebo plugin library, not a standalone
ROS node.  The plugin is loaded into a Gazebo world and bridges that world to
an ArduPilot SITL process over the local UDP ports 9002 and 9003.  This
package is a configuration-only :class:`RosDriver` over rosbridge; it declares
no Python native class, does not launch Gazebo or ArduPilot, and neither
imports nor runs the upstream plugin.

The exposed ROS surface is the part the pinned plugin itself declares:

* an observation of ``/cessna/command/motor_speed``
  (``mav_msgs/CommandMotorSpeed``), the command array the plugin publishes
  after it receives a servo packet from SITL.  The plugin publishes on
  ``/<UAV_MODEL>/command/motor_speed``; only the LFLY Cessna world
  (``LFLY_world_cessna.launch``) sets ``UAV_MODEL`` to ``cessna``.  The iris
  launch files and ``empty_world_cessna.launch`` load worlds without
  ``UAV_MODEL``, where the plugin publishes ``/iris/command/motor_speed``, so
  this binding matches the LFLY Cessna deployment only.  The entries are the
  servo values times 1000; the Cessna aircraft plugin uses them as aileron,
  elevator, propeller (divided by 10), rudder and flap commands, not as rotor
  speeds;
* the acknowledged ``/fdmUDP/take_apm_lapseLock`` and
  ``/fdmUDP/release_apm_lapseLock`` services that pause and release the
  plugin's stepping loop.

The plugin runs Gazebo in lock-step: it pauses the world when it loads and
advances it only with ``Step(1)`` from its loop, after a servo packet.  The
lapse lock makes that loop skip receiving, stepping and sending, so while the
lock is held the world is not stepped.  The lock is a wall-time pause, not an
emergency stop.  The upstream header says it has no memory or identification
of the processes holding it and can resume the simulation before a holder has
finished; the loop clears it automatically when its timer elapses, and any
release that brings the shared holder count to zero clears it, including the
release of a holder whose own lock already expired and the plugin's own
parachute-insertion path.  The package binds the take service as the MHS
e-stop with a fixed maximum-float32 horizon so the timer does not expire in a
realistic deployment; the ordinary take action keeps the upstream method
default of 1 s.  The e-stop stops the plugin's stepping loop but not the
ArduPilot SITL process, and it is not independent of other ROS clients or of
a client that unpauses Gazebo.  This is stated in ``safe_state`` and is not a
hardware or independent stopped-state claim.

Review note (model review of wave C, not the author's text): with
``NB_SERVOS_MOTOR_SPEED`` 5 in the LFLY Cessna world, the upstream loops index
the fifth entry of a four-entry array at the pin (see the facts and gaps).

Every endpoint, type and fact cites the pinned clone at
75430fbc77967cd0a2e3c429a76b5787a9bff2d1.  The fake transport is ROS-free;
no ROS graph, Gazebo world, ArduPilot SITL process or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

_PLUGIN_HEADER = "ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h"
_ROS_SIDE = "ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp"
_GAZEBO_SIDE = "ardupilot_sitl_gazebo_plugin/src/apm_plugin_gazebo_side.cpp"
_MAIN = "ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp"
_APM_SIDE = "ardupilot_sitl_gazebo_plugin/src/apm_plugin_apm_side.cpp"
_TAKE_SRV = "ardupilot_sitl_gazebo_plugin/srv/TakeApmLapseLock.srv"
_RELEASE_SRV = "ardupilot_sitl_gazebo_plugin/srv/ReleaseApmLapseLock.srv"
_CESSNA_XACRO = "ardupilot_sitl_gazebo_plugin/urdf/aircraft_base.xacro"
_CESSNA_WORLD = "ardupilot_sitl_gazebo_plugin/worlds/LFLY_world_cessna/empty.world"
_PARACHUTE = "ardupilot_sitl_gazebo_plugin/src/apm_plugin_parachute.cpp"
_CESSNA_SPAWN = "ardupilot_sitl_gazebo_plugin/launch/cessna_spawn.launch"
_LFLY_LAUNCH = "ardupilot_sitl_gazebo_plugin/launch/LFLY_world_cessna.launch"
_EMPTY_CESSNA_LAUNCH = "ardupilot_sitl_gazebo_plugin/launch/empty_world_cessna.launch"
_EMPTY_CESSNA_WORLD = "ardupilot_sitl_gazebo_plugin/worlds/empty_world_cessna/empty.world"
_CESSNA_MODEL = "ardupilot_sitl_gazebo_plugin/urdf/cessna.xacro"
_RECORDER = "recorder_camera_plugin/src/recorder_camera_plugin.cpp"

#: The plugin advertises its services on a NodeHandle opened with the
#: "/fdmUDP" namespace; the relative service names resolve below it.
_FDM_NAMESPACE_REF = f"{_PLUGIN_HEADER}:93"
_NODE_HANDLE_REF = f"{_ROS_SIDE}:45"
_TAKE_ADVERTISE_REF = f"{_ROS_SIDE}:77"
_RELEASE_ADVERTISE_REF = f"{_ROS_SIDE}:78"
_TAKE_TYPE_REF = f"{_PLUGIN_HEADER}:72"
_RELEASE_TYPE_REF = f"{_PLUGIN_HEADER}:73"

#: The model name defaults to "iris" and is overridden by the SDF UAV_MODEL
#: element.  The LFLY Cessna world sets it to "cessna"; the Cessna aircraft
#: plugin subscribes to the same resolved topic name.
_MODEL_NAME_OVERRIDE_REF = f"{_GAZEBO_SIDE}:52-53"
_CESSNA_WORLD_REF = f"{_CESSNA_WORLD}:88"
_MOTOR_TOPIC_ADVERTISE_REF = f"{_ROS_SIDE}:73-74"
_MOTOR_TOPIC_SUBSCRIBE_REF = f"{_CESSNA_XACRO}:419"
_MOTOR_TYPE_REF = f"{_PLUGIN_HEADER}:52"
_MOTOR_PUBLISH_REF = f"{_ROS_SIDE}:267-275"

#: The upstream take_lapseLock default horizon, used for the fixed request of
#: the input-free pause action.  It is the method default, not a device safety
#: limit; the service itself accepts the caller's max_duration.
_LAPSE_DEFAULT_DEF_REF = f"{_PLUGIN_HEADER}:113"
_LAPSE_DEFAULT_ARG_REF = f"{_PLUGIN_HEADER}:146"

# ---------------------------------------------------------------------------
# Units and fixed requests
# ---------------------------------------------------------------------------

#: The service requests need an identifier; this is the client label this
#: driver presents, not an upstream fact.
_CLIENT_ID = "mhs-driver"

#: The fixed pause horizon in seconds.  The upstream take_lapseLock method
#: defaults to MAX_LAPSE_LOCK_DEFAULT (1 s, header:113 and header:146); the
#: service requires an explicit max_duration, so the driver's input-free pause
#: action supplies that upstream default rather than inventing a new bound.
_PAUSE_HORIZON_S = 1.0

#: The service response carries the resulting holder count.  A take succeeds
#: when at least the caller's own holder is registered; the upstream method
#: increments the counter, so the response is 1 or more.  The application
#: predicate is exact, and a deployment where another holder already owns the
#: lock returns a higher count and is reported as an application failure rather
#: than being mistaken for this driver's own pause.
_TAKE = {
    "service": "/fdmUDP/take_apm_lapseLock",
    "type": "ardupilot_sitl_gazebo_plugin/TakeApmLapseLock",
    "source_name": "take_apm_lapseLock",
    "source_ref": _TAKE_ADVERTISE_REF,
    "type_ref": _TAKE_TYPE_REF,
    "request": {"process_id": _CLIENT_ID, "max_duration": _PAUSE_HORIZON_S},
    "success": {"path": "nb_holders", "equals": 1},
    "result": {"map": {"nb_holders": "output.nb_holders"}},
}

#: release_lapseLock decrements the holder count and returns it.  It succeeds
#: only when this driver's release leaves zero holders; a positive count means
#: another holder remains and the loop is still paused, so this action reports
#: an application failure instead of claiming the loop is free.
_RELEASE = {
    "service": "/fdmUDP/release_apm_lapseLock",
    "type": "ardupilot_sitl_gazebo_plugin/ReleaseApmLapseLock",
    "source_name": "release_apm_lapseLock",
    "source_ref": _RELEASE_ADVERTISE_REF,
    "type_ref": _RELEASE_TYPE_REF,
    "request": {"process_id": _CLIENT_ID},
    "success": {"path": "nb_holders", "equals": 0},
    "result": {"map": {"nb_holders": "output.nb_holders"}},
}

#: The e-stop fixed request uses the maximum finite float32 value for the
#: declared float32 max_duration field (TakeApmLapseLock.srv:2).  The upstream
#: lock is a wall-time timer that the loop decrements; this horizon keeps the
#: plugin's stepping loop stopped in any realistic deployment instead of
#: expiring after the ordinary take action's 1 s default.  The request is a
#: driver choice, not a device safety limit.  It is not a persistent stop
#: against another ROS client: the upstream holder counter has no process
#: identity and an external release can clear the lock (header:296-307).
_ESTOP_TAKE = dict(
    _TAKE,
    request={"process_id": _CLIENT_ID, "max_duration": 3.4028234663852886e38},
)

#: No unit: the plugin publishes each servo value times 1000 and its comments
#: call that rad/s, but the Cessna aircraft plugin that consumes this topic
#: reads the entries as control-surface and propeller commands
#: (aircraft_plugin.cpp:140-148, 186-193).
_MOTOR_SPEED = Field(
    "array",
    description="mav_msgs/CommandMotorSpeed.motor_speed: SITL servo values times 1000, which the Cessna "
                "aircraft plugin reads as aileron, elevator, propeller (/10), rudder and flap commands",
    items=Field("number", description="One servo value times 1000 (5 for every entry when no servo exceeds 0.001)"),
)

_MOTOR_OBSERVATION = {
    "topic": "/cessna/command/motor_speed",
    "type": "mav_msgs/CommandMotorSpeed",
    "source_name": "/cessna/command/motor_speed",
    "source_ref": _MOTOR_TOPIC_SUBSCRIBE_REF,
    "type_ref": _MOTOR_TYPE_REF,
    "operation": "subscribe",
    "path": "motor_speed",
    "result": {"map": {"motor_speed": "output.$"}},
    "timeout_ms": 2000,
}


class ArdupilotSitlGazeboPlugin(RosDriver):
    """ROS 1 surface of the pinned ArduPilot SITL Gazebo plugin."""

    device_id = "ardupilot-sitl-gazebo"
    device_kind = "world.sim"
    mode = "simulated"
    #: The exposed surface only observes the APM-authored motor-speed command
    #: and pauses/releases the plugin loop.  It commands no vehicle motion; the
    #: card's risk floor is R0.
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeArdupilotSitlGazeboPlugin"}
    tags = ["ros", "ros1", "simulation", "gazebo", "ardupilot", "sitl", "motor-speed", "lapse-lock"]
    display_name = "ArduPilot SITL Gazebo plugin (ROS 1 surface)"
    vendor = "Aurelien Roy"
    model = "ArduPilot SITL Gazebo plugin"

    facts = [
        Fact("The plugin is a Gazebo WorldPlugin registered with GZ_REGISTER_WORLD_PLUGIN.",
             source="upstream_code", ref=f"{_MAIN}:57"),
        Fact("ROS_NAMESPACE is defined as /fdmUDP.",
             source="upstream_code", ref=f"{_FDM_NAMESPACE_REF}"),
        Fact("The plugin opens its ROS NodeHandle with ROS_NAMESPACE.",
             source="upstream_code", ref=f"{_NODE_HANDLE_REF}"),
        Fact("The plugin advertises the relative take_apm_lapseLock service on its /fdmUDP node handle.",
             source="upstream_code", ref=f"{_TAKE_ADVERTISE_REF}"),
        Fact("The plugin advertises the relative release_apm_lapseLock service on its /fdmUDP node handle.",
             source="upstream_code", ref=f"{_RELEASE_ADVERTISE_REF}"),
        Fact("The TakeApmLapseLock service request has a process_id string and a float32 max_duration; "
             "the response has an int32 nb_holders.",
             source="upstream_code", ref=f"{_TAKE_SRV}:1-4"),
        Fact("The ReleaseApmLapseLock service request has a process_id string; the response has an "
             "int32 nb_holders.",
             source="upstream_code", ref=f"{_RELEASE_SRV}:1-3"),
        Fact("The take service calls take_lapseLock(req.max_duration) and returns _nbHolders_lapseLock.",
             source="upstream_code", ref=f"{_ROS_SIDE}:89-95"),
        Fact("The release service calls release_lapseLock() and returns _nbHolders_lapseLock.",
             source="upstream_code", ref=f"{_ROS_SIDE}:99-105"),
        Fact("take_lapseLock sets the lock to the requested duration when it is longer than the current one "
             "and increments the holder counter.",
             source="upstream_code", ref=f"{_MAIN}:283-293"),
        Fact("release_lapseLock decrements the holder counter and clears the lock when no holders remain.",
             source="upstream_code", ref=f"{_MAIN}:300-316"),
        Fact("check_lapseLock subtracts loop_elapsed_dt from a held lock and, when the lock falls below zero, "
             "sets the lock and the holder count to zero and logs that the simulation resumes.",
             source="upstream_code", ref=f"{_MAIN}:326-345"),
        Fact("The loop passes check_lapseLock the loop duration measured with ros::WallTime.",
             source="upstream_code", ref=f"{_MAIN}:218-242"),
        Fact("While check_lapseLock returns false the loop continues to its next iteration; otherwise it calls "
             "receive_apm_input and, when a servo packet arrived, steps Gazebo unless _isSimPaused is set and "
             "sends the FDM state.",
             source="upstream_code", ref=f"{_MAIN}:241-262"),
        Fact("init_gazebo_side pauses the Gazebo world.",
             source="upstream_code", ref=f"{_GAZEBO_SIDE}:44-66"),
        Fact("step_gazebo_sim advances the world with Step(1); its comment says the simulation must be in pause "
             "mode for Step to work.",
             source="upstream_code", ref=f"{_GAZEBO_SIDE}:101-109"),
        Fact("on_gazebo_control toggles _isSimPaused on every world_control pause message and calls "
             "SetPaused(true) only when the toggle pauses.",
             source="upstream_code", ref=f"{_GAZEBO_SIDE}:136-157"),
        Fact("The Cessna spawn launch file includes gazebo_ros empty_world.launch with paused set to true.",
             source="upstream_code", ref=f"{_CESSNA_SPAWN}:53-54"),
        Fact("MAX_LAPSE_LOCK_ON_MODEL_INSERT is defined as 5 s.",
             source="upstream_code", ref=f"{_PLUGIN_HEADER}:112"),
        Fact("load_parachute_model inserts the parachute model and takes the lapse lock with "
             "MAX_LAPSE_LOCK_ON_MODEL_INSERT.",
             source="upstream_code", ref=f"{_PARACHUTE}:50-55"),
        Fact("on_parachute_model_loaded sets _loop_lapseLock to 0 without touching the holder count when the "
             "parachute model is not found.",
             source="upstream_code", ref=f"{_PARACHUTE}:70-75"),
        Fact("on_parachute_model_loaded calls release_lapseLock after attaching the parachute.",
             source="upstream_code", ref=f"{_PARACHUTE}:106-109"),
        Fact("receive_apm_input passes the parachute servo value to check_parachute_cmd.",
             source="upstream_code", ref=f"{_APM_SIDE}:141-142"),
        Fact("check_parachute_cmd returns for a servo value below 0.5 and otherwise loads the parachute model "
             "once.",
             source="upstream_code", ref=f"{_PARACHUTE}:22-33"),
        Fact("The recorder camera plugin's lapse-lock service clients target /fdmUDP/take_apm_lapseLock and "
             "/fdmUDP/release_apm_lapseLock.",
             source="upstream_code", ref=f"{_RECORDER}:134-136"),
        Fact("The recorder camera plugin's OnNewFrame, when it saves frames or video, calls its TakeApmLapseLock "
             "client with max_duration 5 before and its ReleaseApmLapseLock client after handling the frame.",
             source="upstream_code", ref=f"{_RECORDER}:181-240"),
        Fact("cessna.xacro leaves its recorder_camera instance inside a comment.",
             source="upstream_code", ref=f"{_CESSNA_MODEL}:10-24"),
        Fact("The header states the lapse lock has no memory or identification of holding processes, can "
             "resume before a holder has finished, and is a bounded wall-time pause.",
             source="upstream_code", ref=f"{_PLUGIN_HEADER}:285-310"),
        Fact("The model name defaults to iris.",
             source="upstream_code", ref=f"{_PLUGIN_HEADER}:85"),
        Fact("The plugin reads the SDF UAV_MODEL element into _modelName.",
             source="upstream_code", ref=f"{_MODEL_NAME_OVERRIDE_REF}"),
        Fact("The LFLY Cessna world sets UAV_MODEL to cessna.",
             source="upstream_code", ref=f"{_CESSNA_WORLD_REF}"),
        Fact("LFLY_world_cessna.launch includes cessna_spawn.launch with the LFLY Cessna world.",
             source="upstream_code", ref=f"{_LFLY_LAUNCH}:2-12"),
        Fact("empty_world_cessna.launch includes cessna_spawn.launch with the empty_world_cessna world.",
             source="upstream_code", ref=f"{_EMPTY_CESSNA_LAUNCH}:2-12"),
        Fact("The empty_world_cessna world loads the plugin without a UAV_MODEL element.",
             source="upstream_code", ref=f"{_EMPTY_CESSNA_WORLD}:182"),
        Fact("NB_SERVOS_MOTOR_SPEED is defined as 4, commented '4(iris) or 5(cessna)'.",
             source="upstream_code", ref=f"{_PLUGIN_HEADER}:104"),
        Fact("_cmd_motor_speed is declared with NB_SERVOS_MOTOR_SPEED entries and commented as the local copy "
             "of the motor speed command in rad/s; _modelName is the next member.",
             source="upstream_code", ref=f"{_PLUGIN_HEADER}:261-264"),
        Fact("The plugin reads the SDF NB_SERVOS_MOTOR_SPEED element into _nbMotorSpeed.",
             source="upstream_code", ref=f"{_GAZEBO_SIDE}:54-55"),
        Fact("The LFLY Cessna world sets NB_SERVOS_MOTOR_SPEED to 5.",
             source="upstream_code", ref=f"{_CESSNA_WORLD}:89"),
        Fact("The aircraft plugin stores motor_speed entries 0 to 4 as the aileron, elevator, propeller "
             "(divided by 10), rudder and flap commands.",
             source="upstream_code", ref="aircraft_plugin/src/aircraft_plugin.cpp:186-193"),
        Fact("The aircraft plugin's command indices are Aileron 0, Elevators 1, Propeller 2, Rudder 3 and Flap 4.",
             source="upstream_code", ref="aircraft_plugin/include/aircraft_plugin/aircraft_plugin.h:89-93"),
        Fact("UpdatePIDs turns the stored aileron, elevator and rudder commands into angles about the value 500, "
             "the flap command into an angle from 0 and the propeller command into a throttle of command / 1000.",
             source="upstream_code", ref="aircraft_plugin/src/aircraft_plugin.cpp:140-148"),
        Fact("The aircraft plugin connects OnUpdate to the world-update-begin event, and OnUpdate calls "
             "UpdatePIDs whenever simulation time has advanced.",
             source="upstream_code", ref="aircraft_plugin/src/aircraft_plugin.cpp:110-138"),
        Fact("The plugin advertises mav_msgs/CommandMotorSpeed on /<modelName>/command/motor_speed with "
             "queue size 10.",
             source="upstream_code", ref=f"{_MOTOR_TOPIC_ADVERTISE_REF}"),
        Fact("The Cessna aircraft plugin subscribes to the resolved /cessna/command/motor_speed topic.",
             source="upstream_code", ref=f"{_MOTOR_TOPIC_SUBSCRIBE_REF}"),
        Fact("The plugin includes the generated mav_msgs/CommandMotorSpeed header.",
             source="upstream_code", ref=f"{_MOTOR_TYPE_REF}"),
        Fact("The published CommandMotorSpeed sets frame_id to quad, stamps the current ROS time and fills "
             "motor_speed with the configured number of _cmd_motor_speed entries.",
             source="upstream_code", ref=f"{_MOTOR_PUBLISH_REF}"),
        Fact("receive_apm_input writes each of the first _nbMotorSpeed servo values times 1000 into "
             "_cmd_motor_speed and sets every entry to 5, commented as rad/s, when none exceeds 1.",
             source="upstream_code", ref=f"{_APM_SIDE}:126-138"),
        Fact("The servo packet comment states each servo value ranges from 0 (no rotation) to 1 (full "
             "throttle).",
             source="upstream_code", ref=f"{_PLUGIN_HEADER}:175-177"),
        Fact("The loop calls receive_apm_input only after check_lapseLock returns true.",
             source="upstream_code", ref=f"{_MAIN}:241-247"),
        Fact("receive_apm_input calls publish_commandMotorSpeed only after a complete servo packet is received.",
             source="upstream_code", ref=f"{_APM_SIDE}:116-144"),
        Fact("MAX_LAPSE_LOCK_DEFAULT is defined as 1 s.",
             source="upstream_code", ref=_LAPSE_DEFAULT_DEF_REF),
        Fact("take_lapseLock's default argument is MAX_LAPSE_LOCK_DEFAULT.",
             source="upstream_code", ref=_LAPSE_DEFAULT_ARG_REF),
        Fact("The repository LICENSE.md says the plugin is licensed under Apache v2.0 terms.",
             source="upstream_code", ref="LICENSE.md:1-6"),
        Fact("The plugin package.xml gives its licence as TODO.",
             source="upstream_code", ref="ardupilot_sitl_gazebo_plugin/package.xml:16"),
        Fact("SocketAPM.cpp carries a GNU GPL version 3 or later notice and names Socket.cpp of the ArduPilot "
             "project as its source.",
             source="upstream_code", ref="ardupilot_sitl_gazebo_plugin/src/SocketAPM.cpp:1-18"),
        Fact("The plugin library is built from the plugin sources including src/SocketAPM.cpp.",
             source="upstream_code", ref="ardupilot_sitl_gazebo_plugin/CMakeLists.txt:74-83"),
    ]

    safe_state = (
        "The acknowledged take_apm_lapseLock service holds the plugin's lapse lock with the maximum float32 "
        "horizon, so its loop stops exchanging SITL packets and stops stepping the Gazebo world it keeps paused: "
        "the aircraft is frozen while no client unpauses Gazebo. ArduPilot SITL keeps running, and any release "
        "that brings the shared holder count to zero resumes the loop, such as one by a holder whose own lock "
        "expired or by the parachute path."
    )

    fidelity = {
        "engine": "analytic:ROS-free recording fake for the ArduPilot SITL Gazebo ROS surface (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no Gazebo step, ArduPilot SITL process, UDP socket or "
                     "wall-clock pacing; placeholder motor speeds do not establish a trajectory or state hash",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge handler: it answers the declared subscription and services and "
            "records the outbound requests, but it runs no Gazebo world, ArduPilot SITL, UDP bridge, physics "
            "step, sensor plugin or wall-clock loop",
            "the plugin's 2.5 ms SITL step (STEP_SIZE_FOR_ARDUPILOT) and its loop rates are source facts, not "
            "the fake's timing; the fake has no timestep or pacing",
            "the fake keeps its placeholder lapse lock held until the release service or a test resets it; it "
            "does not run the upstream elapsed-wall-time expiry in check_lapseLock",
            "the fake publishes a placeholder motor-speed array only in reply to a subscription; the real "
            "plugin publishes only after receiving a SITL servo packet, so a live deployment needs the "
            "operator's Gazebo world, ArduPilot SITL and rosbridge",
            "the fake does not model UDP servo packets, FDM replies, Gazebo stepping, sensors, the parachute "
            "path, rotor dynamics or the aircraft_plugin consumers",
            "the fake does not model the upstream holder-counter bug or an early resume; a live holder-count "
            "race remains unverified",
            "review: the frozen world depends on Gazebo staying paused between the plugin's Step(1) calls; the "
            "clone does not stop another client (the Gazebo GUI, a gazebo_ros pause/unpause caller) from "
            "unpausing it, and in a running world the aircraft plugin keeps applying the last stored command "
            "at every world update while the lock withholds new SITL commands",
            "review: the lock is cleared by any release that brings the shared holder count to zero, including "
            "a holder whose own lock already expired (expiry zeroes the count), the plugin's parachute path "
            "(a 5 s take released after the model loads) and the recorder camera plugin when it saves frames; "
            "a failed parachute load zeroes the lock directly without changing the count",
            "review: the take is not idempotent (every call adds a holder) and the e-stop and the take action "
            "succeed only when nb_holders is exactly 1 (the binding grammar has no lower-bound test); a reviewer "
            "probe showed one take for an idle e-stop and none on reset, but a second e-stop while latched, an "
            "e-stop within 1 s of an ordinary take, another holder or a lost take response make the e-stop "
            "report SAFE_STATE_UNREACHED although the loop is paused, and every background retry of the SDK "
            "then takes the lock again until a reset, so resuming needs one release per take",
            "review: the binding matches only the LFLY_world_cessna.launch deployment; the iris launch files "
            "and empty_world_cessna.launch load worlds without UAV_MODEL, where the plugin publishes "
            "/iris/command/motor_speed (and in empty_world_cessna the Cessna listens on "
            "/cessna/command/motor_speed, so it receives no commands)",
            "review: upstream defect at the pin: the LFLY Cessna world sets NB_SERVOS_MOTOR_SPEED to 5, but "
            "_cmd_motor_speed has 4 entries, so receive_apm_input and publish_commandMotorSpeed write and read "
            "a fifth entry past the array (undefined behaviour; _modelName is the next member); the fifth "
            "published value, the Cessna flap command, is not trustworthy",
            "review: the motor_speed entries are servo values times 1000; the upstream comments call them "
            "rad/s, but the Cessna aircraft plugin reads them as control-surface and propeller commands, so "
            "the output declares no unit",
        ],
    }

    commands = {
        "x-cap.aurelienroy.motor_speed.v1": _MOTOR_OBSERVATION,
        "x-cap.aurelienroy.take_lapse_lock.v1": _TAKE,
        "x-cap.aurelienroy.release_lapse_lock.v1": _RELEASE,
    }

    actions = {
        "x-cap.aurelienroy.motor_speed.v1": Action(
            name="observe_motor_speed",
            verb="read",
            description="Read the latest motor-speed command the plugin published after a SITL servo packet; "
                        "the read makes a fresh subscription and never returns a cached sample",
            output={"motor_speed": _MOTOR_SPEED},
        ),
        "x-cap.aurelienroy.take_lapse_lock.v1": Action(
            name="take_lapse_lock",
            description="Take the plugin's bounded wall-time lapse lock with the upstream method default "
                        "horizon of 1 s; this pauses the plugin loop that steps the paused Gazebo world and "
                        "exchanges packets with ArduPilot SITL, not ArduPilot itself, and the plugin clears "
                        "the lock automatically when the timer expires",
            output={"nb_holders": Field("integer",
                                        description="Holder count returned by TakeApmLapseLock.nb_holders")},
        ),
        "x-cap.aurelienroy.release_lapse_lock.v1": Action(
            name="release_lapse_lock",
            description="Release this driver's lapse lock; succeeds only when the returned holder count is "
                        "zero, because a positive count means another holder still pauses the loop",
            output={"nb_holders": Field("integer",
                                        description="Holder count returned by ReleaseApmLapseLock.nb_holders")},
        ),
    }

    #: The only native pause is the lapse lock.  The e-stop uses a fixed
    #: maximum-float32 horizon so its wall-time timer does not expire in a
    #: realistic deployment; the ordinary take action keeps the upstream 1 s
    #: default.  The header states the lock has no process identity and another
    #: client's release can resume the loop (header:285-310); this is disclosed
    #: in safe_state and is not an independent-stop claim.
    safety_bindings = {"estop": _ESTOP_TAKE}
