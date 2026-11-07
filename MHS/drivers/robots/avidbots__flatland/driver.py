"""OpenMHS rosbridge driver for the Flatland 2-D simulator (gh.avidbots/flatland).

The upstream flatland_server is a C++ ROS 1 node.  This package is a
configuration-only RosDriver over rosbridge; it declares no Python native
class.  The scope is the simulator's ROS clock observation and its
acknowledged pause/resume services.  ``pause`` is the simulator's stop: it
stops the simulated world from stepping, and it is declared as an
input-free safe-state action and as the native e-stop binding.  It is not a
physical emergency stop and it does not command a robot velocity.

Every endpoint, type and fact cites the pinned clone at
fd636eea6c283d36eb662c36604daae45266eaf9.  The fake transport is ROS-free;
no ROS graph, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: Timekeeper publishes the simulation clock on the absolute /clock topic.
_CLOCK_REF = "flatland_server/src/timekeeper.cpp:53-54"

#: ServiceManager::Pause advertises the relative "pause" service; the type is
#: declared by the std_srvs/Empty include in the service manager header.
_PAUSE = {
    "service": "/pause",
    "type": "std_srvs/Empty",
    "source_name": "pause",
    "source_ref": "flatland_server/src/service_manager.cpp:63",
    "type_ref": "flatland_server/include/flatland_server/service_manager.h:53",
    "success": {"path": "$", "equals": {}},
}

#: ServiceManager::Resume advertises the relative "resume" service.
_RESUME = {
    "service": "/resume",
    "type": "std_srvs/Empty",
    "source_name": "resume",
    "source_ref": "flatland_server/src/service_manager.cpp:65",
    "type_ref": "flatland_server/include/flatland_server/service_manager.h:53",
    "success": {"path": "$", "equals": {}},
}

#: The simulated clock value is published as a rosgraph_msgs/Clock message.
_CLOCK_TIME = Field(
    "object",
    description="Simulated ROS clock sample: whole seconds and nanoseconds",
    properties={
        "secs": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)


class Flatland(RosDriver):
    device_id = "flatland"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeFlatland"}
    tags = ["ros", "ros1", "simulation", "flatland", "clock", "pause"]
    display_name = "Flatland 2-D simulator"
    vendor = "Avidbots"
    facts = [
        Fact("Timekeeper advertises rosgraph_msgs/Clock on the absolute /clock topic with queue size 1.",
             source="upstream_code", ref="flatland_server/src/timekeeper.cpp:53-54"),
        Fact("Timekeeper initializes simulated time to ros::Time(0, 0) and, on StepTime, advances it by "
             "max_step_size_ before publishing the clock.",
             source="upstream_code", ref="flatland_server/src/timekeeper.cpp:53-61"),
        Fact("ServiceManager registers the relative pause and resume services on its node handle.",
             source="upstream_code", ref="flatland_server/src/service_manager.cpp:63-65"),
        Fact("ServiceManager::Pause and ServiceManager::Resume take std_srvs/Empty requests, call "
             "World::Pause/World::Resume and return true.",
             source="upstream_code", ref="flatland_server/src/service_manager.cpp:150-159"),
        Fact("World::Pause sets service_paused_, World::Resume clears it, and World::IsPaused is also true "
             "while the internal marker manager is manipulating.",
             source="upstream_code", ref="flatland_server/src/world.cpp:333-340"),
        Fact("World::Update skips the before-physics plugin hook, the Box2D step and Timekeeper::StepTime "
             "while IsPaused is true; only int_marker_manager_.update() still runs.",
             source="upstream_code", ref="flatland_server/src/world.cpp:101-110"),
        Fact("The flatland_server node defaults update_rate to 200 Hz and step_size to 1/200 s, each overridable "
             "by a ROS parameter.", source="upstream_code",
             ref="flatland_server/src/flatland_server_node.cpp:89-93"),
        Fact("SimulationManager sets Timekeeper's maximum step size from step_size_ before the loop.",
             source="upstream_code", ref="flatland_server/src/simulation_manager.cpp:108"),
        Fact("The simulation loop sleeps for positive remaining expected-cycle time unless benchmarking.",
             source="upstream_code", ref="flatland_server/src/simulation_manager.cpp:139-155"),
    ]
    safe_state = ("Simulated physics is paused through the acknowledged pause service; simulated time and "
                  "the Box2D step stop advancing until the resume service is called.")
    #: The package only observes /clock and drives pause/resume; stepping, reset, snapshot and
    #: restore are out of scope.  The fake is a ROS-free recording, so it claims F0 and no dynamics.
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no physics step or pacing; placeholder clock "
                     "samples do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared /clock, /pause and /resume "
            "endpoints and runs no Flatland or Box2D physics, plugins, contacts, sensors or wall-clock loop",
            "the clock samples are placeholders and do not advance with the simulator's real time; a live run "
            "must receive /clock from the operator's flatland_server",
            "upstream update_rate 200 Hz and step_size 1/200 s are configurable ROS defaults, recorded only as "
            "source facts; this fake has no physics timestep or wall-clock pacing",
            "the package exposes no world step, reset, snapshot or restore; only the clock observation and the "
            "pause/resume services are in scope",
            "World::IsPaused is also true while the internal marker manager is manipulating, so a held clock "
            "sample alone does not prove that the pause service set the flag",
        ],
    }

    # /clock is non-latched and is not published while paused. Keep it an
    # explicit observation capability, not an automatic resource snapshot
    # that would wait during pause/resume commands.
    commands = {
        "x-cap.avidbots.clock.v1": {
            "topic": "/clock",
            "type": "rosgraph_msgs/Clock",
            "source_name": "/clock",
            "source_ref": _CLOCK_REF,
            "operation": "subscribe",
            "path": "clock",
            "result": {"map": {"sim_time": "output.$"}},
        },
        "x-cap.avidbots.pause.v1": dict(_PAUSE, result={"acknowledged": {"value": True}}),
        "x-cap.avidbots.resume.v1": dict(_RESUME, result={"acknowledged": {"value": True}}),
    }
    actions = {
        "x-cap.avidbots.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one simulated clock sample published by Flatland",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.avidbots.pause.v1": Action(
            name="pause",
            safe_state=True,
            description="Pause the simulated world with the acknowledged pause service",
            output={"acknowledged": Field("boolean",
                                          description="True once the pause service acknowledged the request")},
        ),
        "x-cap.avidbots.resume.v1": Action(
            name="resume",
            description="Resume the simulated world with the acknowledged resume service",
            output={"acknowledged": Field("boolean", description="True when the resume service acknowledged")},
        ),
    }
    # The upstream stop path for a simulated device: a pause service call.  The
    # runtime latches first; this only stops the simulated world from stepping.
    safety_bindings = {"estop": _PAUSE}
