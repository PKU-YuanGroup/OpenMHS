"""ROS action wire profiles and bounded per-goal state, without ROS imports.

ROS 1 actionlib uses generated topic wrappers. ROS 2 native rosbridge actions
have a different status enum and expose a connection-local ID, not the ROS
UUID. These profiles never infer success from publication or cancellation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping


ROS1_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*/[A-Za-z_][A-Za-z0-9_]*Action\Z")
ROS2_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*/action/[A-Za-z_][A-Za-z0-9_]*\Z")
PROFILES = {"ros1-actionlib": ROS1_TYPE, "ros2-native": ROS2_TYPE}
MAX_ACTIONS = 16
MAX_SAFETY_ACTIONS = 4
MAX_SAFETY_HISTORY = 16


@dataclass
class PendingAction:
    ident: str
    name: str
    action_type: str
    profile: str
    want_feedback: bool = False
    sent: bool = False
    abandoned: bool = False
    error: BaseException | None = None
    response: dict[str, Any] | None = None
    received_at: float | None = None
    feedback: dict[str, Any] | None = None
    feedback_count: int = 0
    setup_sent: list[dict[str, Any]] = field(default_factory=list)
    safety: bool = False

    @property
    def succeeded(self) -> int:
        return 3 if self.profile == "ros1-actionlib" else 4

    @property
    def cancelled(self) -> tuple[int, ...]:
        return (2, 8) if self.profile == "ros1-actionlib" else (5,)

    @property
    def terminal(self) -> tuple[int, ...]:
        return (2, 3, 4, 5, 8) if self.profile == "ros1-actionlib" else (4, 5, 6)

    def setup(self) -> list[dict[str, Any]]:
        if self.profile == "ros2-native":
            return []
        roles = ["result", "status"] + (["feedback"] if self.want_feedback else [])
        types = {"goal": self.action_type + "Goal", "result": self.action_type + "Result",
                 "feedback": self.action_type + "Feedback", "status": "actionlib_msgs/GoalStatusArray",
                 "cancel": "actionlib_msgs/GoalID"}
        return [{"op": "subscribe", "topic": self.name + "/" + role, "type": types[role],
                 "id": self.ident + ":" + role, "queue_length": 1} for role in roles] + [
            {"op": "advertise", "topic": self.name + "/" + role, "type": types[role],
             "id": self.ident + ":" + role} for role in ("goal", "cancel")]

    def goal(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.profile == "ros2-native":
            return {"op": "send_action_goal", "action": self.name, "action_type": self.action_type,
                    "id": self.ident, "args": payload, "feedback": self.want_feedback}
        return {"op": "publish", "topic": self.name + "/goal", "id": self.ident,
                "msg": {"header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},
                        "goal_id": {"stamp": {"secs": 0, "nsecs": 0}, "id": self.ident}, "goal": payload}}

    def cancel(self) -> dict[str, Any]:
        if self.profile == "ros2-native":
            return {"op": "cancel_action_goal", "action": self.name, "id": self.ident}
        # A nonempty ID and zero timestamp cancel exactly this goal, never all goals.
        return {"op": "publish", "topic": self.name + "/cancel", "id": self.ident,
                "msg": {"stamp": {"secs": 0, "nsecs": 0}, "id": self.ident}}

    def cleanup(self) -> list[dict[str, Any]]:
        return [{"op": "unsubscribe" if msg["op"] == "subscribe" else "unadvertise",
                 "topic": msg["topic"], "id": msg["id"]} for msg in reversed(self.setup_sent)]

    def receive(self, message: Mapping[str, Any], received_at: float) -> bool:
        """Called under the bridge condition; retain one result and one latest feedback."""
        op = message.get("op")
        ident = message.get("id")
        if op == "status" and message.get("level") == "error":
            if ident == self.ident or any(ident == frame["id"] for frame in self.setup_sent):
                self.error = ValueError("rosbridge reported an action protocol error")
                return True
            return False
        if not self.sent:
            return False
        status = None
        values = None
        is_result = False
        if self.profile == "ros2-native":
            if op not in ("action_result", "action_feedback") or ident != self.ident:
                return False
            if message.get("action") != self.name:
                self.error = ValueError("action response endpoint does not match its goal")
                return True
            values = message.get("values")
            is_result = op == "action_result"
            if is_result:
                if message.get("result") is not True:
                    self.error = ValueError("ROS action wrapper cannot establish a terminal outcome")
                    return True
                status = message.get("status")
        else:
            if op != "publish" or not isinstance(message.get("msg"), Mapping):
                return False
            msg = message["msg"]
            topic = message.get("topic")
            if topic == self.name + "/status":
                statuses = msg.get("status_list")
                if not isinstance(statuses, list):
                    return False
                for entry in statuses:
                    if (isinstance(entry, Mapping) and isinstance(entry.get("goal_id"), Mapping)
                            and entry["goal_id"].get("id") == self.ident):
                        value = entry.get("status")
                        if type(value) is not int or value not in range(9):
                            self.error = ValueError("ROS 1 action status is malformed or LOST")
                        return True  # status alone never completes an operation
                return False
            envelope = msg.get("status")
            if (not isinstance(envelope, Mapping) or not isinstance(envelope.get("goal_id"), Mapping)
                    or envelope["goal_id"].get("id") != self.ident):
                return False
            if topic not in (self.name + "/result", self.name + "/feedback"):
                return False
            is_result = topic == self.name + "/result"
            values = msg.get("result" if is_result else "feedback")
            status = envelope.get("status")
        if not isinstance(values, dict):
            self.error = ValueError("action result/feedback must be an object")
        elif is_result:
            if type(status) is not int or status not in self.terminal:
                self.error = ValueError("action result has no valid terminal status for its profile")
            elif self.response is not None and _fingerprint(self.response) != _fingerprint({"status": status, "values": values}):
                self.error = ValueError("action returned contradictory terminal results")
            elif self.response is None:
                self.response = {"status": status, "values": copy.deepcopy(values)}
                self.received_at = received_at
        elif self.want_feedback and self.response is None:
            self.feedback = copy.deepcopy(values)
            self.feedback_count = min(self.feedback_count + 1, 2**63 - 1)
        return True


def terminal_identity(message: Mapping[str, Any]) -> str | None:
    """Claimed terminal/protocol-error identity, excluding periodic status/feedback.

    Attribution precedes wrapper validation so a malformed claimed old result
    cannot disappear merely because its endpoint or payload no longer parses.
    """
    op = message.get("op")
    if op == "action_result" or (op == "status" and message.get("level") == "error"):
        ident = message.get("id")
        return ident.split(":", 1)[0] if isinstance(ident, str) else None
    if op == "publish" and isinstance(message.get("topic"), str) and message["topic"].endswith("/result"):
        msg = message.get("msg")
        envelope = msg.get("status") if isinstance(msg, Mapping) else None
        goal = envelope.get("goal_id") if isinstance(envelope, Mapping) else None
        ident = goal.get("id") if isinstance(goal, Mapping) else None
        if isinstance(ident, str):
            return ident
        # rosbridge may also carry the subscription ID on the outer envelope.
        ident = message.get("id")
        return ident.split(":", 1)[0] if isinstance(ident, str) else None
    return None


def _fingerprint(response: Mapping[str, Any]) -> bytes:
    # Incoming frames have already passed the bridge's finite JSON/size bound.
    # JSON preserves bool/int and int/float distinctions that dict == does not.
    return hashlib.sha256(json.dumps(response, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).digest()


@dataclass(frozen=True)
class SafetyActionTerminal:
    """Bounded metadata/fingerprint, not retained feedback or result payloads."""
    ident: str
    name: str
    action_type: str
    profile: str
    fingerprint: bytes

    @classmethod
    def from_pending(cls, pending: PendingAction) -> SafetyActionTerminal:
        assert pending.sent and pending.response is not None and pending.error is None
        return cls(pending.ident, pending.name, pending.action_type, pending.profile,
                   _fingerprint(pending.response))

    def check(self, message: Mapping[str, Any]) -> BaseException | None:
        parsed = PendingAction(self.ident, self.name, self.action_type, self.profile, sent=True)
        parsed.setup_sent = parsed.setup()
        matched = parsed.receive(message, 0.0)
        claimed = terminal_identity(message) == self.ident
        if claimed and (not matched or parsed.response is None) and parsed.error is None:
            return ValueError("retired safety goal received a malformed or mismatched terminal result")
        if parsed.error is not None:
            return parsed.error
        if parsed.response is not None and _fingerprint(parsed.response) != self.fingerprint:
            return ValueError("retired safety goal returned contradictory terminal results")
        return None
