"""ROS-free analytic fake for the pinned SCARA/RRP ROS 2 endpoints.

The fake models the wire contract only: a ``sensor_msgs/JointState`` sample on
``/joint_states``, a ``std_msgs/String`` homogeneous matrix on ``/h_mat``, the
observational ``Forward_Velocity_Kinematics`` service, and the publication
input ``/forward_effort_controller/commands``.  It runs no Gazebo physics, no
controller, no FK/IK node and no wall-clock loop.  Every value below is test
data and is marked ``# placeholder``; none is a device fact or a safety limit.

The pinned clone exposes no acknowledged stop of its own.  The fake also
answers the companion gazebo_ros services ``/pause_physics`` and
``/get_model_list`` (the e-stop and its E1 stall read-back): a paused flag
stands for the Gazebo world's, and ``get_model_list`` stamps each answer with
a placeholder sim time that advances on every answer unless the flag is set.
While paused, ``/joint_states`` is silent, as the gzserver controller
manager's joint_state_broadcaster is; the ``wall_clock_joint_states`` switch
keeps it answering with stale samples instead, because the launch's standalone
``ros2_control_node`` may publish on the system clock (not settled by the
source).
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeScaraRobotRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.joint_names = ["joint1", "joint2", "joint3"]   # placeholder
        self.positions = [0.0, 0.0, 0.0]                     # placeholder
        self.velocities = [0.0, 0.0, 0.0]                    # placeholder
        self.efforts = [0.0, 0.0, 0.0]                       # placeholder
        self.stamp_secs = 12                                 # placeholder
        self.stamp_nsecs = 340000000                         # placeholder
        self.homogeneous_matrix = (                          # placeholder
            "1 0 0 0\n"
            "0 1 0 0\n"
            "0 0 1 0\n"
            "0 0 0 1\n"
        )
        self.published_efforts = []
        self.fail_service = False        # placeholder negative-path switch
        self.malformed_service = False   # placeholder negative-path switch
        self.silent_topics = False       # placeholder negative-path switch
        self.reject_publish = False      # placeholder negative-path switch
        self.paused = False              # placeholder: the fake world starts running
        self.sim_ns = 2_000_000_000      # placeholder sim time, advances 1 ms per answer while running
        self.fail_pause = False          # placeholder negative-path switch: the pause is not answered
        self.ignore_pause = False        # placeholder negative-path switch: the world keeps running
        self.fail_model_list = False     # placeholder negative-path switch: the read-back fails
        self.wall_clock_joint_states = False  # placeholder switch: /joint_states keeps answering while paused

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if self.silent_topics:
                return None
            topic = message.get("topic")
            if topic == "/joint_states":
                if self.paused and not self.wall_clock_joint_states:
                    return None  # the gzserver joint_state_broadcaster runs only from world updates
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {
                        "header": {
                            "stamp": {"sec": self.stamp_secs, "nanosec": self.stamp_nsecs},
                            "frame_id": "",
                        },
                        "name": list(self.joint_names),
                        "position": list(self.positions),
                        "velocity": list(self.velocities),
                        "effort": list(self.efforts),
                    },
                }
            if topic == "/h_mat":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {"data": self.homogeneous_matrix},
                }
            return None
        if operation == "advertise":
            return None
        if operation == "publish":
            if self.reject_publish:
                raise ConnectionError("fake publication rejected")
            if message.get("topic") == "/forward_effort_controller/commands":
                data = (message.get("msg") or {}).get("data")
                if isinstance(data, list):
                    self.published_efforts.append(list(data))
                    self.efforts = list(data)
                    # Placeholder contract effect: shift the reported joint
                    # positions by a tiny amount so the command is observable
                    # in the joint-state read.  This is not a physics step, a
                    # controller response or evidence that a real arm moved.
                    self.positions = [                       # placeholder
                        position + 0.000001 * effort
                        for position, effort in zip(self.positions, data)
                    ]
            return None
        if operation == "call_service":
            service = message.get("service")
            reply = {"op": "service_response", "service": service, "id": message.get("id"), "result": True}
            if service == "/pause_physics":
                if self.fail_pause:
                    return None  # no answer: the e-stop's request times out
                self.paused = True
                return dict(reply, values={})
            if service == "/get_model_list":
                if self.fail_model_list:
                    return dict(reply, result=False, values="get_model_list failed")  # placeholder
                if not self.paused or self.ignore_pause:
                    self.sim_ns += 1_000_000  # placeholder: a running world's sim time advances
                stamp = {"sec": self.sim_ns // 1_000_000_000, "nanosec": self.sim_ns % 1_000_000_000}
                return dict(reply, values={"header": {"stamp": stamp, "frame_id": ""},
                                           "model_names": ["ground_plane", "robot"], "success": True})  # placeholder
            if service == "/Forward_Velocity_Kinematics":
                if self.fail_service:
                    return dict(reply, result=False, values={})
                if self.malformed_service:
                    # The transport succeeded but the response shape is not a values object.
                    return dict(reply, values="not-an-object")  # placeholder malformed value
                return dict(reply, values={                    # placeholder values
                    "endeff_vel_x": 0.0,
                    "endeff_vel_y": 0.0,
                    "endeff_vel_z": 0.0,
                })
            return dict(reply, result=False, values={})
        return None
