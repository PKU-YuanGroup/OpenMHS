"""OpenMHS rosbridge driver for the MuJoCo ROS 1 simulator (gh.ubi-agni/mujoco_ros_pkgs).

The upstream mujoco_ros node is a C++ ROS 1 process.  This package is a
configuration-only RosDriver over rosbridge; it declares no Python native
class.  Its scope is deliberately narrow: the acknowledged ``set_pause``
service with a fixed ``paused=true`` request, and the observational
``get_sim_info`` service reduced to ``state.paused``.  ``pause`` is the
continuous-run stop: the control state records ``running=false`` and the
physics loop takes its paused branch, which can still execute manual steps.  It is not a physical emergency stop, and it
does not command a robot velocity, resume, step, reload or shutdown.

Every endpoint, type and fact cites the pinned clone at
9304ca7ec254ac1aaa0c2f556513a9a51d28530e.  The fake transport is ROS-free;
no ROS graph, simulator process or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The service is advertised relative to the node's private handle ("~").
_SET_PAUSE = {
    "service": "/mujoco_server/set_pause",
    "type": "mujoco_ros_msgs/SetPause",
    "source_name": "set_pause",
    "source_ref": "mujoco_ros/src/ros_one/ros_api.cpp:55",
    "type_ref": "mujoco_ros/include/mujoco_ros/ros_one/ros_api.hpp:51",
    # The fixed request is pause-only.  An empty admin_hash is the
    # unauthenticated deployment assumption, not a credential.
    "request": {"paused": True, "admin_hash": ""},
    "success": {"path": "success", "equals": True},
}

#: get_sim_info is an observation: the callback fills a response, it does not
#: change the simulation.  Only state.paused is mapped into the action output.
_GET_SIM_INFO = {
    "service": "/mujoco_server/get_sim_info",
    "type": "mujoco_ros_msgs/GetSimInfo",
    "source_name": "get_sim_info",
    "source_ref": "mujoco_ros/src/ros_one/ros_api.cpp:72",
    "type_ref": "mujoco_ros/include/mujoco_ros/ros_one/ros_api.hpp:63",
    "operation": "read",
    "result": {"map": {"paused": "state.paused"}},
}


class MujocoRos(RosDriver):
    device_id = "mujoco_ros"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeMujocoRos"}
    tags = ["ros", "ros1", "simulation", "mujoco", "pause", "sim-info"]
    display_name = "MuJoCo ROS simulator"
    vendor = "ubi-agni"
    facts = [
        Fact("RosAPI::SetupServices advertises the relative set_pause service through the node's private "
             "node handle.", source="upstream_code", ref="mujoco_ros/src/ros_one/ros_api.cpp:55"),
        Fact("RosAPI::SetPauseCB takes a mujoco_ros_msgs::SetPause request and response and sets "
             "response.success from TogglePaused(req.paused, req.admin_hash).",
             source="upstream_code", ref="mujoco_ros/src/ros_one/ros_api.cpp:409-417"),
        Fact("SetPause.srv declares request fields bool paused and string admin_hash and response field "
             "bool success.", source="upstream_code", ref="mujoco_ros_msgs/srv/SetPause.srv:1-4"),
        Fact("MujocoEnv::TogglePaused refuses a paused=true request when VerifyAdminHash fails, before "
             "calling SetPaused, and returns false.", source="upstream_code",
             ref="mujoco_ros/src/interface.cpp:57-66"),
        Fact("MujocoEnv::VerifyAdminHash compares the supplied hash with settings_.admin_hash only when "
             "eval_mode is set; outside eval mode it returns true.", source="upstream_code",
             ref="mujoco_ros/src/mujoco_env.cpp:1211-1220"),
        Fact("SimulationControlState::SetPaused stores running_ = !paused and notifies the physics condition.",
             source="upstream_code",
             ref="mujoco_ros/include/mujoco_ros/simulation_control_state.hpp:88-95"),
        Fact("The physics loop calls SimPausedPhysics while the control snapshot is not running and "
             "SimUnpausedPhysics otherwise.", source="upstream_code",
             ref="mujoco_ros/src/physics.cpp:297-302"),
        Fact("SimPausedPhysics executes requested manual steps through WrappedStep; without a pending step it "
             "runs mj_forward and publishes simulation time.", source="upstream_code",
             ref="mujoco_ros/src/physics.cpp:314-340"),
        Fact("MujocoEnv::GetSimInfo reports paused as the negation of the control snapshot's running flag.",
             source="upstream_code", ref="mujoco_ros/src/interface.cpp:1211-1220"),
        Fact("RosAPI::SetupServices advertises the relative get_sim_info service through the node's private "
             "node handle.", source="upstream_code", ref="mujoco_ros/src/ros_one/ros_api.cpp:72"),
        Fact("RosAPI::GetSimInfoCB takes a mujoco_ros_msgs::GetSimInfo request and response, calls "
             "MujocoEnv::GetSimInfo and assigns res.state.paused.", source="upstream_code",
             ref="mujoco_ros/src/ros_one/ros_api.cpp:791-802"),
        Fact("GetSimInfo.srv has an empty request and response field mujoco_ros_msgs/SimInfo state.",
             source="upstream_code", ref="mujoco_ros_msgs/srv/GetSimInfo.srv:1-2"),
        Fact("SimInfo.msg declares bool paused.", source="upstream_code",
             ref="mujoco_ros_msgs/msg/SimInfo.msg:5"),
        Fact("The ROS 1 MujocoEnv constructor creates the private node handle \"~\" and passes it to RosAPI, "
             "so relative service names resolve under the node's private namespace.", source="upstream_code",
             ref="mujoco_ros/src/mujoco_env.cpp:200-201"),
        Fact("The pinned launch file starts the mujoco_node executable as a node named mujoco_server; the "
             "node tag carries no ns attribute.", source="upstream_code",
             ref="mujoco_ros/launch/launch_server.launch:55"),
    ]
    safe_state = ("Continuous simulation run is disabled (running=false). The paused branch can still execute "
                  "pending or externally requested manual steps; this is not proof of quiescent physics, a frozen "
                  "clock or a physical emergency stop.")
    #: The deployed fake is a ROS-free recording transport, not MuJoCo and not a ROS node.
    fidelity = {
        "engine": "recording",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no physics step or pacing; placeholder paused "
                     "state does not establish a trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it runs no MuJoCo engine, physics stepping, "
            "contacts, sensors, renderer, ROS node or simulator process, and has no wall-clock pacing",
            "the fake answers only the two declared services and omits the rest of the SimInfo response; it "
            "reports only state.paused, which is the field this package consumes",
            "the paused flag is placeholder test state; holding it does not prove that an upstream "
            "simulator was running or that its physics loop paused",
            "no live ROS graph, rosbridge connection, simulator execution or hardware validation has run; "
            "the evidence remains contract_checked",
            "the empty admin_hash request assumes an unauthenticated deployment outside eval mode; an "
            "eval-mode deployment may reject it with success=false",
            "pause is the simulator stop, not a physical emergency stop, and it makes no claim about robot "
            "velocities or a hardware safe state",
            "pause does not cancel pending or external manual steps; the paused branch can still advance physics, "
            "and the fake does not model that step queue",
            "resume, model reload, world step, gravity, robot actuation and shutdown are not exposed",
        ],
    }

    commands = {
        "x-cap.ubi-agni.pause.v1": dict(_SET_PAUSE, result={"acknowledged": {"value": True}}),
        "x-cap.ubi-agni.sim_info.v1": _GET_SIM_INFO,
    }
    actions = {
        "x-cap.ubi-agni.pause.v1": Action(
            name="pause",
            verb="invoke",
            safe_state=True,
            description="Pause the MuJoCo ROS simulator with the acknowledged set_pause service",
            output={"acknowledged": Field("boolean",
                                          description="True once the SetPause response reports success=true")},
        ),
        "x-cap.ubi-agni.sim_info.v1": Action(
            name="get_sim_info",
            verb="read",
            description="Read the simulator's paused flag from the acknowledged get_sim_info service",
            output={"paused": Field("boolean",
                                    description="SimInfo.state.paused reported by the simulator")},
        ),
    }
    # The simulator stop path: a pause service call.  The runtime latches in
    # software before invoking it; the upstream pause flag is not a physical stop.
    safety_bindings = {"estop": _SET_PAUSE}
