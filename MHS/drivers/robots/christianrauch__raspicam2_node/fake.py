"""ROS-free protocol fake for the pinned raspicam2_node wire contract.

The fake answers the two fixed rosbridge subscriptions the driver declares:
``/camera/image/compressed`` with a ``sensor_msgs/msg/CompressedImage`` JPEG
message and ``/camera/image/camera_info`` with a CameraInfo-shaped message
carrying the geometry fields the driver reads.  It contacts no ROS graph and
no camera.  The responses are synthesized from placeholder data; this is not
a replay of captured ROS traffic.

Every value below is test data, not a device fact.  The 2x2 placeholder JPEG
is deliberately smaller than any real camera frame; the pinned node's size is
whatever the deployment configures.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: A 2x2 solid-colour JPEG used only as fake image payload (placeholder).
_PLACEHOLDER_JPEG = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYW"
    "ICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgo"
    "KCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcI"
    "CQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRol"
    "JicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ip"
    "qrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAA"
    "AAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLR"
    "ChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaX"
    "mJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEA"
    "PwD0Lwrpeny+F9HkksbV3ezhZmaFSSSgyScUUUV+cYr+NP1f5nk1fjl6n//Z"
)


class FakeRaspicam2Node(RecordingRosTransport):
    def __init__(self, *, malformed_image: bool = False, **_options):
        super().__init__(handler=self._respond)
        self.width = 2                        # placeholder
        self.height = 2                       # placeholder
        self.frame_id = "camera"              # placeholder
        self.image_data = _PLACEHOLDER_JPEG  # placeholder
        self.malformed_image = bool(malformed_image)  # placeholder negative-path switch
        self.subscription_count = 0           # placeholder counter

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        topic = message.get("topic")
        if topic == "/camera/image/compressed":
            self.subscription_count += 1
            data = "not a jpeg" if self.malformed_image else self.image_data  # placeholder
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": {
                    "header": {"frame_id": self.frame_id,  # placeholder
                               "stamp": {"secs": 0, "nsecs": 0}},  # placeholder
                    "format": "jpeg",  # placeholder
                    "data": data,
                },
            }
        if topic == "/camera/image/camera_info":
            self.subscription_count += 1
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": {
                    "header": {"frame_id": self.frame_id,  # placeholder
                               "stamp": {"secs": 0, "nsecs": 0}},  # placeholder
                    "height": self.height,  # placeholder
                    "width": self.width,    # placeholder
                    "distortion_model": "plumb_bob",  # placeholder
                    "d": [],  # placeholder
                    "k": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],  # placeholder
                    "r": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],  # placeholder
                    "p": [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],  # placeholder
                },
            }
        return None
