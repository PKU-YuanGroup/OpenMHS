"""ROS-free scripted transport for the fixed experiment-camera image topic.

The fake models the pinned ROS 1 wire contract: one
``sensor_msgs/Image`` sample on ``/experiment_camera/image_raw`` for each
subscription.  All dimensions, pixels, timestamps and negative-path values
below are placeholders and explicit test data, not device facts or a
captured recording.  No ROS, Gazebo, camera or image codec is executed.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport

TOPIC = "/experiment_camera/image_raw"


class FakeMobipickExperimentCamera(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond, max_message_bytes=16 * 1024 * 1024)
        self.subscriptions = 0                # placeholder counter
        self.silent = False                   # placeholder negative-path switch
        self.encoding = "rgb8"                # placeholder encoding selector
        self.frame_id = "experiment_camera_link"  # placeholder frame identity
        self.image = {                        # placeholder 4x3 RGB8 sample
            "header": {
                "seq": 7,                     # placeholder
                "stamp": {"secs": 1700000000, "nsecs": 123456789},  # placeholder
                "frame_id": self.frame_id,
            },
            "height": 3,                      # placeholder
            "width": 4,                       # placeholder
            "encoding": self.encoding,
            "is_bigendian": 0,                # placeholder
            "step": 12,                       # placeholder
            "data": [                         # placeholder nonconstant RGB8 pixels
                0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255,
                255, 255, 0, 0, 255, 255, 255, 0, 255, 32, 64, 96,
                128, 160, 192, 224, 32, 64, 96, 128, 160, 192, 224, 255,
            ],
        }

    def _respond(self, message):
        if message.get("op") != "subscribe" or message.get("topic") != TOPIC:
            return None
        self.subscriptions += 1
        if self.silent:
            return None
        image = copy.deepcopy(self.image)
        image["encoding"] = self.encoding
        return {
            "op": "publish",
            "topic": TOPIC,
            "id": message.get("id"),
            "msg": image,
        }
