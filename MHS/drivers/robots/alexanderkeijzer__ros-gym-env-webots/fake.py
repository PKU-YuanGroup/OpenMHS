"""ROS-free fake for the Webots gym_env bridge endpoints.

The fake models the pinned upstream wire contract: one subscription on
/joint_sensors/value (gym_env/SensorMessage), one publication on
/joint_actuators/value (gym_env/ActuatorMessage), and the /webots/step,
/webots/reset and /reward service calls.  An action publication updates the
fake's copy of the node's setpoints with the node's own arithmetic
(actuatorCommandCallback, src/gym_env_webots_node.cpp:117-125: add
motorRange*action/20, clamp to [motorMin, motorMax], call set_position); a
step moves each fake joint to its last set_position target.  With the
``action_after_step`` switch the fake runs the next step before the action
callback, as the live node may (the publication and the step call reach it on
different ROS connections).  The joint limits,
start positions and reward are placeholder test data, not device facts.  It
runs no Webots engine, joint controller, physics, contact, sensor or
wall-clock loop.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: Joint limits in panda_joint1..7, panda_finger_joint1..2 order: placeholders
#: copied from the Panda PROTO's RotationalMotor/LinearMotor min/maxPosition
#: (the finger minimum is not stated there and is a placeholder 0); the node
#: reads the live values through get_min_position/get_max_position.
_MIN = [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973, 0.0, 0.0]  # placeholder
_MAX = [2.8973, 1.7628, 2.8973, 0.006, 2.8973, 3.7525, 2.8973, 0.04, 0.04]  # placeholder

#: initActuators stores max-1e-5 and min+1e-5 and range as their difference
#: (src/gym_env_webots_node.cpp:136-140).
_MOTOR_MIN = [value + 1e-5 for value in _MIN]  # placeholder
_MOTOR_MAX = [value - 1e-5 for value in _MAX]  # placeholder
_MOTOR_RANGE = [high - low for low, high in zip(_MOTOR_MIN, _MOTOR_MAX)]  # placeholder

#: Nine placeholder start positions.
_JOINT_POSITIONS = [0.0] * 9  # placeholder

#: Placeholder reward returned by the fake /reward service.
_REWARD = 0.0  # placeholder


class FakeRosGymEnvWebots(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.published_actions = []       # placeholder test record
        self.step_calls = 0               # placeholder test record
        self.reset_calls = 0              # placeholder test record
        self.reward_calls = 0             # placeholder test record
        self.joint_positions = list(_JOINT_POSITIONS)  # placeholder state
        #: the node's motorSetPoints (initialised to zero, src/gym_env_webots_node.cpp:31)
        self.set_points = [0.0] * 9       # placeholder state
        #: the last set_position target of each Webots motor
        self.targets = list(_JOINT_POSITIONS)  # placeholder state
        self.reward = _REWARD             # placeholder state
        self.fail_step_service = False    # placeholder negative-path switch
        self.reject_step_application = False  # placeholder negative-path switch
        self.fail_reset_service = False   # placeholder negative-path switch
        self.fail_reward_service = False  # placeholder negative-path switch
        self.silent_sensors = False       # placeholder negative-path switch: no sample after a step
        self.action_after_step = False    # placeholder switch: the step runs before the action callback
        self._late_actions = []           # actions held for the action_after_step switch

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/joint_sensors/value" and not self.silent_sensors:
                return {
                    "op": "publish",
                    "topic": "/joint_sensors/value",
                    "id": message.get("id"),
                    "msg": {"observations": list(self.joint_positions)},  # placeholder
                }
            return None
        if operation == "publish":
            if message.get("topic") == "/joint_actuators/value":
                body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
                actions = body.get("actions") if isinstance(body.get("actions"), list) else []
                self.published_actions.append(list(actions))  # placeholder record
                if self.action_after_step:
                    self._late_actions.append(list(actions))
                else:
                    self._actuate(actions)
            return None
        if operation == "call_service":
            return self._service(message)
        return None

    def _actuate(self, actions):
        # actuatorCommandCallback: setpoint += range*action/20, clamped, then set_position per joint.
        for index, action in enumerate(actions[:9]):
            point = self.set_points[index] + _MOTOR_RANGE[index] * float(action) / 20
            point = min(max(point, _MOTOR_MIN[index]), _MOTOR_MAX[index])
            self.set_points[index] = point
            self.targets[index] = point

    def _service(self, message):
        service = message.get("service")
        if service == "/webots/step":
            self.step_calls += 1
            if self.fail_step_service:
                return self._response(message, result=False, values={})
            if self.reject_step_application:
                return self._response(message, result=True, values={"rejected": True})
            self.joint_positions = list(self.targets)  # placeholder dynamics: reach the target in one step
            late, self._late_actions = self._late_actions, []
            for actions in late:  # the action callback runs after the step (action_after_step)
                self._actuate(actions)
            return self._response(message, result=True, values={})
        if service == "/webots/reset":
            self.reset_calls += 1
            if self.fail_reset_service:
                return self._response(message, result=False, values={})
            # Webots resets the world (placeholder start positions and targets); the node's setpoints survive.
            self.joint_positions = list(_JOINT_POSITIONS)  # placeholder reset state
            self.targets = list(_JOINT_POSITIONS)  # placeholder reset state
            return self._response(message, result=True, values={})
        if service == "/reward":
            self.reward_calls += 1
            if self.fail_reward_service:
                return self._response(message, result=False, values={})
            return self._response(message, result=True, values={"reward": self.reward})  # placeholder
        return self._response(message, result=False, values={})

    @staticmethod
    def _response(request, *, result, values):
        return {
            "op": "service_response",
            "service": request.get("service"),
            "id": request.get("id"),
            "result": result,
            "values": values,
        }
