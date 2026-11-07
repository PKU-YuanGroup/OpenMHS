"""ROS-free recording fake for the realsense2_camera ROS 2 endpoints.

The fake models the pinned rosbridge contract: a subscriber receives one message per subscription on the
declared topic (color and depth Image, CameraInfo and Metadata, the opt-in depth/color/points PointCloud2) and a
caller receives ``realsense2_camera_msgs/srv/DeviceInfo`` response values.  Every value is controlled test data,
not a device fact: the samples are deliberately small and nonconstant, their geometry, stride and calibration are
fixtures, and nothing here measures a camera, a native frame rate, producer age or synchronization.  Independent
topics answer independently.  The original metadata-only switches remain for the original test cases.
"""

import copy
import struct

from mhs.bridge.ros_transport import RecordingRosTransport

COLOR_INFO = "/camera/camera/color/camera_info"
COLOR_METADATA = "/camera/camera/color/metadata"
DEVICE_INFO = "/camera/camera/device_info"
COLOR_IMAGE = "/camera/camera/color/image_raw"
DEPTH_IMAGE = "/camera/camera/depth/image_rect_raw"
DEPTH_INFO = "/camera/camera/depth/camera_info"
DEPTH_METADATA = "/camera/camera/depth/metadata"
POINTS = "/camera/camera/depth/color/points"


def _stamp(sec, nanosec):
    return {"sec": sec, "nanosec": nanosec}


def _color_sample():
    # placeholder 5x3 RGB8 frame, step = width * 3 as the node publishes it
    data = [(x * 37 + y * 11 + c * 83) % 256 for y in range(3) for x in range(5) for c in range(3)]
    return {"header": {"stamp": _stamp(1730000000, 125000000), "frame_id": "camera_color_optical_frame"},
            "height": 3, "width": 5, "encoding": "rgb8", "is_bigendian": 0, "step": 15, "data": data}


def _depth_sample():
    # placeholder 4x2 16UC1 frame, little-endian (is_bigendian 0) as the node publishes it
    values = [0, 1, 513, 4095, 65535, 1200, 32768, 77]
    data = list(b"".join(struct.pack("<H", value) for value in values))
    return {"header": {"stamp": _stamp(1730000000, 125000123), "frame_id": "camera_depth_optical_frame"},
            "height": 2, "width": 4, "encoding": "16UC1", "is_bigendian": 0, "step": 8, "data": data}


def _points_sample():
    # placeholder unordered cloud: x, y, z FLOAT32 and a packed rgb field, point_step 16, height 1, is_dense true
    data = bytearray()
    for index in range(3):
        data += struct.pack("<fff", 0.1 * index, -0.05 * index, 0.5 + 0.25 * index)
        data += bytes((10 + index, 20 + index, 30 + index, 0))
    fields = [{"name": name, "offset": offset, "datatype": 7, "count": 1}
              for name, offset in (("x", 0), ("y", 4), ("z", 8), ("rgb", 12))]
    return {"header": {"stamp": _stamp(1730000000, 125000456), "frame_id": "camera_depth_optical_frame"},
            "height": 1, "width": 3, "fields": fields, "is_bigendian": False, "point_step": 16,
            "row_step": 48, "data": list(data), "is_dense": True}


class FakeRealsenseRos(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond, max_message_bytes=16 * 1024 * 1024)
        self.frame_id = "fake_color_optical_frame"  # placeholder
        self.width = 640  # placeholder
        self.height = 480  # placeholder
        self.distortion_model = "plumb_bob"  # placeholder
        self.binning_x = 0  # placeholder
        self.binning_y = 0  # placeholder
        self.metadata_json = '{"FrameNumber":"1","Exposure":"156"}'  # placeholder
        self.device_info = {
            "device_name": "Intel RealSense D455",  # placeholder
            "serial_number": "000000000000",  # placeholder
            "firmware_version": "5.13.0.50",  # placeholder
            "usb_type_descriptor": "3.2",  # placeholder
            "firmware_update_id": "0" * 32,  # placeholder
            "sensors": "Stereo Module,RGB Camera",  # placeholder
            "physical_port": "/sys/devices/fake/usb1",  # placeholder
        }
        self.publish_camera_info = True  # placeholder negative-path switch
        self.publish_metadata = True  # placeholder negative-path switch
        self.include_frame_id = True  # placeholder negative-path switch
        self.include_width = True  # placeholder negative-path switch
        self.include_metadata_json = True  # placeholder negative-path switch
        self.device_info_ok = True  # placeholder negative-path switch
        self.include_serial = True  # placeholder negative-path switch
        # Complete default-profile samples (model review); every value is a placeholder fixture.
        self.images = {COLOR_IMAGE: _color_sample(), DEPTH_IMAGE: _depth_sample()}  # placeholder
        self.points = _points_sample()  # placeholder
        self.depth_metadata_json = '{"frame_number":7,"clock_domain":"global_time"}'  # placeholder
        self.depth_info = {  # placeholder depth calibration and ROI, deliberately nonconstant and complete
            "header": {"stamp": _stamp(1730000000, 125000123), "frame_id": "camera_depth_optical_frame"},
            "height": 2, "width": 4, "distortion_model": "plumb_bob",
            "d": [0.0, 0.0, 0.0, 0.0, 0.0],
            "k": [380.5, 0.0, 1.75, 0.0, 380.25, 0.5, 0.0, 0.0, 1.0],
            "r": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            "p": [380.5, 0.0, 1.75, 0.0, 0.0, 380.25, 0.5, 0.0, 0.0, 0.0, 1.0, 0.0],
            "binning_x": 0, "binning_y": 0,
            "roi": {"x_offset": 0, "y_offset": 0, "height": 0, "width": 0, "do_rectify": False},
        }
        self.silent_topics = set()  # placeholder negative-path control: topics that never publish
        self.overrides = {}  # placeholder malformed-packet control: topic -> exact message to publish

    def _camera_info_message(self):
        message = {
            "header": {"stamp": _stamp(1730000000, 125000000)},  # placeholder
            "height": self.height,
            "width": self.width,
            "distortion_model": self.distortion_model,
            "d": [0.11, -0.03, 0.004, 0.002, 0.001],  # placeholder
            "k": [615.0, 0.0, 320.5, 0.0, 615.5, 240.25, 0.0, 0.0, 1.0],  # placeholder
            "r": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],  # placeholder
            "p": [615.0, 0.0, 320.5, 0.0, 0.0, 615.5, 240.25, 0.0, 0.0, 0.0, 1.0, 0.0],  # placeholder
            "binning_x": self.binning_x,
            "binning_y": self.binning_y,
            "roi": {"x_offset": 0, "y_offset": 0, "height": 0, "width": 0, "do_rectify": False},  # placeholder
        }
        if self.include_frame_id:
            message["header"]["frame_id"] = self.frame_id
        if not self.include_width:
            message.pop("width", None)
        return message

    def _metadata_message(self):
        message = {"header": {"stamp": _stamp(1730000000, 125000000),  # placeholder
                              "frame_id": "camera_color_optical_frame"}}  # placeholder
        if self.include_metadata_json:
            message["json_data"] = self.metadata_json
        return message

    def _topic_message(self, topic):
        if topic in self.overrides:
            return self.overrides[topic]
        if topic == COLOR_INFO:
            return self._camera_info_message() if self.publish_camera_info else None
        if topic == COLOR_METADATA:
            return self._metadata_message() if self.publish_metadata else None
        if topic in self.images:
            return self.images[topic]
        if topic == DEPTH_INFO:
            return self.depth_info
        if topic == DEPTH_METADATA:
            return {"header": {"stamp": _stamp(1730000000, 125000123),  # placeholder
                               "frame_id": "camera_depth_optical_frame"},  # placeholder
                    "json_data": self.depth_metadata_json}
        if topic == POINTS:
            return self.points
        return None

    def _respond(self, message):
        op = message.get("op")
        if op == "subscribe":
            topic = message.get("topic")
            if topic in self.silent_topics:
                return None
            msg = self._topic_message(topic)
            if msg is None:
                return None
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": copy.deepcopy(msg),
            }
        if op == "call_service" and message.get("service") == DEVICE_INFO:
            if not self.device_info_ok:
                return {
                    "op": "service_response",
                    "service": DEVICE_INFO,
                    "id": message.get("id"),
                    "result": False,
                    "values": {},
                }
            values = dict(self.device_info)
            if not self.include_serial:
                values.pop("serial_number", None)
            return {
                "op": "service_response",
                "service": DEVICE_INFO,
                "id": message.get("id"),
                "result": True,
                "values": values,
            }
        return None
