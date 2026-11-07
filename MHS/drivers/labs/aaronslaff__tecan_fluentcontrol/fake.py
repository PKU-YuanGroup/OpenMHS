"""Fake backend of the FluentControl driver: an in-memory stand-in for FluentControlClient.

Gate G7: every public method defined here is a method of
``fluent_control_automation:FluentControlClient`` (fluent_control_automation.py:159-225).  The fake does no HTTP and
imports nothing from the clone.  All values below are test data, not device facts: the status and deck dictionaries,
the generated session ids, the session status words and the progress number are placeholders written only so the
driver can be exercised.  Nothing here talks to a device.
"""

from copy import deepcopy


class FakeFluentControlClient:
    """An in-memory client with the public surface of FluentControlClient."""

    def __init__(self, **_options):
        self._status = {"state": "idle"}                    # placeholder canned reply
        self._deck = {"positions": []}                      # placeholder canned reply
        self._sessions = {}
        self._next = 0                                      # placeholder session counter

    def get_instrument_status(self):
        return deepcopy(self._status)

    def get_deck_layout(self):
        return deepcopy(self._deck)

    def post_deck_layout(self, positions):
        self._deck = {"positions": [dict(position) for position in positions]}  # placeholder
        return {"status": "accepted"}                       # placeholder canned reply

    def post_transfer_session(self, transfers):
        self._next += 1                                     # placeholder
        session_id = f"fake-session-{self._next}"           # placeholder generated id
        self._sessions[session_id] = {
            "status": "pending",                            # placeholder
            "transfers": [dict(transfer) for transfer in transfers],
            "progress": 0,                                  # placeholder
        }
        return {"session_id": session_id, "status": "pending"}  # placeholder canned reply

    def start_transfer_session(self, session_id):
        session = self._sessions.setdefault(session_id, {"transfers": []})
        session["status"] = "running"                       # placeholder
        return {"session_id": session_id, "status": "running"}  # placeholder canned reply

    def get_transfer_status(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            return {"session_id": session_id, "status": "unknown"}  # placeholder canned reply
        return {
            "session_id": session_id,
            "status": session["status"],
            "progress": session.get("progress", 0),         # placeholder
        }

    def cancel_transfer_session(self, session_id):
        session = self._sessions.setdefault(session_id, {"transfers": []})
        session["status"] = "cancelled"                     # placeholder
        return {"session_id": session_id, "status": "cancelled"}  # placeholder canned reply
