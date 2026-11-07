"""Fake backend of the galago-tools OT-2 tool: an in-memory stand-in for ``tools.opentrons2.driver:Ot2Driver``.

It has the attributes the upstream constructor sets (robot_ip, robot_port, run_id, base_url, headers;
tools/opentrons2/driver.py:11-18) and the methods the driver uses, with the upstream names and signatures: ``ping``
(20-30), ``upload_and_schedule_protocol`` (62-106), ``start_run`` (108-123), ``get_run_status`` (199-214),
``cancel_protocol`` (167-197) and ``close`` (308-315).  ``stop`` is the one method the upstream class does not define:
the package's hardware backend (native.py) adds it to send only the first request of ``cancel_protocol``, the run
action ``stop`` (175-181), without the DELETE (184-190), so the stopped run stays readable.

Nothing here talks to a robot or reads the protocol file.  The robot server is a dictionary of runs.  Of the status
words, only "succeeded", "stopped", "failed" and "blocked-by-open-door" occur in the clone (driver.py:227-231); the
others ("idle", "running", "stop-requested") and every id are placeholders.  A played run reports "running" for
``_run_reads`` status reads and then "succeeded" (a placeholder protocol duration), and a stop settles to "stopped"
after ``_stop_settles_after`` further status reads, so the driver's confirmation loop is exercised.
"""

from __future__ import annotations


class FakeRobotRefusal(Exception):
    """A non-2xx answer of the fake robot server (the upstream raises a plain Exception with the response text)."""


class FakeOt2Driver:
    def __init__(self, robot_ip="ot2.placeholder.invalid", robot_port=31950, **_options):
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.run_id = None
        self.base_url = f"http://{robot_ip}:{robot_port}"
        self.headers = {"Opentrons-Version": "2"}
        self._runs = {}               # run id -> status (placeholder words except those of driver.py:227-231)
        self._settling = {}           # run id -> status reads left before a requested stop reads "stopped"
        self._requests = []           # (method, path) in order, for the tests
        self._protocols = {}          # run id -> (protocol_file, protocol id); the file is never opened
        self._stop_settles_after = 1  # placeholder
        self._run_reads = 1           # placeholder: status reads that report "running" before "succeeded"
        self._running = {}            # run id -> "running" reads left
        self._count = 0

    def _request(self, method, path):
        self._requests.append((method, path))

    def ping(self):
        self._request("GET", "/health")

    def upload_and_schedule_protocol(self, protocol_file):
        self._request("POST", "/protocols")
        self._count += 1
        protocol_id = f"protocol-{self._count}"            # placeholder
        self._request("POST", "/runs")
        run_id = f"run-{self._count}"                      # placeholder
        self._runs[run_id] = "idle"                        # placeholder status word
        self._protocols[run_id] = (protocol_file, protocol_id)
        self.run_id = run_id
        return run_id

    def start_run(self, run_id):
        self._request("POST", f"/runs/{run_id}/actions play")
        if self._runs.get(run_id) != "idle":
            raise FakeRobotRefusal(f"Failed to start run: run {run_id} is {self._runs.get(run_id)!r}")
        self._runs[run_id] = "running"                     # placeholder status word
        self._running[run_id] = self._run_reads

    def get_run_status(self, run_id):
        self._request("GET", f"/runs/{run_id}")
        if run_id not in self._runs:
            raise FakeRobotRefusal(f"Failed to get run status: no run {run_id}")
        if self._runs[run_id] == "running":
            left = self._running.get(run_id, 0)
            if left <= 0:
                self._runs[run_id] = "succeeded"           # driver.py:227
                self._running.pop(run_id, None)
            else:
                self._running[run_id] = left - 1
            return {"data": {"id": run_id, "status": "running" if left > 0 else "succeeded"}}
        left = self._settling.get(run_id)
        if left is not None:
            if left <= 0:
                self._runs[run_id] = "stopped"             # driver.py:230
                del self._settling[run_id]
            else:
                self._settling[run_id] = left - 1
        return {"data": {"id": run_id, "status": self._runs[run_id]}}

    def _post_stop(self, run_id):
        self._request("POST", f"/runs/{run_id}/actions stop")
        status = self._runs.get(run_id)
        if status in ("succeeded", "stopped", "failed") or status is None:   # placeholder refusal
            raise FakeRobotRefusal(f"Failed to stop run: run {run_id} is {status!r}")
        self._runs[run_id] = "stop-requested"              # placeholder status word
        self._running.pop(run_id, None)
        self._settling[run_id] = self._stop_settles_after

    def stop(self):
        """The package's addition (native.py): driver.py:175-181 alone."""
        if not self.run_id:
            return
        self._post_stop(self.run_id)

    def cancel_protocol(self):
        """driver.py:167-197: stop, then DELETE (a failed DELETE is only a warning upstream), then forget the run."""
        if not self.run_id:
            return
        self._post_stop(self.run_id)
        self._request("DELETE", f"/runs/{self.run_id}")
        self._runs.pop(self.run_id, None)
        self._settling.pop(self.run_id, None)
        self.run_id = None

    def close(self):
        """driver.py:308-315: cancel an active run; an error is only a warning."""
        try:
            if self.run_id:
                self.cancel_protocol()
        except Exception:  # noqa: BLE001 - the upstream logs it as a warning
            pass
