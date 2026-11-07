"""ROS-free canned fake for the quad_sim observation topics.

The fake models the pinned wire contract only: a geometry_msgs/PoseStamped
publication on /ground_truth_to_tf/pose and an actionlib_msgs/GoalStatusArray
publication on /move_base/status.  It opens no ROS connection, starts no
Gazebo, PX4 SITL, MAVROS, gmapping, cartographer or move_base process and runs
no physics, navigation or wall-clock loop.  Every value below is test data,
not a device fact or a bound.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_POSE_TOPIC = "/ground_truth_to_tf/pose"
_STATUS_TOPIC = "/move_base/status"


class FakeQuadSim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.stamp_secs = 12                  # placeholder
        self.stamp_nsecs = 340000000          # placeholder
        self.frame_id = "world"               # placeholder
        self.position = {"x": 1.0, "y": 2.0, "z": 0.3}                 # placeholder
        self.orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}    # placeholder
        self.goal_id = "goal-1"               # placeholder
        self.goal_status = 1                  # placeholder
        self.goal_text = "active"             # placeholder
        self.goal_stamp = {"secs": 11, "nsecs": 0}  # placeholder

        # Negative-path switches used by the repository tests.
        self.silent_topic = None      # placeholder: emit no publication
        self.malformed_topic = None   # placeholder: emit an incomplete message
        self.wrong_id = False         # placeholder: emit an unrelated subscription id
        self.fail_subscribe = False   # placeholder: simulate a broken transport link
        self.subscriptions = []       # placeholder request log
        self.last_subscribe = None    # placeholder echo of the received request

    def _stamp(self):
        return {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs}  # placeholder

    def _pose_message(self):
        message = {
            "header": {"seq": 1, "stamp": self._stamp(), "frame_id": self.frame_id},
            "pose": {
                "position": dict(self.position),
                "orientation": dict(self.orientation),
            },
        }
        if self.malformed_topic == _POSE_TOPIC:
            message.pop("pose")
        return message

    def _status_message(self):
        message = {
            "header": {"seq": 1, "stamp": self._stamp(), "frame_id": ""},
            "status_list": [
                {
                    "goal_id": {"id": self.goal_id, "stamp": dict(self.goal_stamp)},
                    "status": self.goal_status,
                    "text": self.goal_text,
                },
            ],
        }
        if self.malformed_topic == _STATUS_TOPIC:
            message["status_list"][0]["status"] = "not-an-integer"  # placeholder
        return message

    def _publish(self, topic, request, message):
        event = {"op": "publish", "topic": topic, "id": request.get("id"), "msg": message}
        if self.wrong_id:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event

    def _respond(self, message):
        operation = message.get("op")
        if operation != "subscribe":
            return None
        self.subscriptions.append(dict(message))
        self.last_subscribe = dict(message)
        topic = message.get("topic")
        if topic not in (_POSE_TOPIC, _STATUS_TOPIC):
            return None
        if self.fail_subscribe:
            raise ConnectionError("simulated subscription failure")  # placeholder
        if topic == self.silent_topic:
            return None
        if topic == _POSE_TOPIC:
            return self._publish(topic, message, self._pose_message())
        return self._publish(topic, message, self._status_message())
