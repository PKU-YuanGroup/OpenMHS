"""ROS-free recording fake for the pinned ros2_raspicam_node wire contract.

The fake answers the one fixed rosbridge subscription this driver declares:
``/raspicam/raspicam_compressed`` with a ``sensor_msgs/msg/CompressedImage``
message.  The message carries a decoded-pixel payload and the ROS 2 header
shape the upstream node emits.  It contacts no ROS graph and no camera.

The 2x2 JPEG is synthesized test data, not a replay of captured ROS traffic.
It is deliberately smaller than any real deployment frame; the pinned node's
image size is whatever its ``camera_image_width`` and ``camera_image_height``
parameters select.  The frame id and stamp are placeholders too.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: A 2x2 solid-colour JPEG used only as fake image payload.  # placeholder
_PLACEHOLDER_JPEG = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDA"
    "xNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIE"
    "AwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpT"
    "VFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ"
    "2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3"
    "AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpj"
    "ZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn"
    "6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDzWiiivSOA/9k="
)


class FakeRos2Raspicam(RecordingRosTransport):
    def __init__(self, *, malformed_image: bool = False, **_options):
        super().__init__(handler=self._respond)
        self.frame_id = "0"                  # placeholder frame number
        self.sec = 0                         # placeholder ROS 2 stamp seconds
        self.nanosec = 0                     # placeholder ROS 2 stamp nanoseconds
        self.image_data = _PLACEHOLDER_JPEG  # placeholder
        self.malformed_image = bool(malformed_image)  # placeholder negative-path switch
        self.subscription_count = 0           # placeholder counter

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        topic = message.get("topic")
        if topic != "/raspicam/raspicam_compressed":
            return None
        self.subscription_count += 1
        data = "not a jpeg" if self.malformed_image else self.image_data  # placeholder
        return {
            "op": "publish",
            "topic": topic,
            "id": message.get("id"),
            "msg": {
                "header": {
                    "stamp": {"sec": self.sec, "nanosec": self.nanosec},  # placeholder
                    "frame_id": self.frame_id,  # placeholder
                },
                "format": "jpeg",  # placeholder, mirrors the pinned publisher
                "data": data,
            },
        }
