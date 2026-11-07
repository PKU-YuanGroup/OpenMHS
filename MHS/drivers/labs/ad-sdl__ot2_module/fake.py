"""Fake backend of the OT-2 driver: an in-memory stand-in for ot2_interface.ot2_driver_http:OT2_Driver.

Gate G7: every public method defined here exists on the upstream OT2_Driver class.  The upstream class is an HTTP
client (src/ot2_interface/ot2_driver_http.py:42-548); the fake keeps its method names, arguments and return shapes
without sockets or requests: transfer returns (protocol_id, run_id); resume, pause and cancel return a response object
with ``status_code`` and ``json()``; get_run and get_run_log return the answer's JSON as the upstream does;
check_run_status returns the RunStatus member; get_runs returns the simplified list or None; send_request routes the
requests the driver's stop path sends (GET runs, GET runs/<id>, POST runs/<id>/actions) and answers others 404.

What the clone states and the fake follows: the RunStatus values (:29-39); 201 is the good answer of the
/runs/<id>/actions endpoint (:188-195); GET answers are compared with 200 (:297, :320, :372); get_runs returns None
when /runs does not answer 200 (:369-386); check_run_status indexes data.status of GET /runs/<id> (:294-300), so an
answer without ``data`` raises KeyError there; get_run returns that answer as it is (:317-323); send_request strips a
leading '/', sets the Opentrons-Version header when none is given and requires a method (:444-461).

What the clone does not state and the fake decides, each marked ``# placeholder``: which run transitions the robot
refuses (409 here for play on a run that is not idle or paused, pause on a run that is not running, and stop on a
run that already ended or was stopped), the code of an unknown run or path (404) and of an unanswered run list
(503), the error bodies, and the robot's timing: a stopped run reads ``stop-requested`` once and ``stopped`` from then
on, and a started run stays ``running`` until a test changes it.  The fake does not open the protocol path and
accepts a new run while another run is active.  Ids are test data.  ``timeout`` and the other request options are
accepted and ignored because no request leaves this object.  Nothing here talks to a device.
"""

import threading
from enum import Enum


class _RunStatus(Enum):
    """The upstream RunStatus values; private so the fake exposes no public name beyond the upstream class."""

    IDLE = "idle"
    RUNNING = "running"
    FINISHING = "finishing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PAUSED = "paused"
    STOPPING = "stop-requested"
    STOPPED = "stopped"


_ENDED = ("succeeded", "failed", "stop-requested", "stopped")


class _Response:
    """The small part of requests.Response the driver reads: ``status_code`` and ``json()``."""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return dict(self._payload)


def _error(code, detail):
    return _Response(code, {"errors": [{"detail": detail}]})  # placeholder: code and body of a refusal


class FakeOt2:
    """In-memory OT-2 HTTP client surface used by the driver."""

    def __init__(self, config=None, retries=5, retry_backoff=1.0, retry_status_codes=None):
        # retries, retry_backoff and retry_status_codes are the upstream constructor options; the fake does not
        # retry because no request leaves this object.  ``config`` is accepted but not inspected.
        self._lock = threading.RLock()
        self._runs = {}
        self._protocols = {}
        self._run_number = 0        # placeholder: the first generated run id is test data
        self._protocol_number = 0   # placeholder: the first generated protocol id is test data
        self._offline = False       # placeholder test switch: GET /runs answers 503 while True
        self._refused_actions = set()   # placeholder test switch: run actions answered 409, run unchanged
        self._ignored_actions = set()   # placeholder test switch: run actions answered 201, run unchanged

    # -- internal state ------------------------------------------------------------------------------------------
    def _status(self, run):
        """Read a run's status; a stop-requested run reads stopped from the next read on (placeholder timing)."""
        status = run["status"]
        if status == _RunStatus.STOPPING.value:
            run["status"] = _RunStatus.STOPPED.value
        return status

    def _summary(self, run):
        return {"id": run["id"], "protocolId": run["protocolId"], "status": self._status(run),
                "current": run["current"]}

    def _action(self, run_id, action_type):
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return _error(404, "run not found")  # placeholder
            status = run["status"]
            allowed = ((action_type == "play" and status in ("idle", "paused"))
                       or (action_type == "pause" and status == "running")
                       or (action_type == "stop" and status not in _ENDED))
            if not allowed or action_type in self._refused_actions:
                return _error(409, f"cannot {action_type} a run in status {status}")  # placeholder
            if action_type not in self._ignored_actions:
                if action_type == "play":
                    run["status"], run["current"] = _RunStatus.RUNNING.value, True
                elif action_type == "pause":
                    run["status"] = _RunStatus.PAUSED.value
                else:
                    run["status"], run["current"] = _RunStatus.STOPPING.value, False
            return _Response(201, {"data": {"runId": run_id, "actionType": action_type}})

    # -- the upstream surface ------------------------------------------------------------------------------------
    def transfer(self, protocol_path):
        """Mirror the upstream upload + create-run step; return (protocol_id, run_id)."""
        with self._lock:
            self._protocol_number += 1
            self._run_number += 1
            protocol_id = "protocol-%d" % self._protocol_number  # placeholder: test identifier
            run_id = "run-%d" % self._run_number                # placeholder: test identifier
            self._protocols[protocol_id] = str(protocol_path)
            self._runs[run_id] = {
                "id": run_id,
                "protocolId": protocol_id,
                "status": _RunStatus.IDLE.value,
                "current": False,
                "commands": [],
            }
            return protocol_id, run_id

    def resume(self, run_id):
        """Mirror the upstream play action; the response is returned unchecked, as upstream."""
        return self._action(run_id, "play")

    def pause(self, run_id):
        """Mirror the upstream pause action."""
        return self._action(run_id, "pause")

    def cancel(self, run_id):
        """Mirror the upstream stop action."""
        return self._action(run_id, "stop")

    def check_run_status(self, run_id):
        """Mirror the upstream status read: RunStatus of data.status; an answer without data raises KeyError."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError("data")
            return _RunStatus(self._status(run))

    def get_run(self, run_id):
        """Mirror the upstream run read: the answer's JSON, an error body included."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return _error(404, "run not found").json()
            data = {key: value for key, value in run.items() if key != "commands"}
            data["status"] = self._status(run)
            return {"data": data}

    def get_run_log(self, run_id):
        """Mirror the upstream run read plus its commands."""
        with self._lock:
            result = self.get_run(run_id)
            run = self._runs.get(run_id)
            result["commands"] = ({"data": list(run["commands"])} if run is not None
                                  else _error(404, "run not found").json())
            return result

    def get_runs(self):
        """Mirror the upstream simplified run list; None when the run list does not answer 200."""
        with self._lock:
            if self._offline:
                return None
            return [{"runID": item["id"], "protocolID": item["protocolId"], "status": item["status"],
                     "current": item["current"]} for item in map(self._summary, list(self._runs.values()))]

    def get_robot_status(self):
        """Mirror the upstream status derivation over the stored runs."""
        runs = self.get_runs()
        if runs is None:
            return "offline"
        for run in runs:
            status = run["status"]
            if status in ("succeeded", "stop-requested"):
                continue
            if status in {member.value for member in _RunStatus}:
                return status
        return "idle"

    def reset_robot_data(self):
        """Mirror the upstream maintenance step: delete failed runs only."""
        with self._lock:
            for run_id in [key for key, run in self._runs.items() if run["status"] == _RunStatus.FAILED.value]:
                del self._runs[run_id]

    def send_request(self, request_extension, **kwargs):
        """Mirror the upstream arbitrary request for the routes the driver sends."""
        request_extension = request_extension if request_extension[0] != "/" else request_extension[1:]
        if "headers" not in kwargs:
            kwargs["headers"] = {"Opentrons-Version": "2"}
        if "method" not in kwargs:
            raise Exception("No request method specified, please provide GET, POST, UPDATE, DELETE as keyword "
                            "argument")
        method = kwargs["method"].upper()
        parts = request_extension.split("/")
        with self._lock:
            if method == "GET" and parts == ["runs"]:
                if self._offline:
                    return _error(503, "run list unavailable")  # placeholder
                return _Response(200, {"data": [self._summary(run) for run in list(self._runs.values())]})
            if method == "GET" and len(parts) == 2 and parts[0] == "runs":
                result = self.get_run(parts[1])
                return _Response(200 if "data" in result else 404, result)  # placeholder: 404 for an unknown run
            if method == "POST" and len(parts) == 3 and parts[0] == "runs" and parts[2] == "actions":
                body = kwargs.get("json")
                data = body.get("data") if isinstance(body, dict) else None
                action_type = data.get("actionType") if isinstance(data, dict) else None
                return self._action(parts[1], action_type)
            return _error(404, "no such path")  # placeholder
