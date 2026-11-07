"""Fake backend of the BCS motor: an in-memory stand-in for one BCSMotor and its BCSServer replies.

The upstream object (``src/bcsophyd/zmq/bcs_motor.py:21``) holds a ``BCSServer`` and calls only a few of its
endpoints.  This fake mirrors the shape the driver uses: attributes with the same names, ``zmq_move_motor`` and
``zmq_stop_motor`` that run their request in a worker thread like the upstream wrappers, ``stop`` that sends StopMotor
and sets ``isMoving`` like the upstream method, and an async ``zmq_get_motor_full_async`` that parses the
``GetMotorFull`` reply like the upstream one.  The nested ``_FakeBCSServer`` is the reply side and implements the
three BCSServer coroutines the upstream motor calls (``get_motor_full``, ``move_motor``, ``stop_motor``).

Nothing here imports ophyd, pyzmq or bcsophyd, opens a socket, or talks to a LabVIEW server.  Every value is a
placeholder chosen for the tests, not a fact about a motor.  The knobs used by the package tests are plain attributes
of the nested server; they are test data too.

Model review (2026-11-05): the upstream BCSServer sends every request on one ZeroMQ REQ socket and awaits the reply
with no lock and no receive timeout (bcs_server.py:105, 123-148).  A REQ socket refuses a new send while a reply is
pending, and a pending receive that the caller cancels leaves it waiting for that reply.  ``awaiting_reply`` models
that state (default off): while it is set, every request of the nested server raises, as the upstream send would, and
``zmq_move_motor``/``zmq_stop_motor`` swallow the error in their worker thread as the upstream wrappers do.  The
package tests use it to show that a StopMotor sent behind a cancelled GetMotorFull never reaches the server
(review/lists/r22-probe_bcs_req_race.py reproduces the same with a running move).
"""

import asyncio
import threading


class _FakeBCSServer:
    """In-memory replies for the three BCSServer coroutines BCSMotor calls."""

    def __init__(self):
        self.position = 0.0                 # placeholder
        self.goal = 0.0                     # placeholder
        self.move_complete = True
        self.stop_confirms = True           # when False, StopMotor succeeds but Move Complete stays False
        self.fail_queries = False           # when True, GetMotorFull returns success=False
        self.malformed_queries = False      # when True, GetMotorFull returns an empty data list
        self.fail_move = False              # when True, MoveMotor returns success=False
        self.awaiting_reply = False         # when True, the REQ socket still waits for a reply: every send fails
        self.queries = 0                    # placeholder (test counter)
        self.stop_requests = 0              # placeholder (test counter of StopMotor requests that reached the server)

    def _send(self, command):
        if self.awaiting_reply:
            raise RuntimeError(f"placeholder: {command} refused, the REQ socket still waits for a reply (EFSM)")

    async def get_motor_full(self, motors=None):
        self._send("GetMotorFull")
        self.queries += 1
        if self.fail_queries:
            return {"success": False, "error_description": "placeholder: the GetMotorFull request failed"}
        if self.malformed_queries:
            return {"success": True, "data": []}
        return {"success": True,
                "data": [{"Raw Motor Position": self.position,
                          "Motor State": {"Move Complete": self.move_complete}}]}

    async def move_motor(self, motors=None, goals=None):
        self._send("MoveMotor")
        if self.fail_move:
            return {"success": False, "error_description": "placeholder: the MoveMotor request failed"}
        self.goal = float(goals[0])
        self.position = self.goal
        self.move_complete = True
        return {"success": True}

    async def stop_motor(self, motors=None):
        self._send("StopMotor")
        self.stop_requests += 1
        if self.stop_confirms:
            self.move_complete = True
        return {"success": True}


class FakeBcsMotor:
    def __init__(self, **_options):
        self.name = "bcs_motor"                     # placeholder
        self.originalName = "BCS Motor 1"           # placeholder
        self.itemType = "motor"
        self.prefix = ""
        self.units = "mm"                           # placeholder (the deployment's configured unit)
        self.host = "127.0.0.1"                     # placeholder
        self.port = 5577                            # placeholder
        self.bcs_server = _FakeBCSServer()
        self._connected = True
        self._position = 0.0                        # placeholder
        self.velocity = 0.0                         # placeholder
        self.acceleration = 0.0                     # placeholder
        self.timeout = 60.0                         # placeholder
        self.settle_time = 0.0                      # placeholder
        self.isMoving = False
        self.moveComplete = True

    @staticmethod
    def _in_thread(coroutine):
        """Run the coroutine in a worker thread, as the upstream ZeroMQ wrappers do."""
        def run_in_thread():
            asyncio.run(coroutine)

        thread = threading.Thread(target=run_in_thread, daemon=False)
        thread.start()
        thread.join()

    async def zmq_get_motor_full_async(self, motor_name):
        """The upstream async query: raise on an unsuccessful or empty reply, else return the data list."""
        response = await self.bcs_server.get_motor_full([motor_name])
        if not response.get("success", False):
            raise RuntimeError(f"Failed to get motor data: {response.get('error_description', 'Unknown error')}")
        data = response.get("data")
        if not data:
            raise ValueError("No data found in the response.")
        return data

    def zmq_move_motor(self, motors, goals):
        """The upstream wrapper: send MoveMotor in a worker thread and do not surface its exceptions."""
        def request():
            return self.bcs_server.move_motor(motors, goals)

        # The upstream thread target is asyncio.run(self._zmq_move_motor_async(...)); an exception there is not
        # returned to this caller.  Keep the same observable contract: send the request, ignore a failed reply.
        self._in_thread(request())

    def zmq_stop_motor(self, motors):
        """The upstream wrapper: send StopMotor in a worker thread and do not surface its exceptions."""
        def request():
            return self.bcs_server.stop_motor(motors)

        self._in_thread(request())

    def stop(self, *, success=False):
        """The upstream stop: send StopMotor for this motor and set isMoving=False (moveComplete is unchanged)."""
        self.zmq_stop_motor([self.originalName])
        self.isMoving = False
