"""ROS-free recording fake for the gazebo_grasp object-state endpoints.

The fake models the pinned wire contract: the ``object_msgs/ObjectInfo``
service on ``/gazebo_objects/get_info`` and one ``object_msgs/Object``
publication on ``/gazebo_objects``.  It is an in-memory stand-in, not a
recording of captured traffic and not a Gazebo world or plugin.

Every numeric value, object name and canned reply below is test data, marked
``# placeholder``; none is a device fact, a Limit or a reference.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_SERVICE = "/gazebo_objects/get_info"
_TOPIC = "/gazebo_objects"

#: Placeholder object set.  The real names and poses come from the operator's
#: Gazebo world and the pinned GazeboObjectInfo plugin.
_OBJECTS = {
    "cube1": {  # placeholder model name
        "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": "world"},
        "name": "cube1",  # placeholder
        "origin": {
            "position": {"x": 0.2, "y": 0.0, "z": 0.76},  # placeholder
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
        },
    },
    "cube2": {  # placeholder model name used only by the conformance alternate
        "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": "world"},
        "name": "cube2",  # placeholder
        "origin": {
            "position": {"x": -0.2, "y": 0.0, "z": 0.76},  # placeholder
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
        },
    },
}


class FakeGazeboGrasp(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.objects = {name: dict(value) for name, value in _OBJECTS.items()}
        self.silent = False                # placeholder: no fresh topic sample
        self.fail_service = False          # placeholder negative-path switch
        self.fail_application = False      # placeholder negative-path switch
        self.malformed_result = False      # placeholder negative-path switch
        self.calls = []                    # placeholder test record

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") != _TOPIC:
                return None
            if self.silent:
                return None
            return {
                "op": "publish",
                "topic": _TOPIC,
                "id": message.get("id"),
                "msg": self._first_object(),
            }
        if operation == "call_service":
            if message.get("service") == _SERVICE:
                return self._object_info(message)
            return {
                "op": "service_response",
                "service": message.get("service"),
                "id": message.get("id"),
                "result": False,
                "values": "placeholder unknown service",
            }
        if operation in ("advertise", "unadvertise", "unsubscribe", "publish"):
            return None
        return None

    def _object(self, name):
        obj = self.objects[name]
        # A shallow copy keeps the placeholder values independent of the
        # caller's mutation of the returned event.
        return {
            "header": dict(obj.get("header") or {}),
            "name": obj.get("name", name),
            "origin": {
                "position": dict((obj.get("origin") or {}).get("position") or {}),
                "orientation": dict((obj.get("origin") or {}).get("orientation") or {}),
            },
        }

    def _first_object(self):
        return self._object(sorted(self.objects)[0])

    def _object_info(self, message):
        self.calls.append(dict(message))
        if self.fail_service:
            return {
                "op": "service_response",
                "service": _SERVICE,
                "id": message.get("id"),
                "result": False,
                "values": "placeholder object-info service unavailable",
            }
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        name = args.get("name")
        if self.fail_application:
            return {
                "op": "service_response",
                "service": _SERVICE,
                "id": message.get("id"),
                "result": True,
                "values": {"success": False, "error_code": 2, "object": {}},  # placeholder OTHER_ERROR
            }
        if not isinstance(name, str) or name not in self.objects:
            return {
                "op": "service_response",
                "service": _SERVICE,
                "id": message.get("id"),
                "result": True,
                "values": {"success": False, "error_code": 1, "object": {}},  # placeholder OBJECT_NOT_FOUND
            }
        if self.malformed_result:
            return {
                "op": "service_response",
                "service": _SERVICE,
                "id": message.get("id"),
                "result": True,
                "values": {"success": True},  # placeholder malformed missing object
            }
        return {
            "op": "service_response",
            "service": _SERVICE,
            "id": message.get("id"),
            "result": True,
            "values": {"success": True, "error_code": 0, "object": self._object(name)},  # placeholder
        }
