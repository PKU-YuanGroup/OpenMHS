"""ROS-free recording fake for the pinned nao_walker topics and stop service.

The fake models the ROS 1 rosbridge wire shapes this driver declares:
``advertise``/``publish`` on ``/cmd_vel`` and ``/cmd_pose``,
``call_service`` to ``/stop_walk_srv``, and ``call_service`` to
``/clip_footstep_srv`` with the clipped-step reply.  It imports no ROS, NaOqi or
clone code and starts no process.

Every value below is placeholder test data, not a device fact, except the
upstream axis-clipping constants copied from ``nao_footstep_clipping.Params``.
The fake does not emulate walking, balance or NaOqi, and its clip stand-in does
not reproduce the external ``almath`` ellipse or collision-avoidance steps.  In
particular, the upstream ``handleStopWalkSrv`` returns ``None`` after a caught
RuntimeError. Official rospy service conversion rejects None as a service
handler failure. The ``stop_walk_raised_upstream`` switch therefore emits a
failed service response and retains walking state; it does not invent success.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport

_ZERO_TWIST = {"linear": {"x": 0.0, "y": 0.0, "z": 0.0},
               "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}  # placeholder initial command echo
_ZERO_POSE = {"x": 0.0, "y": 0.0, "theta": 0.0}              # placeholder initial command echo

#: Upstream clipping constants from nao_footstep_clipping.Params (source facts,
#: not test data).  The support-side y range is a placeholder choice because the
#: external StepTarget.left value is not in the clone.
_CLIP_MIN_X, _CLIP_MAX_X = -0.04, 0.08
_CLIP_MIN_Y, _CLIP_MAX_Y = -0.16, -0.088
_CLIP_MAX_THETA = 0.5


def _clip_number(value, low, high):
    number = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
    return min(max(number, low), high)


class FakeNaoWalker(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.walking = False                     # placeholder: no physical state is claimed
        self.stop_calls = 0                     # placeholder counter
        self.last_velocity = copy.deepcopy(_ZERO_TWIST)  # placeholder command echo
        self.last_pose = copy.deepcopy(_ZERO_POSE)       # placeholder command echo
        self.fail_stop_service = False          # placeholder negative-path switch
        self.fail_stop_application = False      # placeholder negative-path switch
        self.malformed_stop_reply = False       # placeholder negative-path switch
        self.stop_walk_raised_upstream = False  # placeholder: caught RuntimeError leads to service failure

    @staticmethod
    def _response(message, *, result=True, values=None):
        return {
            "op": "service_response",
            "service": message.get("service"),
            "id": message.get("id"),
            "result": bool(result),
            "values": {} if values is None else copy.deepcopy(values),
        }

    def _respond(self, message):
        operation = message.get("op")
        topic = message.get("topic")
        if operation == "subscribe":
            return None
        if operation == "publish":
            if topic == "/cmd_vel" and isinstance(message.get("msg"), dict):
                self.last_velocity = copy.deepcopy(message["msg"])  # placeholder command echo
                twist = message["msg"]
                linear = twist.get("linear") if isinstance(twist.get("linear"), dict) else {}
                angular = twist.get("angular") if isinstance(twist.get("angular"), dict) else {}
                components = (linear.get("x"), linear.get("y"), linear.get("z"), angular.get("z"))
                self.walking = any(isinstance(value, (int, float)) and not isinstance(value, bool)
                                   and value != 0 for value in components)  # placeholder state rule
            elif topic == "/cmd_pose" and isinstance(message.get("msg"), dict):
                self.last_pose = copy.deepcopy(message["msg"])  # placeholder command echo
                self.walking = True  # placeholder state rule
            return None
        if operation in ("advertise", "unadvertise", "unsubscribe"):
            return None
        if operation != "call_service":
            return None
        service = message.get("service")
        if service == "/clip_footstep_srv":
            step = message.get("args", {}).get("step") if isinstance(message.get("args"), dict) else None
            step = step if isinstance(step, dict) else {}
            pose = step.get("pose") if isinstance(step.get("pose"), dict) else {}
            leg = step.get("leg", 0)  # placeholder default leg: the external enum is not in the clone
            clipped = {
                "step": {
                    "leg": leg,
                    "pose": {
                        "x": _clip_number(pose.get("x"), _CLIP_MIN_X, _CLIP_MAX_X),
                        "y": _clip_number(pose.get("y"), _CLIP_MIN_Y, _CLIP_MAX_Y),
                        "theta": _clip_number(pose.get("theta"), -_CLIP_MAX_THETA, _CLIP_MAX_THETA),
                    },
                },
            }
            return self._response(message, values=clipped)
        if service != "/stop_walk_srv":
            return self._response(message, result=False, values={"error": "undeclared service"})  # placeholder
        if self.fail_stop_service:
            return self._response(message, result=False, values={"error": "service unavailable"})  # placeholder
        if self.malformed_stop_reply:
            # A non-boolean result is not a valid rosbridge service response; the
            # bridge must surface it as an uncertain stop, never as completion.
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": "accepted", "values": {}}  # placeholder malformed reply
        self.stop_calls += 1  # placeholder counter
        if self.stop_walk_raised_upstream:
            # The node returns None; rospy rejects that invalid handler result.
            self.walking = True  # placeholder: the failed stop did not clear the walk
            return self._response(message, result=False,
                                  values={"error": "service handler returned None"})
        self.walking = False  # placeholder: the callback returned after waitUntilWalkIsFinished
        if self.fail_stop_application:
            return self._response(message, values={"rejected": True})  # placeholder application rejection
        return self._response(message)
