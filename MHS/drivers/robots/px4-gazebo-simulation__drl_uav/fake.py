"""ROS-free recording fake for the pinned drl_uav game topic contract.

The fake answers the declared ``game_status`` subscription and records the
``game_input`` publications.  It contacts no ROS graph, rosbridge peer, Gazebo,
PX4, MAVROS, state_machine or DRL agent.  Every state value below is
synthesized placeholder data, not a device fact and not a replay of captured
ROS traffic.  The +-0.1 toy update and the pos1 reset mirror the pinned
``scripts/game_test.py`` test platform; they are not UAV dynamics.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeDrlUavGame(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder game state only; game_test.py starts with vel1 0.5 and
        # pos1 3.5, but these are test data, not a device fact.
        self.vel1 = 0.5  # placeholder
        self.vel2 = 0.0  # placeholder
        self.pos1 = 3.5  # placeholder
        self.pos2 = 0.0  # placeholder
        self.sent_actions = []  # placeholder recording of outbound game actions
        # Negative-path switches used by the package tests.
        self.silent_status = False  # placeholder: publish no game_status sample
        self.malformed_status = False  # placeholder: publish a game_status missing vel1/vel2/pos2

    def _status_message(self):
        if self.malformed_status:
            return {"pos1": self.pos1}  # placeholder: deliberately missing fields
        return {
            "vel1": self.vel1,  # placeholder
            "vel2": self.vel2,  # placeholder
            "pos1": self.pos1,  # placeholder
            "pos2": self.pos2,  # placeholder
        }

    def _publish_action(self, message):
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        action = body.get("action")
        self.sent_actions.append(action)  # placeholder recording
        if isinstance(action, bool) or not isinstance(action, (int, float)):
            return None
        action = float(action)
        # Placeholder toy effect only: these are the pinned game_test.py
        # semantics, not physics, not a thrust model and not an arrival claim.
        if action > 100.0:  # placeholder sentinel from game_test.py
            self.pos1 = 3.5  # placeholder reset value from game_test.py
        elif action == 1.0:
            self.pos1 += 0.1  # placeholder toy increment
        elif action == 0.0:
            self.pos1 -= 0.1  # placeholder toy decrement
        return None

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/game_status" and not self.silent_status:
                return {
                    "op": "publish",
                    "topic": "/game_status",
                    "id": message.get("id"),
                    "msg": self._status_message(),
                }
            return None
        if operation == "publish":
            if message.get("topic") == "/game_input":
                return self._publish_action(message)
            return None
        # advertise/unsubscribe are recorded by RecordingRosTransport; no reply.
        return None
