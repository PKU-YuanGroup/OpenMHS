"""OpenMHS rosbridge driver for the swarm_sync_sim simulation clock (gh.shupx/swarm_sync_sim).

The upstream ``sss_sim_env`` package is a C++ ROS 1 nodelet that drives a
lock-stepped multi-robot simulation.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class and
imports no ROS.  The scope is the simulation clock environment control exposed
by ``TimeServer``: the latched ``/clock`` and ``/sss_clock_is_online``
observations and the acknowledged ``/sss_clock_control`` service used to pause
and resume the clock.

``pause`` stops the wall-timer speed regulator (time client 0) from posting
further clock requests and is the simulator's stop.  It is an input-free
safe-state action and the native e-stop binding.  Because ``try_update_clock``
advances ``/clock`` only when every client, client 0 included, has a new
request, registered time clients can complete at most the regulator's pending
0.01 s step after a pause; simulated time then holds until any ROS client (the
shipped clock UI's Start button or speed dial included) sends ``proceed=true``
(model review of 2026-11-04).  It is not a physical emergency stop.
Participant registration and the per-client time-request protocol are outside
this package (see ``facts.md`` and RESULT notes).

Every endpoint, type and fact cites the pinned clone at
4837b511c3d2bcaa36448e5e5af51335004bafd8.  The fake transport is ROS-free and
contacts no ROS graph, simulator or hardware.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: TimeServer publishes the simulated clock on the absolute /clock topic and a
#: latched online flag on /sss_clock_is_online.
_CLOCK_REF = "src/sss_sim_env/src/sim_clock/TimeServer.cpp:41-42"

#: The absolute clock-control service and its callback.
_CONTROL_REF = "src/sss_sim_env/src/sim_clock/TimeServer.cpp:43"
_CONTROL_TYPE_REF = "src/sss_sim_env/include/sss_sim_env/TimeServer.hpp:28"

#: The pause trace (model review of 2026-11-04): the start-up pause state, the
#: regulator registered as client 0 and its 0.01 s step, the all-clients rule
#: of try_update_clock and its request clearing, and the shipped clock UI that
#: resumes the clock from its Start button and speed dial.
_TS = "src/sss_sim_env/src/sim_clock/TimeServer.cpp"
_UI = "src/sss_sim_env/scripts/clock_ui.py"
_START_STATE_REF = f"{_TS}:34-39"
_REGULATOR_CLIENT_REF = f"{_TS}:58-62"
_REGULATOR_STEP_REF = f"{_TS}:67-68"
_ALL_CLIENTS_REF = f"{_TS}:248-272"
_CLEAR_REQUESTS_REF = f"{_TS}:286-297"
_LAUNCH_REF = "src/sss_sim_env/launch/sim_clock.launch:4-23"
_UI_CALLS_REF = f"{_UI}:48-82"
_UI_WIRING_REF = f"{_UI}:162-164"

#: The service callback applies proceed, then optionally max_sim_speed, and
#: always answers success=true (its request/response contract is in the .srv).
_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/Clock",
    "source_name": "/clock",
    "source_ref": _CLOCK_REF,
    "operation": "subscribe",
    "path": "clock",
    "result": {"map": {"sim_time": "output.$"}},
}

_ONLINE = {
    "topic": "/sss_clock_is_online",
    "type": "std_msgs/Bool",
    "source_name": "/sss_clock_is_online",
    "source_ref": _CLOCK_REF,
    "operation": "subscribe",
    "path": "data",
    "result": {"map": {"online": "output.$"}},
}

_CONTROL = {
    "service": "/sss_clock_control",
    "type": "sss_sim_env/SimClockControl",
    "source_name": "/sss_clock_control",
    "source_ref": _CONTROL_REF,
    "type_ref": _CONTROL_TYPE_REF,
    "success": {"path": "success", "equals": True},
}

#: The callback always applies proceed.  max_sim_speed 0.0 is the message's
#: documented "keep original sim speed" value, so an input-free pause and
#: resume leave the configured ratio untouched.
_PAUSE = dict(
    _CONTROL,
    request={"proceed": False, "max_sim_speed": 0.0},
    result={"acknowledged": {"value": True}},
)

_RESUME = dict(
    _CONTROL,
    request={"proceed": True},
    args={"max_sim_speed": {"from": "input.max_sim_speed"}},
    result={"acknowledged": {"value": True}},
)

#: The clone accepts every nonzero max_sim_speed and states no numeric maximum;
#: the launch value is a configurable default, not a device bound.  The
#: operator supplies the site speed-ratio envelope for resume.
_SPEED_LIMIT = Limit.operator_required(
    "the /sss_clock_control callback accepts every nonzero max_sim_speed and the clone states no numeric "
    "maximum; the launch value is a configured default, so the operator supplies the site speed-ratio envelope"
)

_SIM_TIME = Field(
    "object",
    description="Simulated ROS clock sample carried by the latched /clock topic",
    properties={
        "secs": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)

_ACK = {
    "acknowledged": Field(
        "boolean",
        description="True once the /sss_clock_control service acknowledged the request",
    )
}


class SwarmSyncSim(RosDriver):
    device_id = "swarm_sync_sim"
    device_kind = "world.sim"
    mode = "simulated"
    #: This package controls only the simulation clock of an isolated simulator.
    #: Vehicle control through MAVROS/px4_rotor_sim and the simulated robots are
    #: outside this package and are not claimed.
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeSwarmSyncSim"}
    tags = ["ros", "ros1", "simulation", "swarm-sync-sim", "clock", "pause", "lock-step"]
    display_name = "swarm_sync_sim lock-step simulation clock"
    vendor = "shupx"
    model = "sss_sim_env sim clock nodelet"
    facts = [
        Fact("The sim clock advertises rosgraph_msgs/Clock on the absolute /clock topic and std_msgs/Bool on "
             "the absolute /sss_clock_is_online topic, both as latched publishers.",
             source="upstream_code", ref=_CLOCK_REF),
        Fact("TimeServer advertises the absolute /sss_clock_control, /sss_timeclient_register and "
             "/sss_timeclient_unregister services.",
             source="upstream_code", ref="src/sss_sim_env/src/sim_clock/TimeServer.cpp:43-45"),
        Fact("The clock-control callback sets is_paused_ from the proceed field, changes max_speed_ratio_ and "
             "the wall-timer period only when max_sim_speed is nonzero, and always answers success=true.",
             source="upstream_code", ref="src/sss_sim_env/src/sim_clock/TimeServer.cpp:101-116"),
        Fact("The speed-regulator wall timer requests and tries a clock update only while the clock is not "
             "paused.",
             source="upstream_code", ref="src/sss_sim_env/src/sim_clock/TimeServer.cpp:81-99"),
        Fact("The update-clock-request callback stores the client's request and calls try_update_clock without "
             "checking is_paused_.",
             source="upstream_code", ref="src/sss_sim_env/src/sim_clock/TimeServer.cpp:164-193"),
        Fact("try_update_clock publishes the minimum pending request on /clock only when every time client has "
             "a new request and that request is later than the current ROS time.",
             source="upstream_code", ref="src/sss_sim_env/src/sim_clock/TimeServer.cpp:248-284"),
        Fact("try_update_clock checks the clients from index 0 and does not publish when any of them, client 0 "
             "included, has no new request.",
             source="upstream_code", ref=_ALL_CLIENTS_REF),
        Fact("After publishing, try_update_clock clears has_new_request for every client whose request time is "
             "at or before the new sim_time_.",
             source="upstream_code", ref=_CLEAR_REQUESTS_REF),
        Fact("The TimeServer constructor registers time client 0 as the simulation speed regulator.",
             source="upstream_code", ref=_REGULATOR_CLIENT_REF),
        Fact("The regulator step speed_regulator_period_ is 0.01 s and its wall timer period is that step divided "
             "by max_speed_ratio_.",
             source="upstream_code", ref=_REGULATOR_STEP_REF),
        Fact("The node reads max_speed_ratio (default 100) and auto_start (default false) and starts with "
             "is_paused_ = !auto_start_.",
             source="upstream_code", ref=_START_STATE_REF),
        Fact("sim_clock.launch defaults max_speed_ratio to 100, auto_start to true and open_ui to true, and starts "
             "clock_ui.py when open_ui is set.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("clock_ui.py calls /sss_clock_control with proceed=True from call_start, with proceed=False from "
             "call_pause, and with proceed=True and the new max_sim_speed from call_speed_change.",
             source="upstream_code", ref=_UI_CALLS_REF),
        Fact("clock_ui.py connects call_start to the Start button, call_pause to the Pause button and "
             "call_speed_change to the speed dial's valueChanged signal.",
             source="upstream_code", ref=_UI_WIRING_REF),
        Fact("Registering a time client appends it, returns client_id and success=true, and calls "
             "try_update_clock.",
             source="upstream_code", ref="src/sss_sim_env/src/sim_clock/TimeServer.cpp:119-136"),
        Fact("Unregistering client 0 is refused; a matching nonzero client id is erased and success set true, "
             "otherwise success stays false.",
             source="upstream_code", ref="src/sss_sim_env/src/sim_clock/TimeServer.cpp:140-162"),
        Fact("The SimClockControl request carries proceed and max_sim_speed, and max_sim_speed 0 keeps the "
             "original simulation speed.",
             source="upstream_code", ref="src/sss_sim_env/srv/SimClockControl.srv:3-6"),
        Fact("The SimClockControl response is a success boolean.",
             source="upstream_code", ref="src/sss_sim_env/srv/SimClockControl.srv:7-8"),
        Fact("The TimeRequest message carries time_client_id and request_time.",
             source="upstream_code", ref="src/sss_sim_env/msg/TimeRequest.msg:1-2"),
        Fact("The README describes swarm_sync_sim as a synchronized (lock-stepped) multi-robot swarm "
             "simulation platform based on ROS.",
             source="vendor_doc", ref="README.md:5"),
        Fact("The README's first usage step launches sss_sim_env sim_clock.launch with max_speed_ratio and "
             "auto_start arguments.",
             source="vendor_doc", ref="README.md:35-36"),
    ]
    safe_state = (
        "The acknowledged /sss_clock_control request sets is_paused_, so the speed regulator (time client 0) "
        "stops posting clock requests; as try_update_clock publishes /clock only when every client, client 0 "
        "included, has a new request, simulated time advances at most the pending 0.01 s regulator step and "
        "then holds, freezing nodes timed on simulated time, until any ROS client, the shipped clock UI Start "
        "button or speed dial included, sends proceed=true."
    )
    #: The deployed fake is an event-driven recording transport.  It has no ROS
    #: graph, nodelet, lock-step scheduler, time-client network or wall clock.
    fidelity = {
        "engine": "analytic:ROS recording transport (event-driven clock control, no simulator)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned-response fake that adds a fixed placeholder step on each /clock "
                     "observation while unpaused; no wall-clock pacing, participant accounting, lock-step "
                     "scheduling or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers /clock, /sss_clock_is_online and "
            "/sss_clock_control with canned messages and runs no TimeServer, nodelet manager, ROS graph, "
            "time-client network or wall-clock regulator",
            "the clock sample is a placeholder and advances by a fixed test step on each observation while "
            "unpaused; the fake cannot establish wall-clock pacing, regulator timing or lock-step determinism",
            "/clock is latched in the clone and the fake returns the held sample while paused; that sample is "
            "not fresh stopped-state evidence",
            "the pause flag in the fake only changes the fake's own state; no external time client or "
            "update_clock_request path exists in this package",
            "the fake holds /clock at once after a pause, while the clone can still complete the regulator's "
            "pending 0.01 s step when time clients request it; the fake's reject_clock_application switch "
            "models a reply the clone never sends (its callback always answers success=true)",
            "the shipped sim_clock.launch starts clock_ui.py by default, and its Start button or any speed-dial "
            "change sends proceed=true, so a pause, the e-stop's included, holds only while no ROS client "
            "resumes the clock; the MHS latch refuses only this driver's commands",
            "while paused, nodes timed on simulated time (the simulated vehicles' timers, the visualizer loops) "
            "freeze; nodes on wall time do not",
            "participant registration (/sss_timeclient_register, /sss_timeclient_unregister) and per-client "
            "time requests (/sss_time_client/update_clock_request) are NOT COVERED: a single rosbridge "
            "binding cannot sequence register, request and wait for /clock, and a registered silent client "
            "blocks clock updates",
            "the simulated robots, MAVROS/px4 topics, tello and UGV dynamics, physics stepping, reset, "
            "snapshot, restore and rendering are NOT COVERED by this package",
        ],
    }

    commands = {
        "x-cap.shupx.clock.v1": _CLOCK,
        "x-cap.shupx.online.v1": _ONLINE,
        "x-cap.shupx.pause.v1": _PAUSE,
        "x-cap.shupx.resume.v1": _RESUME,
    }
    actions = {
        "x-cap.shupx.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read the latched simulated clock sample published on /clock",
            output={"sim_time": _SIM_TIME},
        ),
        "x-cap.shupx.online.v1": Action(
            name="read_clock_online",
            verb="read",
            description="Read the latched sim clock online flag",
            output={"online": Field("boolean", description="True while TimeServer has published its online flag")},
        ),
        "x-cap.shupx.pause.v1": Action(
            name="pause",
            safe_state=True,
            description="Pause the simulation clock with /sss_clock_control; /clock holds after at most the "
                        "regulator's pending 0.01 s step until a client resumes it",
            output=_ACK,
        ),
        "x-cap.shupx.resume.v1": Action(
            name="resume",
            description="Resume clock advancement at an operator-selected speed ratio",
            input={"max_sim_speed": Field(
                "number", unit="1", limit=_SPEED_LIMIT,
                description="Simulation speed ratio for the resumed clock")},
            output=_ACK,
        ),
    }
    #: The upstream stop is the same acknowledged clock-control service with a
    #: fixed proceed=false request.  The runtime latches in software first.
    #: This pauses the regulator, and without client 0's requests
    #: try_update_clock stops advancing /clock after the pending step
    #: (TimeServer.cpp:81-99, 248-297); any ROS client can resume it.
    safety_bindings = {"estop": _PAUSE}
