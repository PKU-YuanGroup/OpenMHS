"""OpenMHS rosbridge driver for the drl_uav reinforcement-learning game interface.

The pinned repository is a ROS 1 catkin package for deep reinforcement learning
of a UAV in an external Gazebo/Pixhawk/ROS SITL simulation: it ships message
definitions, a DRL agent node (``scripts/talker.py``) and a toy game node
(``scripts/game_test.py``).  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class, does not
launch or import the upstream nodes, and neither starts Gazebo, PX4, MAVROS nor
the external ``state_machine``.  The operator runs the upstream game/environment
and rosbridge separately.

The served surface is the clone's only in-repo environment contract:

* the relative ``game_status`` topic with ``drl_uav/Output_Game`` (four
  ``float64`` fields ``vel1``, ``vel2``, ``pos1`` and ``pos2``), published by
  the toy environment and subscribed by the DRL node;
* the relative ``game_input`` topic with ``drl_uav/Input_Game`` (one
  ``float64`` field ``action``), published by the DRL node and consumed by the
  environment.

The declared action envelope is the clone's documented DRL action vocabulary
``{0, 1, -1}`` (``ReadMe.md:18-24``): 0 and 1 request a thrust decrease or
increase and -1 requests an environment restart.  The shipped toy game instead
restarts when ``action > 100.0`` (``scripts/game_test.py:24``) and
``scripts/player_test.py:44-45`` uses 200.0, so the restart sentinel is a
deployment detail: a deployment that uses 200.0 is outside this envelope.  The
publication receipt confirms transmission only; it does not prove that any
environment consumed the action, restarted, or changed altitude.

``game_status`` is the only observation the clone defines for the game; the
real DRL node also reads ``mavros/local_position/pose``,
``mavros/local_position/velocity`` and ``/mavros/setpoint_raw/attitude``, but
those MAVROS topics and their message types are outside this package's scope.
Every endpoint, type and fact cites the pinned clone at
55e2a0a97c70f584b0a272176999148985f5ee46.  The fake transport is ROS-free and
all of its state values are placeholders.

There is no acknowledged stop service or stop action in the clone
(``CMakeLists.txt:62-74`` defines no service or action).  The driver therefore
declares no e-stop or safe-state binding; an MHS e-stop engages only the
software latch, calls nothing upstream and keeps the latch engaged.  The
declared risk is R0 because the served contract is a simulated game topic
interface with no physical effect; the external Gazebo/PX4 runtime is not
launched, controlled or certified here.  This package is model-authored and
unreviewed.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: talker.py imports both game message types from the generated drl_uav.msg package.
_MSG_IMPORT_REF = "scripts/talker.py:17-18"

#: talker.py publishes Input_Game on the relative game_input topic with queue size 10.
_GAME_INPUT_PUB_REF = "scripts/talker.py:219"

#: talker.py publishes the current env_input.action on game_input in interact().
_GAME_INPUT_SEND_REF = "scripts/talker.py:267"

#: talker.py subscribes Output_Game on the relative game_status topic.
_GAME_STATUS_SUB_REF = "scripts/talker.py:312"

#: talker.py sets action -1.0 and publishes it to restart after a done condition.
_GAME_RESTART_REF = "scripts/talker.py:408-411"

#: game_test.py publishes Output_Game on the relative game_status topic with queue size 10.
_TOY_STATUS_PUB_REF = "scripts/game_test.py:15"

#: game_test.py subscribes Input_Game on the relative game_input topic.
_TOY_INPUT_SUB_REF = "scripts/game_test.py:41"

#: game_test.py restarts when action > 100.0 and moves pos1 by +-0.1 for action 1.0 or 0.0.
_TOY_SEMANTICS_REF = "scripts/game_test.py:24-32"

#: game_test.py publishes the game status at 10 Hz.
_TOY_RATE_REF = "scripts/game_test.py:49-58"

#: The package declares only message files; the service/action sections are commented out.
_MSG_ONLY_REF = "CMakeLists.txt:51-74"

# ---------------------------------------------------------------------------
# Units and limits
# ---------------------------------------------------------------------------

#: The ReadMe states the DRL action vocabulary {0, 1, -1}; the message field itself
#: is a bare float64 and the shipped toy uses a different restart sentinel, which is
#: disclosed in facts.md and the fidelity gaps.
_ACTION_LIMIT = Limit(
    allowed=[-1.0, 0.0, 1.0],
    source="vendor_doc",
    ref="ReadMe.md:18-24",
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_GAME_STATUS_FIELDS = ("vel1", "vel2", "pos1", "pos2")

_GAME_STATUS_OUTPUT = {
    name: Field("number", description=f"Output_Game.{name} as published; the clone declares no unit")
    for name in _GAME_STATUS_FIELDS
}

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the Input_Game message to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication has no execution acknowledgement"),
}

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

_GAME_STATUS = {
    "topic": "/game_status",
    "type": "drl_uav/Output_Game",
    "source_name": "game_status",
    "source_ref": _GAME_STATUS_SUB_REF,
    "type_ref": "scripts/talker.py:18",
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {name: f"output.{name}" for name in _GAME_STATUS_FIELDS}},
    "description": "Observe one drl_uav/Output_Game sample on game_status",
}

_GAME_ACTION = {
    "topic": "/game_input",
    "type": "drl_uav/Input_Game",
    "source_name": "game_input",
    "source_ref": _GAME_INPUT_PUB_REF,
    "type_ref": "scripts/talker.py:17",
    "operation": "publish",
    "message": {"action": 0.0},
    "args": {"action": {"from": "input.action"}},
    "description": "Publish one drl_uav/Input_Game action on game_input; transmission only",
}


class DrlUavGame(RosDriver):
    device_id = "drl-uav-game"
    device_kind = "world.sim"
    mode = "simulated"
    #: A simulated game-topic interface with no physical effect.  The external
    #: Gazebo/PX4/state_machine runtime is outside this package's scope.
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeDrlUavGame"}
    tags = ["ros", "ros1", "simulation", "reinforcement-learning", "uav", "game", "drl"]
    display_name = "DRL UAV game environment"
    vendor = "px4-gazebo-simulation"
    model = "drl_uav ROS 1 game interface"
    facts = [
        Fact("The clone describes deep reinforcement learning for a UAV in a Gazebo simulation environment.",
             source="vendor_doc", ref="ReadMe.md:2"),
        Fact("The documented deployment is Gazebo, Pixhawk and ROS SITL, started together with MAVROS, an "
             "external state_machine node and this package's talker.py.", source="vendor_doc",
             ref="ReadMe.md:91-122"),
        Fact("The documented DRL state is [Pos_z, Vel_z, Thrust], the action set is {0, 1, -1} (0 decreases "
             "thrust, 1 increases thrust and -1 restarts the environment), and the reward is 1 inside "
             "19.7 < Pos_z < 20.3 and 0 otherwise.", source="vendor_doc", ref="ReadMe.md:15-30"),
        Fact("The clone lists Gazebo constraints thrust [0.40, 0.78], Vel_z [-3.0, 3.0] and Pos_z [10, 30] for "
             "training; these describe the external Gazebo environment, not the game topic envelope.",
             source="vendor_doc", ref="ReadMe.md:124-130"),
        Fact("talker.py imports Num, Input_Game and Output_Game from the generated drl_uav.msg package.",
             source="upstream_code", ref="scripts/talker.py:16-18"),
        Fact("talker.py advertises Input_Game on the relative game_input topic with queue size 10.",
             source="upstream_code", ref=_GAME_INPUT_PUB_REF),
        Fact("talker.py publishes the current env_input action on game_input in interact().",
             source="upstream_code", ref=_GAME_INPUT_SEND_REF),
        Fact("talker.py subscribes Output_Game on the relative game_status topic.",
             source="upstream_code", ref=_GAME_STATUS_SUB_REF),
        Fact("talker.py sets the action to -1.0 and publishes it to restart the game after a done condition.",
             source="upstream_code", ref=_GAME_RESTART_REF),
        Fact("game_test.py describes itself as a test platform of the game environment and advertises "
             "Output_Game on the relative game_status topic with queue size 10.", source="upstream_code",
             ref="scripts/game_test.py:1-15"),
        Fact("game_test.py subscribes Input_Game on the relative game_input topic.",
             source="upstream_code", ref=_TOY_INPUT_SUB_REF),
        Fact("The toy game resets pos1 to 3.5 when the action is greater than 100.0, adds 0.1 to pos1 for "
             "action 1.0 and subtracts 0.1 for action 0.0.", source="upstream_code", ref=_TOY_SEMANTICS_REF),
        Fact("game_test.py publishes game_status at 10 Hz from a rospy.Rate(10) loop.",
             source="upstream_code", ref=_TOY_RATE_REF),
        Fact("game_test.py initializes the game status with vel1 0.5 and pos1 3.5.",
             source="upstream_code", ref="scripts/game_test.py:16-18"),
        Fact("player_test.py sets the action to 200.0 when the reported UAV altitude is outside [8.0, 30.0] "
             "to restart the environment.", source="upstream_code", ref="scripts/player_test.py:43-45"),
        Fact("Input_Game contains one float64 field named action.", source="upstream_code",
             ref="msg/Input_Game.msg:1"),
        Fact("Output_Game contains four float64 fields named vel1, vel2, pos1 and pos2.", source="upstream_code",
             ref="msg/Output_Game.msg:1-4"),
        Fact("The package declares only message files; its service and action sections are commented out.",
             source="upstream_code", ref=_MSG_ONLY_REF),
        Fact("talker.py ends with a Python 2 print statement, so the script is not importable under Python 3.",
             source="upstream_code", ref="scripts/talker.py:458"),
    ]
    safe_state = (
        "No acknowledged stop exists in the clone: an MHS e-stop engages only the software latch, calls nothing "
        "upstream and keeps the latch engaged, while the external game environment and the simulated UAV keep "
        "running; the driver publishes only a game action and cannot restart, pause or stop them."
    )
    #: F0 describes the deployed ROS-free recording fake, not the external simulator.
    fidelity = {
        "engine": "analytic:ROS-free recording fake for the drl_uav game topic contract (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no UAV dynamics, physics step or wall-clock pacing; "
                     "placeholder game state does not establish flight, altitude or episode replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free ros_transport handler: it answers the declared game_status subscription and "
            "records the game_input publication, but it runs no Gazebo, PX4, MAVROS, state_machine, DRL agent or "
            "wall-clock loop",
            "the real environment is outside the clone: the README starts PX4/Gazebo, MAVROS and an external "
            "state_machine, and this package neither starts nor validates them",
            "the fake models the toy game_test.py semantics (action 1.0 adds 0.1 to pos1, action 0.0 subtracts "
            "0.1 and action > 100.0 resets pos1 to 3.5); it does not model the external state_machine and it "
            "ignores the README's -1 restart request, which game_test.py also ignores",
            "the clone gives conflicting restart sentinels: the README documents -1, game_test.py restarts above "
            "100.0 and player_test.py uses 200.0; the declared envelope is only the README vocabulary {0, 1, -1}",
            "Output_Game's four float64 fields have no documented units or physical meaning; the driver exposes "
            "them as bare numbers and asserts none",
            "the game_status publication rate is 10 Hz only in the toy game_test.py; live topic freshness, "
            "namespace resolution, QoS and remapping are outside the clone and the fake",
            "no e-stop or safe-state binding is declared: there is no upstream stop service or action, a "
            "publication has no confirmation and the stock e-stop keeps the latch and calls nothing upstream",
            "the real DRL node's mavros/local_position/pose, mavros/local_position/velocity and "
            "/mavros/setpoint_raw/attitude topics and their types are NOT COVERED",
            "ROS 1 catkin build, rospy, keras/TensorFlow, the upstream nodes and any hardware are NOT COVERED",
        ],
    }

    parameters = {
        name: Field("number", description=f"Output_Game.{name} as last published; the clone declares no unit")
        for name in _GAME_STATUS_FIELDS
    }
    reads = {
        name: {
            "topic": "/game_status",
            "type": "drl_uav/Output_Game",
            "source_name": "game_status",
            "source_ref": _GAME_STATUS_SUB_REF,
            "type_ref": "scripts/talker.py:18",
            "path": name,
            "timeout_ms": 2000,
        }
        for name in _GAME_STATUS_FIELDS
    }
    commands = {
        "x-cap.px4-gazebo-simulation.game-status.v1": _GAME_STATUS,
        "x-cap.px4-gazebo-simulation.game-action.v1": _GAME_ACTION,
    }
    actions = {
        "x-cap.px4-gazebo-simulation.game-status.v1": Action(
            name="read_game_status",
            verb="read",
            description="Read one drl_uav/Output_Game sample from the game_status topic",
            output=_GAME_STATUS_OUTPUT,
        ),
        "x-cap.px4-gazebo-simulation.game-action.v1": Action(
            name="send_game_action",
            verb="invoke",
            description="Publish one drl_uav/Input_Game action on game_input; the receipt confirms transmission "
                        "only, not consumption, altitude change or episode transition",
            input={
                "action": Field(
                    "number",
                    unit="1",
                    description="DRL game action: 0 requests less thrust, 1 requests more thrust and -1 requests "
                                "an environment restart according to ReadMe.md:18-24; dimensionless selector",
                    limit=_ACTION_LIMIT,
                ),
            },
            output=_PUBLISHED,
        ),
    }
    #: The clone has no stop service or stop action (CMakeLists.txt:62-74), so
    #: no e-stop binding is declared.  A stock e-stop latches in software only.
    safety_bindings = {}
