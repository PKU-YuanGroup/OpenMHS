"""OpenMHS driver for gh.ad-sdl/ot2_module: an Opentrons OT-2 over its HTTP server.

A direct Driver (decorated methods) over the upstream client ``ot2_interface.ot2_driver_http:OT2_Driver``.  The
upstream class is the HTTP client used by the MADSci node: it uploads a protocol file, creates a run, and sends
the Opentrons ``play``, ``pause`` and ``stop`` run actions (src/ot2_interface/ot2_driver_http.py:132-278).  This
driver keeps that protocol-run interface.  It does not expose per-well aspirate/dispense actions because the clone
has no command that targets a loaded labware well: ``stream`` accepts a command type and an opaque params object
(src/ot2_interface/ot2_driver_http.py:463-548), and the shipped streaming example loads labware and moves a pipette
relative, but never aspirates or dispenses (tests/test_ot2_streaming.py:12-65).

A protocol file decides what the robot does in its run (volumes, labware, modules, motion); the clone uploads it as
it is (src/ot2_interface/ot2_driver_http.py:146-158).  The envelope therefore bounds which files may run:
``protocol_path`` is ``Limit.operator_required`` and every start is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
operator overlay lists the approved protocol paths as an allowed set (see ``site-limits.example.json``).

The node's ``safety_stop`` is not used: it only sets a flag (src/ot2_rest_node.py:522-527).  The e-stop and the
safe-state action read the robot's run list and send the run stop action to every run that is running, paused,
finishing or in a status the clone does not name, and to a run of this driver whose play request may be in flight;
each stop is confirmed by a fresh read of the run, which must report stop-requested, stopped, succeeded or failed,
otherwise the stop fails ``MHS.SAFETY.SAFE_STATE_UNREACHED`` and the runtime keeps the latch.  The stop path sends
the request ``OT2_Driver.cancel`` builds (src/ot2_interface/ot2_driver_http.py:271-277) through the upstream's
``send_request`` (:444-461) with a timeout, because ``cancel`` and ``get_runs`` pass none (:275-277, :370) and the
e-stop must not wait forever for a silent robot.

Every Fact cites a line of the clone at the pinned commit (39ffdfdb73c3bc08bb988c5140cfc1af3cecbd0c).  This package
is model-authored and unreviewed: the acceptance gate runs the fake backend only.
"""

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

_ROBOT_STATES = ("idle", "running", "finishing", "failed", "paused", "offline", "stopped")
#: Run statuses of the clone's RunStatus in which a run does not move and does not go on by itself
#: (src/ot2_interface/ot2_driver_http.py:29-39).  Every other status, one the clone does not name included, is
#: treated as a run to stop.
_AT_REST = frozenset({"idle", "succeeded", "failed", "stop-requested", "stopped"})
#: Statuses that confirm a stop action when read after it (or show that the run had already ended).
_STOP_CONFIRMED = frozenset({"stop-requested", "stopped", "succeeded", "failed"})
#: Timeout in seconds of every request of the stop path.  The package's choice, not an upstream or device value:
#: the upstream stop and run reads pass no timeout (src/ot2_interface/ot2_driver_http.py:275-277, :370).
_STOP_REQUEST_TIMEOUT_S = 5.0
_UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
_PROTOCOL_REASON = (
    "Which protocol files may run is the operator's decision: a protocol decides the volumes, labware, modules and "
    "motion of its run, the clone uploads it unchecked (src/ot2_interface/ot2_driver_http.py:146-158) and names no "
    "protocol or directory a deployment may run. The overlay lists the approved paths as an allowed set.")


class Ot2(Driver):
    device_id = "ot2"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "ot2_interface.ot2_driver_http:OT2_Driver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOt2"}
    vendor, model = "Opentrons", "OT-2"
    display_name = "Opentrons OT-2 liquid handler (ot2_interface.OT2_Driver)"
    tags = ["liquid-handler", "pipette", "protocol-runner", "http"]
    facts = [
        Fact("The module is a MADSci node for Opentrons liquid handlers, the OT-2 and the Flex",
             source="vendor_doc", ref="README.md:3"),
        Fact("OT2_Driver builds the robot base URL from config.ip and config.port and sets the Opentrons-Version: 2 "
             "request header", source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:71-72"),
        Fact("The constructor probes /robot/lights and raises RuntimeError when the probe does not return "
             "HTTP 200", source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:70-77"),
        Fact("After the probe the constructor switches the robot lights on; when the probe does not report them off "
             "it first switches them off and sleeps one second", source="upstream_code",
             ref="src/ot2_interface/ot2_driver_http.py:79-84"),
        Fact("change_lights_status posts {'on': status} to /robot/lights", source="upstream_code",
             ref="src/ot2_interface/ot2_driver_http.py:419-424"),
        Fact("transfer opens the local protocol file, posts it to /protocols with timeout=600, prints the answer's "
             "status code, text and reason, creates a run at /runs with timeout=60 and returns the protocol id and "
             "run id", source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:146-169"),
        Fact("resume posts actionType 'play' to /runs/{run_id}/actions without a timeout and returns the response "
             "without checking its status code", source="upstream_code",
             ref="src/ot2_interface/ot2_driver_http.py:249-256"),
        Fact("cancel posts actionType 'stop' to /runs/{run_id}/actions without a timeout and returns the response "
             "without checking its status code", source="upstream_code",
             ref="src/ot2_interface/ot2_driver_http.py:271-278"),
        Fact("execute compares the answer of the play action with 201, which it calls the good response code for "
             "this endpoint, and only prints when it differs", source="upstream_code",
             ref="src/ot2_interface/ot2_driver_http.py:188-195"),
        Fact("execute posts play and polls check_run_status every second, catching and printing every exception, "
             "until the run is failed, succeeded or stopped", source="upstream_code",
             ref="src/ot2_interface/ot2_driver_http.py:184-210"),
        Fact("RunStatus names idle, running, finishing, succeeded, failed, paused, stop-requested and stopped",
             source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:29-39"),
        Fact("check_run_status reads /runs/{run_id}, prints when the answer is not HTTP 200 and constructs RunStatus "
             "from the response data.status", source="upstream_code",
             ref="src/ot2_interface/ot2_driver_http.py:294-300"),
        Fact("get_run returns the JSON of GET /runs/{run_id} and only prints when the answer is not HTTP 200",
             source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:317-323"),
        Fact("get_runs sends GET /runs without a timeout, maps the id, protocolId, status and current of each run in "
             "its data list to runID, protocolID, status and current, and returns None when /runs does not answer "
             "HTTP 200", source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:369-386"),
        Fact("get_robot_status returns 'offline' when get_runs returns None, skips succeeded and stop-requested "
             "runs, returns the status of the first other run whose status RunStatus names, and returns 'idle' "
             "when none does", source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:396-409"),
        Fact("reset_robot_data sends DELETE /runs/{runID} for every run whose status is failed",
             source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:411-417"),
        Fact("send_request joins base_url and the request extension, sets the Opentrons-Version: 2 header when no "
             "headers are given, requires a method keyword and passes the keyword arguments to requests.request",
             source="upstream_code", ref="src/ot2_interface/ot2_driver_http.py:444-461"),
        Fact("The protocol generator's Temperature_Set command sets a temperature module to an integer change_temp",
             source="upstream_code", ref="src/ot2_interface/protopiler/config.py:262-268"),
        Fact("The protocol generator's Move_Labware command moves labware inside the Flex with the gripper",
             source="upstream_code", ref="src/ot2_interface/protopiler/config.py:271-272"),
        Fact("OT2Node.execute sets self.run_id to the run id before OT2_Driver.execute and back to None after it "
             "returns", source="upstream_code", ref="src/ot2_rest_node.py:436-438"),
        Fact("OT2Node.execute answers a run whose status is stopped with the message that the OT2 is successfully "
             "IDLE after stopping a protocol", source="upstream_code", ref="src/ot2_rest_node.py:454-465"),
        Fact("OT2Node.safety_stop logs and sets node_status.stopped; it sends no stop to the robot",
             source="upstream_code", ref="src/ot2_rest_node.py:522-527"),
        Fact("OT2Node.cancel logs and calls self.ot2_interface.cancel(self.run_id)",
             source="upstream_code", ref="src/ot2_rest_node.py:529-534"),
    ]
    safe_state = (
        "Every run the robot lists as running, paused, finishing or in a status the clone's RunStatus does not "
        "name, and a new run of this driver whose play may be in flight, got the run stop action and then read "
        "stop-requested, stopped, succeeded or failed (stop-requested: the stop was accepted, motion may not have "
        "ended); a run stop over the HTTP API, not a hardware stop: it neither resets module set points nor stops "
        "anything outside a run, and no run is started")

    def setup(self):
        self._active_run_id = None
        # The run whose play request this driver has sent and not yet seen answered: an idle run may start then.
        self._play_pending = None

    # -- reads --------------------------------------------------------------------------------------------------
    @read("robot_status", type="string", enum=_ROBOT_STATES,
          description="The upstream get_robot_status(): the status of the first run in the robot's list that is "
                      "not succeeded or stop-requested (an older stopped or failed run can hide a newer running "
                      "one; read runs for every run), offline when /runs does not answer HTTP 200, idle when no "
                      "run matches")
    def robot_status(self):
        return self.native.get_robot_status()

    @read("runs", type="array",
          items=Field("object", description="One stored run as the upstream get_runs() summarizes it",
                      properties={
                          "runID": Field("string", description="Run identifier"),
                          "protocolID": Field("string", description="Identifier of the uploaded protocol"),
                          "status": Field("string", description="Run status text"),
                          "current": Field("boolean", description="Whether the robot marks this as the current "
                                                                  "run"),
                      }),
          description="All runs stored on the robot; the read fails when /runs does not answer HTTP 200")
    def runs(self):
        runs = self.native.get_runs()
        if runs is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the robot did not answer GET /runs with HTTP 200")
        return runs

    @read("active_run_id", type="string",
          description="Identifier of the run most recently created through this driver (kept after the run ends "
                      "or is stopped); empty when none")
    def active_run_id(self):
        return self._active_run_id or ""

    @read("active_run_status", type="string",
          description="Status the robot reports for the run most recently created through this driver, or idle "
                      "when there is none")
    def active_run_status(self):
        run_id = self._active_run_id
        if not run_id:
            return "idle"
        status = self.native.check_run_status(run_id)
        return getattr(status, "value", str(status))

    # -- the primary control ------------------------------------------------------------------------------------
    @action(name="x-cap.ad-sdl.start_protocol.v1",
            description="Upload an Opentrons protocol file that the operator overlay allows, create a run and send "
                        "the robot's play action; the run continues on the robot after this action returns, until "
                        "it ends or is stopped, and the protocol alone decides what the robot does in it",
            input={"protocol_path": Field("string",
                                          description="Path on the driver host of the Opentrons protocol file to "
                                                      "upload; one of the paths the operator overlay allows",
                                          limit=Limit.operator_required(_PROTOCOL_REASON))},
            output={"protocol_id": Field("string", description="Identifier assigned to the uploaded protocol"),
                    "run_id": Field("string", description="Identifier assigned to the created run"),
                    "status": Field("string", description="Run status reported by the robot right after it "
                                                           "accepted the play action")})
    def start_protocol(self, protocol_path):
        protocol_id, run_id = self.native.transfer(str(protocol_path))
        run_id = str(run_id)
        self._active_run_id = run_id
        self._play_pending = run_id
        try:
            if self.cancelled():
                self._play_pending = None
                self._stop_runs([run_id], confirmed=_STOP_CONFIRMED | {"idle"})
                raise Cancelled("the protocol start was cancelled before the play action; the run was not started")
            try:
                response = self.native.resume(run_id)
            except Exception as exc:
                raise OutcomeUnknown(f"the play request of run {run_id} failed ({type(exc).__name__}); the robot "
                                     "may have started the run") from exc
        finally:
            self._play_pending = None
        if self.cancelled():
            self._stop_runs([run_id], confirmed=_STOP_CONFIRMED | {"idle"})
            raise Cancelled("the protocol start was cancelled; the run received the stop action")
        code = getattr(response, "status_code", None)
        if code != 201:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the robot answered the play action of run {run_id} with HTTP {code}, not 201",
                               native_code=code)
        try:
            run = self.native.get_run(run_id)
        except Exception as exc:
            raise OutcomeUnknown(f"the robot accepted the play action of run {run_id}, but reading the run "
                                 f"failed ({type(exc).__name__})") from exc
        data = run.get("data") if isinstance(run, dict) else None
        status = data.get("status") if isinstance(data, dict) else None
        if not isinstance(status, str):
            raise OutcomeUnknown(f"the robot accepted the play action of run {run_id}, but did not report the "
                                 "run's status")
        return {"protocol_id": str(protocol_id), "run_id": run_id, "status": status}

    # -- safety -------------------------------------------------------------------------------------------------
    def _request(self, extension, method, **kwargs):
        """One bounded request through the upstream send_request (src/ot2_interface/ot2_driver_http.py:444-461)."""
        return self.native.send_request(extension, method=method, timeout=_STOP_REQUEST_TIMEOUT_S, **kwargs)

    def _listed_runs(self):
        """(run id, status) of every run of GET /runs, read as get_runs reads it (ot2_driver_http.py:369-381)."""
        response = self._request("runs", "GET")
        code = getattr(response, "status_code", None)
        body = response.json() if code == 200 else None
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise DriverFailed(_UNREACHED, f"GET /runs answered HTTP {code} without a run list: the runs to stop "
                                           "are unknown", native_code=code)
        listed = []
        for run in data:
            status = run.get("status") if isinstance(run, dict) else None
            run_id = run.get("id") if isinstance(run, dict) else None
            if not isinstance(run_id, str) or not run_id:
                if status in _AT_REST:
                    continue
                raise DriverFailed(_UNREACHED, f"GET /runs lists a run in status {status!r} without an id")
            listed.append((run_id, status))
        return listed

    def _stop_runs(self, run_ids, confirmed=_STOP_CONFIRMED):
        """Send the run stop action to each run and confirm it by a fresh read of the run; raise when unconfirmed."""
        stopped = []
        for run_id in run_ids:
            # The request OT2_Driver.cancel builds (ot2_driver_http.py:271-277), with a timeout.
            answer = self._request(f"runs/{run_id}/actions", "POST", json={"data": {"actionType": "stop"}})
            code = getattr(answer, "status_code", None)
            read = self._request(f"runs/{run_id}", "GET")
            read_code = getattr(read, "status_code", None)
            body = read.json() if read_code == 200 else None
            data = body.get("data") if isinstance(body, dict) else None
            status = data.get("status") if isinstance(data, dict) else None
            if status not in confirmed:
                raise DriverFailed(_UNREACHED, f"run {run_id}: the stop action was answered HTTP {code} and a fresh "
                                               f"read (HTTP {read_code}) reported {status!r}, not "
                                               f"{' or '.join(sorted(confirmed))}", native_code=code)
            stopped.append({"run_id": run_id, "status": status})
        return stopped

    def _stop_all(self):
        """Stop every run that may move, and this driver's run while its play request may be in flight."""
        pending = self._play_pending
        targets = [run_id for run_id, status in self._listed_runs()
                   if status not in _AT_REST or (run_id == pending and status == "idle")]
        return self._stop_runs(targets)

    @estop(native="send_request")
    def stop(self):
        """The native stop: the run stop action to every run that may move, each confirmed by a fresh read."""
        self._stop_all()

    @action(name="x-cap.ad-sdl.stop_active_run.v1", safe_state=True,
            description="Send the robot's run stop action to every run it lists as running, paused, finishing or "
                        "in a status the clone does not name, and to a run of this driver whose play may be in "
                        "flight, and confirm each by a fresh read; it takes no input",
            output={"stopped_runs": Field("array",
                                          items=Field("object", description="A run that received the stop action",
                                                      properties={
                                                          "run_id": Field("string", description="Run identifier"),
                                                          "status": Field("string",
                                                                          description="Status a fresh read reported "
                                                                                      "after the stop action"),
                                                      }),
                                          description="Runs that received the stop action, each confirmed; empty "
                                                      "when no run needed one")})
    def stop_active_run(self):
        return {"stopped_runs": self._stop_all()}
