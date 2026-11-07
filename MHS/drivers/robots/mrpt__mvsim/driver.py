"""OpenMHS driver for one vehicle of an MVSim simulation, through MVSim's own ZMQ/protobuf services (gh.mrpt/mvsim).

MVSim's simulator advertises services on its own ZMQ/protobuf client: ``set_controller_twist`` hands a twist setpoint
to a vehicle's controller under the simulation-step lock and answers success only when the controller accepted it,
and ``get_pose`` reads the vehicle's pose and twist (modules/simulator/src/World_services.cpp:78-170, 251-273). The
clone's own Python client calls them with serialised protobuf requests (examples_python/mvsim-teleop.py:13-30).

This package drives one configured vehicle (option ``vehicle``, default ``r1``, the name the clone's examples and
tutorial worlds use) through those services: a twist setpoint, a pose read, and an e-stop that sets a zero twist and
checks the answer. It is a direct Driver over the upstream client's ``callService`` member (the pybind11 class of the
generated binding, ``native``); the requests and answers are encoded by the package's own ``mvsim_wire`` module.
The ``fake`` backend is ``fake.py``; the ``sim`` backend (``sim.py``) is the package's own bounded ZMQ client with its
own declared dependency (pyzmq), because the upstream client waits without a timeout while holding the GIL. Every
fact cites the pinned clone at cfaf9f28f57fe5798a6b1defa65a435402bd38d0. No MVSim server, ROS graph or hardware was run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop

from . import mvsim_wire

_VX_LIMIT = Limit.operator_required(
    "MVSim states no bound for a twist setpoint: set_controller_twist hands vx to the vehicle's controller "
    "unchanged; the operator supplies the site envelope")
_WZ_LIMIT = Limit.operator_required(
    "MVSim states no bound for a twist setpoint: set_controller_twist hands omega to the vehicle's controller "
    "unchanged; the operator supplies the site envelope")

_POSE = Field("object", description="Pose of the vehicle as get_pose reports it (MVSim's TPose3D members)",
              properties={name: Field("number", description=f"Pose member {name}")
                          for name in ("x", "y", "z", "yaw", "pitch", "roll")})
_TWIST = Field("object", description="Twist of the vehicle as get_pose reports it (vz, wx and wy are written as 0)",
               properties={name: Field("number", description=f"Twist member {name}") for name in ("vx", "vy", "wz")})


class MvsimVehicle(Driver):
    device_id = "mvsim-vehicle"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    #: Velocity setpoints for a mobile base are mobile-base transit, R2 in the hazard table of MHS/spec/04-safety.md,
    #: as in the comparable simulated mobile-base packages; risk follows that table, not the card floor (R0).
    risk = "R2"
    native = "pybind:modules/comms/python/generated-sources-pybind/mvsim/Comms/Client.cpp#mvsim.Client"
    backends = {"fake": ".fake:FakeMvsimClient", "sim": ".sim:connect"}
    display_name = "MVSim vehicle through MVSim's services"
    vendor = "MRPT"
    model = "MVSim simulated vehicle"
    tags = ["mvsim", "simulation", "mobile-base", "zmq", "protobuf", "twist"]
    facts = [
        Fact("srv_set_controller_twist locks simulationStepRunningMtx_, answers success false with an error message "
             "when the object is not found, is not a VehicleBase or has no controller, passes the requested vx, vy "
             "and wz to the controller's setTwistCommand, and answers success true only when the controller accepted "
             "the twist.", source="upstream_code", ref="modules/simulator/src/World_services.cpp:124-170"),
        Fact("srv_get_pose answers success with the pose, the twist (vx, vy and omega; vz, wx and wy written as 0) "
             "and whether copy_of_objects_had_collision_ holds the object, or success false when the object is "
             "unknown; after answering it adds the object to reset_collision_flags_.", source="upstream_code",
             ref="modules/simulator/src/World_services.cpp:78-122"),
        Fact("In its post-step processing, which copies every object's dynamic state for service calls, the simulator "
             "adds each object whose hadCollision flag is set to copy_of_objects_had_collision_, then calls "
             "resetCollisionFlag on every object in reset_collision_flags_ and clears that set.",
             source="upstream_code", ref="modules/simulator/src/World_simul.cpp:224-269"),
        Fact("Simulable::hadCollision reports whether a collision occurred since the flag was last reset, and "
             "resetCollisionFlag resets it to false.", source="upstream_code",
             ref="modules/simulator/include/mvsim/Simulable.h:136-142"),
        Fact("The ROS node reads a vehicle's hadCollision flag, calls resetCollisionFlag and publishes the value it "
             "read on that vehicle's collision publisher.", source="upstream_code",
             ref="mvsim_node_src/mvsim_node.cpp:1120-1130"),
        Fact("World::internal_advertiseServices advertises set_pose, get_pose, set_controller_twist, shutdown, "
             "set_light_state and get_light_state on the simulator's ZMQ client.", source="upstream_code",
             ref="modules/simulator/src/World_services.cpp:251-273"),
        Fact("ControllerBaseInterface::setTwistCommand takes setpoints for linear (vx) velocity in m/s and angular "
             "(omega) velocity in rad/s, ignores vy, and returns false (twist commands unsupported) unless a "
             "controller overrides it.", source="upstream_code", ref="modules/simulator/include/mvsim/ControllerBase.h:44-54"),
        Fact("The differential drive's twist_pid controller stores the twist setpoint and returns true.",
             source="upstream_code", ref="modules/simulator/include/mvsim/VehicleDynamics/VehicleDifferential.h:151-158"),
        Fact("The differential drive's twist_ideal controller sets the vehicle twist to the setpoint perfectly and "
             "instantaneously; its setTwistCommand stores the setpoint and returns true.", source="upstream_code",
             ref="modules/simulator/include/mvsim/VehicleDynamics/VehicleDifferential.h:179-203"),
        Fact("The differential drive's trajectory controller does not override setTwistCommand.",
             source="upstream_code",
             ref="modules/simulator/include/mvsim/VehicleDynamics/VehicleDifferential.h:243-262"),
        Fact("SrvSetControllerTwist carries the required objectId (field 1) and twistSetPoint (field 2).",
             source="upstream_code", ref="modules/msgs/proto/SrvSetControllerTwist.proto:7-11"),
        Fact("Twist carries the required doubles vx, vy, vz, wx, wy and wz as fields 1 to 6.",
             source="upstream_code", ref="modules/msgs/proto/Twist.proto:5-12"),
        Fact("SrvSetControllerTwistAnswer carries the required success (field 1) and an optional errorMessage "
             "(field 2).", source="upstream_code", ref="modules/msgs/proto/SrvSetControllerTwistAnswer.proto:5-10"),
        Fact("SrvGetPoseAnswer carries success (1), errorMessage (2), pose (3), objectIsInCollision (4) and twist "
             "(5).", source="upstream_code", ref="modules/msgs/proto/SrvGetPoseAnswer.proto:8-18"),
        Fact("The generated Python binding of mvsim::Client exposes callService, which passes a serialised request "
             "as bytes to Client::callService and returns the serialised answer as bytes; the binding does not "
             "release the GIL around the call.", source="upstream_code", ref="modules/comms/python/generated-sources-pybind/mvsim/Comms/Client.cpp:74-87"),
        Fact("Client::doCallService asks the server for the service's endpoint, then sends a CallService message "
             "to it and waits for the reply.", source="upstream_code", ref="modules/comms/src/Comms/Client.cpp:735-808"),
        Fact("mvsim::receiveMessage waits on the ZMQ socket's recv with no timeout argument.",
             source="upstream_code", ref="modules/comms/src/Comms/common.cpp:63-73"),
        Fact("The client's service thread answers a request for an unknown service with a GenericAnswer whose "
             "success is false.", source="upstream_code", ref="modules/comms/src/Comms/Client.cpp:565-580"),
        Fact("mvsim-teleop.py builds a SrvSetControllerTwist for robot 'r1' with vx and vy in m/s and w in rad/s "
             "and sends it with callService('set_controller_twist', ...).", source="upstream_code",
             ref="examples_python/mvsim-teleop.py:17-40"),
        Fact("The tutorial world demo_2robots names its first vehicle r1.", source="upstream_code",
             ref="mvsim_tutorial/demo_2robots.world.xml:47"),
        Fact("The ROS node's cmd_vel callback also calls the vehicle controller's setTwistCommand.",
             source="upstream_code", ref="mvsim_node_src/mvsim_node.cpp:934-942"),
        Fact("The ROS node zeroes a vehicle's twist with setTwistCommand({0, 0, 0}) once its last ROS cmd_vel is "
             "older than MAX_CMD_VEL_AGE_SECONDS, tracked only for vehicles that received a ROS cmd_vel.",
             source="upstream_code", ref="mvsim_node_src/mvsim_node.cpp:525-540"),
        Fact("The default server port is 23700, or MVSIM_SERVER_PORT when it holds a valid port number.",
             source="upstream_code", ref="modules/comms/include/mvsim/Comms/ports.h:20-49"),
    ]
    safe_state = (
        "MVSim's set_controller_twist accepted a zero twist setpoint for the configured vehicle's controller, under "
        "the simulation-step lock: zero velocity is commanded, not measured braking. A controller that does not accept "
        "twists refuses it (e-stop unreached). ROS cmd_vel, GUI teleop and other MVSim clients can still command it."
    )
    fidelity = {
        "engine": "analytic:fake of MVSim's set_controller_twist and get_pose services (no simulation)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Canned service answers from placeholder state; no MVSim world, vehicle dynamics, controller, "
                     "clock or ZMQ socket, and no recorded traffic",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers set_controller_twist and get_pose from placeholder state; it runs no MVSim world, "
            "vehicle dynamics, collision, controller PID, clock or ZMQ transport (no dynamics are modelled)",
            "the fake's twist follows the setpoint at once, as MVSim's twist_ideal controller does; a twist_pid or "
            "Ackermann controller approaches it over time, and the fake pose never moves",
            "a raw-force or trajectory controller refuses twist commands (ControllerBase default): the fake models "
            "that refusal with a switch, not with a world file",
            "the sim backend (sim.py) speaks MVSim's ZMQ protocol with bounded sockets and has not been run against "
            "an MVSim server; its timing and port choice are the deployment's, and it connects to the configured "
            "host at the port the server reports for a service (MVSim reports its wildcard bind, Client.cpp:166-167 "
            "and 462), never to a host the server names",
            "the fake reports a placeholder collision flag that its reads never change; MVSim reports "
            "objectIsInCollision from a record its step only adds to (World_simul.cpp:254-256), and each get_pose "
            "call makes the next step reset the vehicle's own hadCollision flag (World_services.cpp:115-120, "
            "World_simul.cpp:260-269), which the ROS node's collision topic also reads and resets; the fake models "
            "neither",
            "set_pose, shutdown, the light services, MVSim topics, the ROS node and multi-vehicle commands are "
            "outside this package's declared surface",
        ],
    }

    def _vehicle(self) -> str:
        vehicle = self.options.get("vehicle", "r1")
        if not isinstance(vehicle, str) or not 1 <= len(vehicle) <= 128 or not vehicle.isprintable():
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "option vehicle must name one MVSim object")
        return vehicle

    def _send_twist(self, vx: float, wz: float) -> None:
        """Hand one twist setpoint to the vehicle's controller; a refusal fails, an uncertain outcome is unknown."""
        request = mvsim_wire.set_controller_twist(self._vehicle(), vx, 0.0, wz)
        try:
            reply = self.native.callService("set_controller_twist", request)
        except mvsim_wire.ServiceNotOffered as exc:
            # The server named no endpoint for the service: the request never reached it.
            raise DriverFailed("MHS.DEVICE.FAULTED", "MVSim does not offer set_controller_twist") from exc
        except Exception as exc:
            raise OutcomeUnknown("set_controller_twist was sent but no trustworthy answer arrived; the setpoint "
                                 "may have been applied") from exc
        try:
            success, message = mvsim_wire.answer(reply)
        except ValueError as exc:
            raise OutcomeUnknown("the answer of set_controller_twist does not parse; the setpoint may have been "
                                 "applied") from exc
        if not success:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"set_controller_twist refused the setpoint: {message[:200]}")

    @action(name="x-cap.mrpt.mvsim_controller_twist.v1", risk="R2",
            description="Hand one twist setpoint (vx, wz) to the vehicle's controller through MVSim's "
                        "set_controller_twist service; the setpoint persists until another command",
            input={"vx": Field("number", unit="m/s", limit=_VX_LIMIT,
                               description="Linear velocity setpoint along the vehicle's local x axis"),
                   "wz": Field("number", unit="rad/s", limit=_WZ_LIMIT,
                               description="Angular velocity setpoint about the vehicle's vertical axis")},
            output={"accepted": Field("boolean", description="True when MVSim answered that the controller "
                                                             "accepted the setpoint"),
                    "vx": Field("number", unit="m/s", description="The linear velocity setpoint the controller accepted"),
                    "wz": Field("number", unit="rad/s",
                                description="The angular velocity setpoint the controller accepted")},
            examples=[{"vx": 0.0, "wz": 0.0}])
    def set_twist(self, vx, wz):
        self._send_twist(vx, wz)
        return {"accepted": True, "vx": vx, "wz": wz}

    @action(name="x-cap.mrpt.mvsim_pose.v1", verb="read",
            description="Read the vehicle's pose, twist and collision flag through MVSim's get_pose service; the "
                        "call also makes the next simulation step reset the vehicle's own hadCollision flag, which "
                        "the ROS node's collision topic reads",
            output={"pose": _POSE, "twist": _TWIST,
                    "in_collision": Field("boolean", description=(
                        "get_pose's objectIsInCollision: whether MVSim's step copy has recorded a collision of the "
                        "vehicle; the clone only ever adds to that record, so it stays true after the first one"))})
    def read_pose(self):
        try:
            reply = self.native.callService("get_pose", mvsim_wire.get_pose(self._vehicle()))
            answer = mvsim_wire.pose_answer(reply)
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the answer of get_pose does not parse") from exc
        if not answer["success"] or answer["pose"] is None or answer["twist"] is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"get_pose answered no pose for the vehicle: {answer['error'][:200]}")
        twist = answer["twist"]
        return {"pose": answer["pose"], "twist": {"vx": twist["vx"], "vy": twist["vy"], "wz": twist["wz"]},
                "in_collision": answer["collision"]}

    @estop(native="set_controller_twist")
    def stop(self):
        # A zero twist setpoint, acknowledged by the controller (World_services.cpp:124-170); any failure raises, so
        # the runtime reports the safe state unreached and keeps retrying with the latch held.
        self._send_twist(0.0, 0.0)

    def teardown(self):
        self.native.shutdown()
