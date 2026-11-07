"""ROS-free canned-response fake for the DAVE ocean-current endpoints.

The fake models the pinned wire contract of DAVE's ocean-current ROS plugin:
a geometry_msgs/TwistStamped publication on the resolved current topic, the
two GetCurrentModel services used by this driver and the SetCurrentVelocity
service.  It mirrors the native short-circuit partial application of the three
SetMean calls.  Every number below is test data (# placeholder), not a device
fact.
"""

import math

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeDave(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder configuration values, not upstream bounds.
        self.velocity = 0.75                    # placeholder [m/s]
        self.horizontal_angle = 0.1             # placeholder [rad]
        self.vertical_angle = 0.05              # placeholder [rad]
        self.velocity_min = 0.0                 # placeholder [m/s]
        self.velocity_max = 5.0                 # placeholder [m/s]
        self.velocity_noise = 0.0               # placeholder [m/s]
        self.velocity_mu = 0.0                  # placeholder [1]
        self.angle_min = -3.141592653589793     # placeholder [rad]
        self.angle_max = 3.141592653589793      # placeholder [rad]
        self.angle_noise = 0.0                  # placeholder [rad]
        self.angle_mu = 0.0                     # placeholder [1]
        self.stamp_secs = 12                    # placeholder [s]
        self.stamp_nsecs = 340000000            # placeholder [ns]
        self.fail_set_service = False           # placeholder negative-path switch
        self.fail_set_application = False       # placeholder negative-path switch
        self.malformed_set_response = False     # placeholder malformed-reply switch

    @staticmethod
    def _model(mean, low, high, noise, mu):
        return {"mean": mean, "min": low, "max": high, "noise": noise, "mu": mu}

    def _vector(self):
        magnitude = self.velocity
        horizontal = self.horizontal_angle
        vertical = self.vertical_angle
        return {
            "x": magnitude * math.cos(horizontal) * math.cos(vertical),  # placeholder-derived
            "y": magnitude * math.sin(horizontal) * math.cos(vertical),  # placeholder-derived
            "z": magnitude * math.sin(vertical),                          # placeholder-derived
        }

    def _set_velocity_mean(self, value):
        if not self.velocity_min <= value <= self.velocity_max:
            return False
        self.velocity = value
        return True

    def _set_horizontal_mean(self, value):
        if not self.angle_min <= value <= self.angle_max:
            return False
        self.horizontal_angle = value
        return True

    def _set_vertical_mean(self, value):
        if not self.angle_min <= value <= self.angle_max:
            return False
        self.vertical_angle = value
        return True

    def _set_current(self, args):
        # The native callback is a short-circuit && chain: a later rejection
        # leaves the earlier model updates in place.
        success = self._set_velocity_mean(float(args.get("velocity", 0.0)))
        if success:
            success = self._set_horizontal_mean(float(args.get("horizontal_angle", 0.0)))
        if success:
            success = self._set_vertical_mean(float(args.get("vertical_angle", 0.0)))
        return success

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/hydrodynamics/current_velocity":
                return {
                    "op": "publish",
                    "topic": "/hydrodynamics/current_velocity",
                    "id": message.get("id"),
                    "msg": {
                        "header": {
                            "seq": 0,  # placeholder
                            "stamp": {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs},
                            "frame_id": "/world",
                        },
                        "twist": {
                            "linear": self._vector(),
                            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                        },
                    },
                }
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/hydrodynamics/get_current_velocity_model":
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": True,
                    "values": self._model(self.velocity, self.velocity_min, self.velocity_max,
                                          self.velocity_noise, self.velocity_mu),
                }
            if service == "/hydrodynamics/get_current_horz_angle_model":
                return {
                    "op": "service_response",
                    "service": service,
                    "id": message.get("id"),
                    "result": True,
                    "values": self._model(self.horizontal_angle, self.angle_min, self.angle_max,
                                          self.angle_noise, self.angle_mu),
                }
            if service == "/hydrodynamics/set_current_velocity":
                if self.fail_set_service:
                    return {"op": "service_response", "service": service,
                            "id": message.get("id"), "result": False, "values": {}}  # placeholder
                if self.malformed_set_response:
                    return {"op": "service_response", "service": service,
                            "id": message.get("id"), "result": True,
                            "values": "malformed"}  # placeholder malformed reply
                success = self._set_current(message.get("args") or {})
                if self.fail_set_application:
                    return {"op": "service_response", "service": service,
                            "id": message.get("id"), "result": True,
                            "values": {"success": False}}  # placeholder rejection
                return {"op": "service_response", "service": service,
                        "id": message.get("id"), "result": True,
                        "values": {"success": success}}
            return {"op": "service_response", "service": service,
                    "id": message.get("id"), "result": False, "values": {}}  # placeholder
        return None
