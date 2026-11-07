"""ROS-free event-driven contract fake for the KUKA LWR simulation endpoints.

The fake models only the pinned wire contract used by ``driver.py``: a
``sensor_msgs/JointState`` publication on ``/joint_states``, the
``iai_control_msgs/MultiJointVelocityImpedanceCommand`` publication on
``/r_arm_vel/command``, and stamped
``pr2_controllers_msgs/JointTrajectoryControllerState`` samples on
``/r_arm_vel/state`` for the sensed-confirmation stop.  It is an analytic
stand-in, not a replay of captured traffic; it runs no ROS graph, loopback
controller manager, PR2/IAI controller, URDF model, physics engine or RViz.

Every number below is test data, not a device fact, and is marked
``# placeholder``.  A confirmation burst sets the measured joint velocity
equal to the commanded velocity at once.  That is not the loopback
integration and not the controller watchdog.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: Placeholder joint names in the configured controller order (test data).
_JOINT_NAMES = [
    "right_arm_0_joint",
    "right_arm_1_joint",
    "right_arm_2_joint",
    "right_arm_3_joint",
    "right_arm_4_joint",
    "right_arm_5_joint",
    "right_arm_6_joint",
]

_JOINTS = 7                 # placeholder joint count
_BURST = 4                  # placeholder samples per /r_arm_vel/state subscription
_DT_NS = 50_000_000         # placeholder producer-stamp step (50 ms)
_CLOCK_NS = 1_000_000_000   # placeholder clock; a zero stamp is invalid
_MOVING = [0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder joint velocity before the zero request


class FakeKukaRvizSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.positions = [0.0] * _JOINTS          # placeholder
        self.velocities = [0.0] * _JOINTS         # placeholder joint-state echo
        self.efforts = [0.0] * _JOINTS            # placeholder
        self.seq = 1                              # placeholder fixed ROS 1 header sequence
        self.commanded_velocities = []            # placeholder recorded publication
        # Placeholder controller state.  desired is the applied command; actual is the measured velocity.
        # Both start away from zero so a confirmation depends on the zero-velocity request.
        self.applied_desired = list(_MOVING)      # placeholder
        self.measured_actual = list(_MOVING)      # placeholder
        self.clock_ns = _CLOCK_NS                 # placeholder simulated clock
        self.silent_joint_states = False          # placeholder negative-path switch
        self.omit_joint_state_position = False    # placeholder negative-path switch
        self.silent_arm_state = False             # placeholder: /r_arm_vel/state answers nothing
        self.frozen_stamps = False                # placeholder: every state sample repeats one stamp
        self.null_actual_velocity = False         # placeholder: actual.velocities[0] is null
        self.competing_command = False            # placeholder: another publisher keeps a nonzero command
        self.unsettled_actual = False             # placeholder: desired follows the command, actual stays moving

    def _joint_state(self, ident):
        # A ROS 1 sensor_msgs/JointState always carries a std_msgs/Header
        # (seq, secs/nsecs); the fixed sequence keeps two resource reads stable.
        message = {
            "header": {"seq": self.seq, "stamp": {"secs": 0, "nsecs": 0},  # placeholder
                       "frame_id": ""},                                     # placeholder
            "name": list(_JOINT_NAMES),
            "velocity": list(self.velocities),     # placeholder
            "effort": list(self.efforts),          # placeholder
        }
        if not self.omit_joint_state_position:
            message["position"] = list(self.positions)  # placeholder
        return {
            "op": "publish",
            "topic": "/joint_states",
            "id": ident,
            "msg": message,
        }

    def _stamp(self):
        if self.frozen_stamps:
            return {"secs": 1, "nsecs": 0}  # placeholder repeated producer stamp
        return {"secs": self.clock_ns // 1_000_000_000, "nsecs": self.clock_ns % 1_000_000_000}

    def _arm_sample(self, ident):
        actual = list(self.measured_actual)
        if self.null_actual_velocity:
            actual[0] = None  # placeholder missing measurement
        message = {
            "header": {"seq": 0, "stamp": self._stamp(), "frame_id": ""},  # placeholder
            "joint_names": list(_JOINT_NAMES),
            "desired": {"velocities": list(self.applied_desired)},  # placeholder applied command
            "actual": {"positions": list(self.positions), "velocities": actual},  # placeholder
            "error": {"velocities": [0.0] * _JOINTS},  # placeholder
        }
        if not self.frozen_stamps:
            self.clock_ns += _DT_NS
        return {"op": "publish", "topic": "/r_arm_vel/state", "id": ident, "msg": message}

    def _arm_burst(self, ident):
        if self.competing_command:
            # Placeholder: lasa_to_iai or the position controller overwrites the applied command.
            self.applied_desired = list(_MOVING)
            self.measured_actual = list(_MOVING)
        return [self._arm_sample(ident) for _ in range(_BURST)]

    def _record_command(self, message):
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        velocity = body.get("velocity")
        if not isinstance(velocity, list):
            return
        self.commanded_velocities = list(velocity)  # placeholder recorded command
        # Analytic contract echo only: the fake does not integrate the loopback
        # model or claim that the arm moved.
        self.velocities = list(velocity)  # placeholder joint-state echo
        if self.competing_command:
            self.applied_desired = list(_MOVING)  # placeholder
            self.measured_actual = list(_MOVING)  # placeholder
        elif self.unsettled_actual:
            self.applied_desired = list(velocity)  # placeholder applied command
            self.measured_actual = list(_MOVING)   # placeholder velocity_ that did not settle
        else:
            self.applied_desired = list(velocity)  # placeholder
            self.measured_actual = list(velocity)  # placeholder immediate echo, not the loopback

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == "/joint_states":
                if self.silent_joint_states:
                    return None
                return self._joint_state(message.get("id"))
            if topic == "/r_arm_vel/state":
                if self.silent_arm_state:
                    return None
                return self._arm_burst(message.get("id"))
            return None
        if operation == "publish":
            if message.get("topic") == "/r_arm_vel/command":
                self._record_command(message)
            return None
        return None
