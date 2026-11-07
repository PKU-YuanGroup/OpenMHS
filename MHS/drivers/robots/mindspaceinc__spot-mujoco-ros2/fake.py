"""ROS-free analytic fake for the pinned Spot MuJoCo ROS 2 wire contract.

It models the endpoints declared in ``driver.py``:

* an advertise and a publish of ``communication/msg/ActuatorCmds`` on
  ``/simulation/actuators_cmds``;
* a fresh ``sensor_msgs/msg/JointState`` sample on ``/simulation/joint_states``;
* the acknowledged ``communication/srv/SimulationReset`` service on
  ``/simulation/sim_reset``.

It is an analytic contract stand-in, not a recording of captured traffic and
not the upstream simulation executable: it runs no MuJoCo physics, PD law,
contact, actuator dynamics, sensor or timer.  It keeps the last command and a
placeholder joint state in plain attributes so a publication or reset has an
observable contract effect.  Every number below is test data and is marked
``# placeholder``; none is a device fact or a safety limit.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: The upstream model's 12 hinge/actuator names, repeated here as placeholder
#: sample data.  The names occur in the pinned MJCF, but these samples are not
#: a measurement of the live node's journal.
_JOINT_NAMES = (
    "fl.hx", "fl.hy", "fl.kn",
    "fr.hx", "fr.hy", "fr.kn",
    "hl.hx", "hl.hy", "hl.kn",
    "hr.hx", "hr.hy", "hr.kn",
)


class FakeSpotMujocoRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.joint_names = list(_JOINT_NAMES)          # placeholder sample names
        self.joint_positions = [0.0] * 12              # placeholder
        self.joint_velocities = [0.0] * 12             # placeholder
        self.joint_efforts = [0.0] * 12                # placeholder
        self.base_position = (0.0, 0.0, 0.7)           # placeholder
        self.base_orientation = (0.0, 0.0, 0.0, 1.0)   # placeholder
        self.last_command = None                       # recorded wire message, no physical meaning
        self.commands = []                             # recording helper, no device meaning
        self.reset_requests = []                       # recording helper, no device meaning
        self.fail_reset_service = False                # placeholder negative-path switch
        self.fail_reset_application = False            # placeholder negative-path switch
        self.malformed_reset = False                   # placeholder negative-path switch
        self.malformed_joint_state = False             # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "call_service":
            return self._service(message)
        # advertise, publish, unsubscribe: the bridge needs no response.
        if operation == "publish":
            self._record_command(message)
        return None

    def _observation(self, message):
        if message.get("topic") != "/simulation/joint_states":
            return None
        if self.malformed_joint_state:
            return {"op": "publish", "topic": message.get("topic"), "id": message.get("id"),
                    "msg": "malformed"}  # placeholder
        return {
            "op": "publish",
            "topic": message.get("topic"),
            "id": message.get("id"),
            "msg": {
                # ROS 2 std_msgs/Header (stamp sec/nanosec); placeholder values.
                "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "spot"},  # placeholder
                "name": list(self.joint_names),  # placeholder
                "position": list(self.joint_positions),  # placeholder
                "velocity": list(self.joint_velocities),  # placeholder
                "effort": list(self.joint_efforts),  # placeholder
            },
        }

    def _service(self, message):
        service = message.get("service")
        if service != "/simulation/sim_reset":
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}  # placeholder
        if self.fail_reset_service:
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}  # placeholder
        request = message.get("args") if isinstance(message.get("args"), dict) else {}
        header = request.get("header") if isinstance(request.get("header"), dict) else {}
        if header.get("frame_id") != "spot":
            # The upstream callback rejects a frame_id that is not the model name.
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": {"is_success": False}}  # placeholder
        if self.fail_reset_application:
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": {"is_success": False}}  # placeholder
        if self.malformed_reset:
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": True, "values": "malformed"}  # placeholder
        self._apply_reset(request)
        return {"op": "service_response", "service": service, "id": message.get("id"),
                "result": True, "values": {"is_success": True}}  # placeholder

    def _record_command(self, message):
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        self.last_command = body
        self.commands.append(body)
        # Analytic contract effect only.  The real node's joint feedback moves
        # under the PD law and physics.  The fake evaluates a small placeholder
        # first-order nudge of the same PD expression so an input change is
        # observable; this is not the node's data.ctrl and not physics.
        kp = body.get("kp") if isinstance(body.get("kp"), list) else []
        pos = body.get("pos") if isinstance(body.get("pos"), list) else []
        kd = body.get("kd") if isinstance(body.get("kd"), list) else []
        vel = body.get("vel") if isinstance(body.get("vel"), list) else []
        torque = body.get("torque") if isinstance(body.get("torque"), list) else []
        size = len(self.joint_positions)
        if not all(len(values) == size for values in (kp, pos, kd, vel, torque)):
            return
        positions = []
        efforts = []
        for index in range(size):
            ctrl = (float(kp[index]) * (float(pos[index]) - self.joint_positions[index])
                    + float(kd[index]) * (float(vel[index]) - self.joint_velocities[index])
                    + float(torque[index]))
            ctrl = max(-100.0, min(100.0, ctrl))
            positions.append(self.joint_positions[index] + 0.001 * ctrl)  # placeholder factor
            efforts.append(ctrl)  # placeholder
        self.joint_positions = positions
        self.joint_velocities = [float(value) for value in vel]  # placeholder
        self.joint_efforts = efforts

    def _apply_reset(self, request):
        self.reset_requests.append(request)
        base = request.get("base_pose") if isinstance(request.get("base_pose"), dict) else {}
        position = base.get("position") if isinstance(base.get("position"), dict) else {}
        orientation = base.get("orientation") if isinstance(base.get("orientation"), dict) else {}
        self.base_position = (
            float(position.get("x", 0.0)),  # placeholder default
            float(position.get("y", 0.0)),  # placeholder default
            float(position.get("z", 0.7)),  # placeholder default
        )
        self.base_orientation = (
            float(orientation.get("x", 0.0)),  # placeholder default
            float(orientation.get("y", 0.0)),  # placeholder default
            float(orientation.get("z", 0.0)),  # placeholder default
            float(orientation.get("w", 1.0)),  # placeholder default
        )
        joint_state = request.get("joint_state") if isinstance(request.get("joint_state"), dict) else {}
        names = joint_state.get("name") if isinstance(joint_state.get("name"), list) else []
        positions = joint_state.get("position") if isinstance(joint_state.get("position"), list) else []
        if names and positions:
            self.joint_names = [str(name) for name in names]  # placeholder sample names
            self.joint_positions = [float(value) for value in positions]  # placeholder
        else:
            # mj_resetData would restore the model's hinge defaults; the fake uses
            # zero placeholder positions for all 12 joints.
            self.joint_names = list(_JOINT_NAMES)
            self.joint_positions = [0.0] * 12  # placeholder
        self.joint_velocities = [0.0] * len(self.joint_positions)  # placeholder
        self.joint_efforts = [0.0] * len(self.joint_positions)  # placeholder
        self.last_command = None
