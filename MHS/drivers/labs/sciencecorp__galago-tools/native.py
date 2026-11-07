"""Hardware backend: a bounded port of galago-tools' OT-2 client, ``tools.opentrons2.driver:Ot2Driver``.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend; the package is
R2 and model-authored, so the loader refuses that backend until a human signs ``reviewed_by`` in driver.lock.json.
Nothing here was run against a robot.

Why a port and not the upstream class.  Every ``requests`` call of ``Ot2Driver`` except ``get_run_status`` (30 s,
driver.py:202-206) has no timeout (driver.py:22-25, 67-73, 85-93, 111-115, 132-136, 153-157, 175-187), so a robot
server that accepts the connection and never answers would hold the e-stop forever.  The upstream class also inherits
``ABCToolDriver.__getattr__``, which answers any attribute it does not define with a function that does nothing
(tools/base_server.py:28-34), so a misspelt or missing method is silently a no-op.  This port therefore re-implements,
with the upstream's names and signatures, the methods the driver uses: each sends exactly the request of the cited
upstream lines (method, URL, JSON body, multipart field, the ``Opentrons-Version: 2`` header) through the upstream's
own HTTP library, ``requests`` (requirements.txt:5), with ``timeout=(connect_timeout_s, read_timeout_s)``.  The read
timeout bounds each wait for data, not a whole response.  A non-2xx answer raises where the upstream raises; a failed
DELETE in ``cancel_protocol`` is only logged, as upstream (driver.py:188-190).  The upstream's own ``try``/``except``
blocks only log and re-raise (for example 104-106), so the port leaves them out.

One method is the port's own: ``stop`` sends the first request of ``cancel_protocol`` (the run action ``stop``,
driver.py:175-181) without the DELETE that follows it (184-190), so the run stays on the robot and its status can be
read back; the driver's e-stop confirms the stop by that status.  Nothing else differs from the upstream methods.

Options: ``robot_ip`` (required; deployment data), ``robot_port`` (default 31950, the upstream constructor's,
driver.py:11), ``connect_timeout_s`` and ``read_timeout_s`` (connection settings of this port, not device facts).
The protocol file passed to ``upload_and_schedule_protocol`` is read on this host, as upstream (driver.py:66).
"""

from __future__ import annotations

import logging

DEFAULT_CONNECT_TIMEOUT_S = 3.0
DEFAULT_READ_TIMEOUT_S = 5.0

log = logging.getLogger(__name__)


def connect(*, robot_ip, robot_port=31950, connect_timeout_s=DEFAULT_CONNECT_TIMEOUT_S,
            read_timeout_s=DEFAULT_READ_TIMEOUT_S):
    if not isinstance(robot_ip, str) or not robot_ip.strip():
        raise ValueError("robot_ip must be the address of the OT-2 robot server")
    if isinstance(robot_port, bool) or not isinstance(robot_port, int) or not 0 < robot_port < 65536:
        raise ValueError("robot_port must be a TCP port number")
    for name, value in (("connect_timeout_s", connect_timeout_s), ("read_timeout_s", read_timeout_s)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < float(value) <= 60:
            raise ValueError(f"{name} must be a number of seconds in (0, 60]")
    return BoundedOt2Driver(robot_ip, robot_port, connect_timeout_s=float(connect_timeout_s),
                            read_timeout_s=float(read_timeout_s))


class BoundedOt2Driver:
    """``Ot2Driver`` with a timeout on every request (and the ``stop`` request on its own)."""

    def __init__(self, robot_ip, robot_port=31950, *, connect_timeout_s, read_timeout_s):
        import requests  # the upstream's HTTP library (requirements.txt:5)

        self._requests = requests
        self._timeout = (connect_timeout_s, read_timeout_s)
        self.robot_ip = robot_ip                                   # driver.py:12
        self.robot_port = robot_port                               # driver.py:13
        self.run_id = None                                         # driver.py:15
        self.base_url = f"http://{robot_ip}:{robot_port}"          # driver.py:17
        self.headers = {"Opentrons-Version": "2"}                  # driver.py:18

    def ping(self):
        """driver.py:20-30."""
        response = self._requests.get(url=f"{self.base_url}/health", headers=self.headers, timeout=self._timeout)
        if response.status_code != 200:
            raise Exception(f"Ping failed with status {response.status_code}: {response.text}")

    def upload_and_schedule_protocol(self, protocol_file):
        """driver.py:62-106: upload the file as protocol.py, then create a run of it; remember and return its id."""
        with open(protocol_file, "rb") as f:
            upload_response = self._requests.post(
                url=f"{self.base_url}/protocols",
                files={"files": ("protocol.py", f, "text/x-python-script")},
                headers=self.headers, timeout=self._timeout)
        if not upload_response.ok:
            raise Exception(f"Protocol upload failed: {upload_response.text}")
        try:
            protocol_id = upload_response.json()["data"]["id"]
        except KeyError:
            raise Exception(f"Invalid upload response format: {upload_response.text}")
        create_run_response = self._requests.post(
            url=f"{self.base_url}/runs", json={"data": {"protocolId": protocol_id}},
            headers=self.headers, timeout=self._timeout)
        if not create_run_response.ok:
            raise Exception(f"Failed to create run: {create_run_response.text}")
        run_id = create_run_response.json()["data"]["id"]
        self.run_id = run_id
        return run_id

    def start_run(self, run_id):
        """driver.py:108-123: the run action ``play``."""
        response = self._requests.post(url=f"{self.base_url}/runs/{run_id}/actions", headers=self.headers,
                                       json={"data": {"actionType": "play"}}, timeout=self._timeout)
        if not response.ok:
            raise Exception(f"Failed to start run: {response.text}")

    def get_run_status(self, run_id):
        """driver.py:199-214 (the upstream's 30 s timeout replaced by this port's)."""
        response = self._requests.get(url=f"{self.base_url}/runs/{run_id}", headers=self.headers,
                                      timeout=self._timeout)
        if not response.ok:
            raise Exception(f"Failed to get run status: {response.text}")
        return response.json()

    def stop(self):
        """The port's own: driver.py:175-181 alone (the run action ``stop``), without the DELETE of 184-190."""
        if not self.run_id:
            return
        response = self._requests.post(url=f"{self.base_url}/runs/{self.run_id}/actions", headers=self.headers,
                                       json={"data": {"actionType": "stop"}}, timeout=self._timeout)
        if not response.ok:
            raise Exception(f"Failed to stop run: {response.text}")

    def cancel_protocol(self):
        """driver.py:167-197: stop the run, delete it (a failed DELETE is only logged, as upstream), forget it."""
        if not self.run_id:
            return
        self.stop()
        delete_response = self._requests.delete(url=f"{self.base_url}/runs/{self.run_id}", headers=self.headers,
                                                timeout=self._timeout)
        if not delete_response.ok:
            log.warning("Failed to delete run: %s", delete_response.text)
        self.run_id = None

    def close(self):
        """driver.py:308-315: cancel an active run; an error is only logged."""
        try:
            if self.run_id:
                self.cancel_protocol()
        except Exception as exc:  # noqa: BLE001 - as upstream (a warning)
            log.warning("Error during cleanup: %s", exc)
