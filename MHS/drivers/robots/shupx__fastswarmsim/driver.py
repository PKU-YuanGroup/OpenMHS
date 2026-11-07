"""OpenMHS rosbridge driver for the FastSwarmSim time coordinator (gh.shupx/fastswarmsim).

FastSwarmSim is a ROS 2 PX4 multi-rotor simulator.  This package is a
configuration-only :class:`RosDriver` over rosbridge for the simulation-time
environment control exposed by the ``fss_time`` coordinator: the ``/clock``
publication, the ``fss/sim_clock_status`` observation and the acknowledged
``fss/clock_control`` service.  It declares no Python native class, imports no
ROS and starts no coordinator.

``pause`` stops a root coordinator from advancing the shared simulation clock;
it is the simulator's stop and an input-free safe-state action, not a physical
emergency stop.  A child coordinator (``fss_time_parent_coordinator_endpoint``
set) keeps advancing on its parent's grants, and any client of
``fss/clock_control`` (the coordinator UI that the default launch starts) can
resume the clock.  The PX4/MAVROS vehicle interface, LiDAR rendering and RViz
visualisation are outside this package (see ``facts.md`` and RESULT notes).

Every endpoint, type and fact cites the pinned clone at
56a6380fcd409a0700baedc39a632a823622d633.  The fake transport is ROS-free and
contacts no ROS graph or simulator.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The coordinator publishes its simulated clock on the absolute /clock topic.
_CLOCK_REF = "src/fss_time/src/time_coordinator.cpp:181-183"

#: The coordinator publishes the detailed status on a relative topic.
_STATUS_REF = "src/fss_time/src/time_coordinator.cpp:185-186"
_STATUS_TYPE_REF = "src/fss_time/include/fss_time/time_coordinator.hpp:18"

#: The relative control service and its callback.
_CONTROL_REF = "src/fss_time/src/time_coordinator.cpp:187-196"
_CONTROL_TYPE_REF = "src/fss_time/include/fss_time/time_coordinator.hpp:19"

#: The callback always applies both request fields, in this order, and always
#: answers success=true.  A pause therefore also sets max_real_time_factor;
#: this driver uses the documented 0.0 "disable the periodic regulator" value
#: while stopped and requires the operator to choose the resume factor.
_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/msg/Clock",
    "source_name": "/clock",
    "source_ref": _CLOCK_REF,
    "operation": "subscribe",
    "path": "clock",
    "result": {"map": {"sim_time": "output.$"}},
}

_STATUS = {
    "topic": "/fss/sim_clock_status",
    "type": "fss_time_interfaces/msg/SimClockStatus",
    "source_name": "fss/sim_clock_status",
    "source_ref": _STATUS_REF,
    "type_ref": _STATUS_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"status": "output.$"}},
}

#: The same continuous status topic is also the resource snapshot.  It keeps
#: publishing while the clock is paused, so it is not a silent-topic snapshot;
#: the explicit clock/status capabilities remain the primary observations.
_STATUS_READ = {
    "topic": "/fss/sim_clock_status",
    "type": "fss_time_interfaces/msg/SimClockStatus",
    "source_name": "fss/sim_clock_status",
    "source_ref": _STATUS_REF,
    "type_ref": _STATUS_TYPE_REF,
    "operation": "subscribe",
}

_CONTROL = {
    "service": "/fss/clock_control",
    "type": "fss_time_interfaces/srv/SimClockControl",
    "source_name": "fss/clock_control",
    "source_ref": _CONTROL_REF,
    "type_ref": _CONTROL_TYPE_REF,
    "success": {"path": "success", "equals": True},
}

#: The upstream README documents 0.0 as disabling periodic regulator
#: requests; this is the value the input-free pause request sends while the
#: coordinator is stopped (src/fss_time/README.md:221).
_PAUSE = dict(
    _CONTROL,
    request={"running": False, "max_real_time_factor": 0.0},
    result={"acknowledged": {"value": True}},
)

_RESUME = dict(
    _CONTROL,
    request={"running": True, "max_real_time_factor": 0.0},
    args={"max_real_time_factor": {"from": "input.max_real_time_factor"}},
    result={"acknowledged": {"value": True}},
)

#: The clone states no numeric envelope for the service request: the README
#: names 1.0 as the launch default and 2.0/1000.0 only as examples, and a
#: deployment may configure another factor.  The operator supplies the site
#: envelope; until then every resume is refused.
_SPEED_LIMIT = Limit.operator_required(
    "the coordinator applies max_real_time_factor as the simulation-time to wall-time ratio, but the clone "
    "states no numeric minimum or maximum for the fss/clock_control request and the launch value is a "
    "configured default, not a device bound; the operator supplies the site factor envelope for resume"
)

_CLOCK_TIME = Field(
    "object",
    description="Simulated ROS clock sample",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)

_STATUS_OUTPUT = {
    "status": Field(
        "object",
        description="Coordinator status sample",
        properties={
            "sim_time": _CLOCK_TIME,
            "running": Field("boolean", description="Coordinator flag that gates clock advancement"),
            "max_real_time_factor": Field("number", unit="1",
                                          description="Configured simulation-time to wall-time ratio"),
            "observed_real_time_factor": Field("number", unit="1",
                                               description="Observed simulation-time to wall-time ratio"),
            "participant_count": Field("integer", unit="1",
                                       description="Registered ZeroMQ time participants"),
            "new_request_participant_count": Field(
                "integer", unit="1",
                description="Participants with an unserved safe-time request"),
            "regulator_active": Field(
                "boolean",
                description="True while the coordinator is running with a positive factor"),
            "debug_msg": Field("string", description="Coordinator debug-state message"),
            "speed_regulator_step_ns": Field("integer", unit="ns",
                                             description="Configured regulator step in nanoseconds"),
            "min_operation_walltime": Field("integer", unit="ns",
                                            description="Coordinator minimum operation wall time in nanoseconds"),
        },
    ),
}

_ACK = {"acknowledged": Field("boolean",
                              description="True once the clock_control service acknowledged the request")}


class FastSwarmSim(RosDriver):
    device_id = "fastswarmsim"
    device_kind = "world.sim"
    mode = "simulated"
    #: Only the shared simulation clock is controlled: pause, resume and speed.
    #: SAFE-006 classifies isolated simulation stepping as R0; vehicle motion
    #: through MAVROS is outside this package and is not claimed.
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeFastSwarmSim"}
    tags = ["ros", "ros2", "simulation", "fastswarmsim", "px4", "clock", "pause"]
    display_name = "FastSwarmSim lock-step time coordinator"
    vendor = "shupx"
    model = "fss_time time coordinator"
    facts = [
        Fact("The time coordinator publishes rosgraph_msgs::msg::Clock on the absolute /clock topic with "
             "rclcpp::ClockQoS, which the source comment describes as best-effort and volatile.",
             source="upstream_code", ref=_CLOCK_REF),
        Fact("The coordinator publishes fss_time_interfaces::msg::SimClockStatus on the relative "
             "fss/sim_clock_status topic with KeepLast(10) and transient-local durability.",
             source="upstream_code", ref=_STATUS_REF),
        Fact("The coordinator creates the relative fss/clock_control service of type "
             "fss_time_interfaces::srv::SimClockControl.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:187-188"),
        Fact("The clock_control callback applies request->max_real_time_factor, then request->running, and "
             "always answers success=true with message \"time_coordinator updated\".",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:192-195"),
        Fact("set_running stores the flag, resets the regulator and real-time requests to the current "
             "simulation time and publishes the status message.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:348-361"),
        Fact("set_max_real_time_factor stores the value, resets the regulator and real-time requests, "
             "resets the regulator timer and publishes the status message.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:363-374"),
        Fact("should_advance returns false and reports RequestNotAdvanced while running_ is false.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:695-700"),
        Fact("A 200 ms wall timer calls on_clock_status_tick.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:341-344"),
        Fact("on_clock_status_tick updates the observed real-time factor, calls publish_clock_locked and "
             "publishes the status.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:609-617"),
        Fact("publish_clock fills a rosgraph_msgs::msg::Clock from the current simulation time and "
             "publishes it when publish_clock_ and clock_pub_ are set.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:785-791"),
        Fact("The fss_time README says the coordinator provides fss/clock_control to pause/resume the "
             "clock and set max_real_time_factor at runtime.",
             source="vendor_doc", ref="src/fss_time/README.md:21"),
        Fact("The fss_time README documents max_real_time_factor default 1.0, says 2.0 allows up to 2x "
             "and a large positive value gives the highest practical speed.",
             source="vendor_doc", ref="src/fss_time/README.md:43"),
        Fact("The fss_time README documents max_real_time_factor 0.0 as disabling periodic regulator "
             "requests and not as an unconstrained free-run mode.",
             source="vendor_doc", ref="src/fss_time/README.md:221"),
        Fact("The coordinator sets has_parent_coordinator_ when the fss_time_parent_coordinator_endpoint "
             "parameter is not empty.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:147-149"),
        Fact("receive_parent_grant sets sim_time_ns_ to a granted time newer than the current one and "
             "publishes the clock without checking running_.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:502-525"),
        Fact("With follows_real_time_ set, should_advance advances to the real-time request (capped by the "
             "regulator request below a factor of 1.0) and waits only for a participant that neither follows "
             "real time nor has a new request.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:707-725"),
        Fact("A child coordinator registers with its parent and passes its own follows_real_time setting.",
             source="upstream_code", ref="src/fss_time/src/time_coordinator.cpp:278-288"),
        Fact("time_coordinator.launch.py declares start_coordinator_ui with the default true.",
             source="upstream_code", ref="src/fss_time/launch/time_coordinator.launch.py:32-37"),
        Fact("time_coordinator.launch.py starts time_coordinator_ui.py when start_coordinator_ui is true.",
             source="upstream_code", ref="src/fss_time/launch/time_coordinator.launch.py:115-124"),
        Fact("The coordinator UI's play/pause handler calls request_control(not self.bridge.running, "
             "self.bridge.expected_rtf).",
             source="upstream_code", ref="src/fss_time/scripts/time_coordinator_ui.py:507-508"),
    ]
    safe_state = (
        "The acknowledged fss/clock_control service is called with running=false and "
        "max_real_time_factor=0.0; in a root coordinator (no fss_time_parent_coordinator_endpoint, the "
        "launch default) should_advance then refuses to advance the shared simulation time until any client "
        "of fss/clock_control sends running=true, such as the coordinator UI's play button. A child "
        "coordinator keeps advancing its clock on every parent grant, so there the clock is not held."
    )
    #: The deployed fake is an event-driven recording transport with no
    #: coordinator, ZeroMQ participant network, PX4 dynamics or wall clock.
    fidelity = {
        "engine": "analytic:ROS canned-response fake (event-driven clock control, no simulator)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned-response fake with placeholder clock/status replies; no clock "
                     "advance, participant accounting, lock-step scheduling or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free event-driven transport: it answers /clock, fss/sim_clock_status and "
            "fss/clock_control with canned messages and runs no fss_time coordinator, ZeroMQ participant "
            "network, PX4 dynamics, LiDAR renderer, DDS graph or wall-clock loop",
            "clock and status numbers are placeholders and do not advance; the fake cannot establish "
            "clock progression, observed real-time factor, participant accounting or lock-step determinism",
            "the fake keeps publishing the same placeholder clock sample while paused, modelling the "
            "coordinator's 200 ms status tick rather than a fresh stopped-state trajectory",
            "the clone states no numeric envelope for max_real_time_factor; resume is operator_required "
            "and no live site envelope is supplied here",
            "the pause service always overwrites max_real_time_factor as well as running; the fake models "
            "that, and a deployment must resume with an operator-selected factor",
            "vehicle control (MAVROS setpoints, arming, mode changes), PX4 dynamics, LiDAR point clouds and "
            "RViz visualisation are NOT COVERED by this package",
            "the pause holds only a root coordinator: a child coordinator (fss_time_parent_coordinator_endpoint "
            "set) advances its clock on every parent GRANT without checking running, and a parent that follows "
            "real time does not wait for a child that follows real time; the fake models a root coordinator "
            "only",
            "any client of fss/clock_control can resume the clock while the MHS latch is held; the default "
            "time_coordinator.launch.py starts the coordinator UI, whose play button sends running=true",
            "the status publisher is KeepLast(10) transient-local, so a new subscription may first receive a "
            "stored sample from before the latest pause or resume; the fake always answers with its current "
            "state",
        ],
    }

    commands = {
        "x-cap.shupx.clock.v1": _CLOCK,
        "x-cap.shupx.clock_status.v1": _STATUS,
        "x-cap.shupx.pause.v1": _PAUSE,
        "x-cap.shupx.resume.v1": _RESUME,
    }
    #: The coordinator status is the observable effect of pause/resume.  A
    #: 200 ms wall timer keeps publishing it while paused; the publisher is
    #: KeepLast(10) transient-local, so a new subscription may first receive a
    #: stored sample from before the latest pause or resume.
    parameters = {
        "clock_running": Field("boolean",
                               description="Last SimClockStatus.running observed on the status topic"),
        "clock_factor": Field("number", unit="1",
                              description="Last SimClockStatus.max_real_time_factor observed on the status topic"),
    }
    reads = {
        "clock_running": dict(_STATUS_READ, path="running"),
        "clock_factor": dict(_STATUS_READ, path="max_real_time_factor"),
    }
    actions = {
        "x-cap.shupx.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one simulated clock sample from the fss_time coordinator",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.shupx.clock_status.v1": Action(
            name="read_clock_status",
            verb="read",
            description="Read the coordinator's status, including running and the configured factor",
            output=_STATUS_OUTPUT,
        ),
        "x-cap.shupx.pause.v1": Action(
            name="pause",
            safe_state=True,
            description="Pause clock advancement with the acknowledged fss/clock_control service",
            output=_ACK,
        ),
        "x-cap.shupx.resume.v1": Action(
            name="resume",
            description="Resume clock advancement at an operator-selected real-time factor",
            input={"max_real_time_factor": Field(
                "number", unit="1", limit=_SPEED_LIMIT,
                description="Simulation-time to wall-time ratio for the resumed clock")},
            output=_ACK,
        ),
    }
    #: The upstream stop is the same acknowledged clock_control service with a
    #: fixed running=false request.  The runtime latches in software first.
    safety_bindings = {"estop": _PAUSE}
