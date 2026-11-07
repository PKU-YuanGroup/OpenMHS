"""OpenMHS driver for gh.sciencecorp/galago-tools: the pack's Opentrons OT-2 tool (``tools.opentrons2.driver:Ot2Driver``).

Re-authored by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 (the user's decision of 2026-11-05:
Claude authors, Claude Sonnet reviews).  The earlier DeepSeek package served the pack's SpectraMax plate reader, whose
client has no abort command (blocked, G3.NO_ESTOP).  Galago Tools is a pack of tool drivers; its OT-2 tool is the one
whose work can be stopped: a protocol run on the robot server has the run action ``stop`` (driver.py:167-181) and a
status that can be read (199-214).  The card's routing override re-selects ``Ot2Driver`` (p3-reauthor-routing.json).

The OT-2 runs uploaded Python protocols that move the pipette gantry and pipette (the pack's example protocol picks up
and drops a tip, tools/opentrons2/protocols/example.py:86-89), so the device is R2 (pipetting).  This package serves:

* ``x-cap.sciencecorp.ot2_run_protocol.v1`` (R2): upload one operator-approved protocol file, create a run of it and
  play it (driver.py:62-123); it returns the run id and the status read right after ``play``.  The protocol path is
  ``Limit.operator_required``: the operator's site limits list the exact files a model may run;
* ``x-cap.sciencecorp.ot2_stop_run.v1`` (the safe-state action): stop this endpoint's run and confirm it;
* reads of the run id this endpoint started and of that run's status.

The stop.  The e-stop and the safe-state action read the run's status; unless it is already ``succeeded``, ``stopped``
or ``failed`` (the states that end the upstream's ``wait_for_completion``, driver.py:227-231), they send the run action
``stop`` and read the status again every ``POLL_S`` until it is one of those three, for at most ``STOP_CONFIRM_S``;
otherwise the stop fails and the runtime reports ``MHS.SAFETY.SAFE_STATE_UNREACHED``, keeps the latch and retries.
The run is not deleted (the upstream's ``cancel_protocol`` deletes it right after the stop, 184-190, which would make
the status unreadable).  ``play`` is sent only under the same lock and only if the operation was not cancelled, so an
e-stop never runs between that check and the play request (it waits for one play request in flight).  With no run of
this endpoint, the stop reads the robot server's health (``ping``, 20-30) and has nothing to stop: runs started by
other clients (the Opentrons App, another galago instance) are not stopped by this package.

A run this endpoint created but never played (an e-stop that lands during the upload cancels the play) is stopped the
same way.  The clone shows neither the status word of a created, unplayed run nor whether the robot server accepts
``stop`` for it: if the server refuses that stop and the run does not read succeeded, stopped or failed, the stop fails
closed (latch kept, retried) and ``run_protocol`` answers Busy until a stop of that run succeeds.

Every request goes through the hardware backend's bounded port of ``Ot2Driver`` (native.py): the upstream's requests
have no timeout.  A transport failure of an effectful request is an unknown outcome; of a read, a failure.
"""

from __future__ import annotations

import threading
import time

from mhs.driver import Busy, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

OT2 = "tools/opentrons2/driver.py"
SERVER = "tools/opentrons2/server.py"
BASE = "tools/base_server.py"

#: The run states that end the upstream's wait_for_completion (driver.py:227-231 without "blocked-by-open-door",
#: which pauses a run that can continue): the run no longer executes.
TERMINAL = ("succeeded", "stopped", "failed")
#: How long the stop waits for a terminal status after the stop request, and how often it reads it.
STOP_CONFIRM_S = 8.0
POLL_S = 0.25

PROTOCOL = Limit.operator_required(
    "a protocol file runs arbitrary pipetting on the OT-2; the operator's site limits list the exact files (absolute "
    "paths on the driver host) a model may upload and run")

_LOCK_GUARD = threading.Lock()


class GalagoOt2(Driver):
    device_id = "galago-ot2"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "tools.opentrons2.driver:Ot2Driver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOt2Driver"}
    vendor, model = "Opentrons", "OT-2 (galago-tools opentrons2 tool)"
    display_name = "Opentrons OT-2 through galago-tools' Ot2Driver"
    tags = ["opentrons", "ot-2", "liquid handler", "pipetting", "http", "galago"]
    safe_state = ("no protocol run of this endpoint executing: the e-stop sends the run action stop and reads the "
                  "run's status until it is succeeded, stopped or failed (driver.py:175-181, 199-231); the robot's "
                  "gantry, tips and liquids stay where the run left them")
    facts = [
        Fact("Ot2Driver keeps the robot address, the port (default 31950), the current run id, the base URL and the "
             "header Opentrons-Version: 2", source="upstream_code", ref=f"{OT2}:10-18"),
        Fact("ping sends GET /health and raises unless the status code is 200", source="upstream_code",
             ref=f"{OT2}:20-30"),
        Fact("upload_and_schedule_protocol posts the file as protocol.py to /protocols, then posts a run of that "
             "protocol to /runs and keeps its id as run_id", source="upstream_code", ref=f"{OT2}:62-106"),
        Fact("start_run posts the run action play to /runs/<id>/actions", source="upstream_code",
             ref=f"{OT2}:108-123"),
        Fact("pause_protocol and resume_protocol post the run actions pause and play for the current run",
             source="upstream_code", ref=f"{OT2}:125-165"),
        Fact("cancel_protocol posts the run action stop, then deletes the run, only logging a failed delete, and "
             "forgets the run id", source="upstream_code", ref=f"{OT2}:167-197"),
        Fact("get_run_status gets /runs/<id> with a 30 s timeout and returns the JSON body", source="upstream_code",
             ref=f"{OT2}:199-214"),
        Fact("wait_for_completion reads data.status every 2 s: succeeded ends it, and stopped, failed or "
             "blocked-by-open-door raise", source="upstream_code", ref=f"{OT2}:216-241"),
        Fact("close cancels an active run and only logs an error", source="upstream_code", ref=f"{OT2}:308-315"),
        Fact("No requests call of Ot2Driver other than get_run_status passes a timeout", source="upstream_code",
             ref=f"{OT2}:20-197"),
        Fact("ABCToolDriver answers any attribute it does not define with a function that returns None",
             source="upstream_code", ref=f"{BASE}:28-34"),
        Fact("The OT-2 tool server's configure step leaves the Ot2Driver construction commented out, so its "
             "commands reach the ToolServer's ABCToolDriver", source="upstream_code", ref=f"{SERVER}:24-27"),
        Fact("The tool server's RunProgram writes the script with injected variables to a temporary file and runs "
             "it with start_protocol", source="upstream_code", ref=f"{SERVER}:98-121"),
        Fact("The pack's example OT-2 protocol loads a p300 single-channel pipette, picks up a tip and drops it",
             source="upstream_code", ref="tools/opentrons2/protocols/example.py:86-89"),
    ]

    # -- locks -----------------------------------------------------------------------------------------------------
    def _stop_lock(self) -> threading.Lock:
        lock = getattr(self, "_ot2_stop_lock", None)
        if lock is None:
            with _LOCK_GUARD:
                lock = getattr(self, "_ot2_stop_lock", None)
                if lock is None:
                    lock = threading.Lock()
                    self._ot2_stop_lock = lock
        return lock

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _status(self, run_id: str) -> str:
        try:
            body = self.native.get_run_status(run_id)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            raise DriverFailed("MHS.DEVICE.FAULTED", f"reading run {run_id} failed ({type(exc).__name__})") from exc
        status = body.get("data", {}).get("status") if isinstance(body, dict) else None
        if not isinstance(status, str) or not status:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"run {run_id}: the status response has no data.status")
        return status

    def _stop_owned_run(self) -> dict:
        """Stop this endpoint's run and read its status until it is terminal (see the module docstring)."""
        with self._stop_lock():
            run_id = self.native.run_id
            if run_id is None:
                try:
                    self.native.ping()
                except Exception as exc:  # noqa: BLE001 - a silent robot server is an unconfirmed stop
                    raise DriverFailed("MHS.DEVICE.FAULTED", f"no run of this endpoint, and the robot server did not "
                                       f"answer /health ({type(exc).__name__})") from exc
                return {"run_id": None, "status": None}
            status = self._status(run_id)
            if status in TERMINAL:
                return {"run_id": run_id, "status": status}
            deadline = time.monotonic() + STOP_CONFIRM_S
            try:
                self.native.stop()
            except Exception as exc:  # noqa: BLE001 - re-read below: a refused stop of a run that just ended is fine
                status = self._status(run_id)
                if status in TERMINAL:
                    return {"run_id": run_id, "status": status}
                raise DriverFailed("MHS.DEVICE.FAULTED", f"the stop request for run {run_id} failed "
                                   f"({type(exc).__name__}); the run reports {status!r}") from exc
            while True:
                status = self._status(run_id)
                if status in TERMINAL:
                    return {"run_id": run_id, "status": status}
                if time.monotonic() >= deadline:
                    raise DriverFailed("MHS.DEVICE.FAULTED", f"run {run_id} still reports {status!r} "
                                       f"{STOP_CONFIRM_S} s after the stop request")
                time.sleep(POLL_S)

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("run_id", type="string",
          description="The id of the last run this endpoint created; empty before the first run")
    def run_id(self):
        run_id = self.native.run_id
        return "" if run_id is None else str(run_id)

    @read("run_status", type="string",
          description="The robot server's status of that run (data.status, driver.py:223); empty without a run")
    def run_status(self):
        run_id = self.native.run_id
        return "" if run_id is None else self._status(run_id)

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.sciencecorp.ot2_run_protocol.v1", risk="R2",
            description="Upload an operator-approved protocol file, create a run of it and play it",
            input={"protocol": Field("string", description="Path of the protocol file on the driver host; one of "
                                                            "the operator's approved files",
                                     limit=PROTOCOL)},
            output={"run_id": Field("string", description="The run created and played"),
                    "protocol": Field("string", description="The protocol file uploaded"),
                    "status": Field("string", description="The run's status read right after play")})
    def run_protocol(self, protocol):
        self.check_cancelled()
        previous = self.native.run_id
        if previous is not None:
            status = self._status(previous)
            if status not in TERMINAL:
                raise Busy(f"run {previous} of this endpoint still reports {status!r}; stop it first")
        try:
            run_id = self.native.upload_and_schedule_protocol(protocol)
        except Exception as exc:  # noqa: BLE001 - a protocol or a run may exist on the robot now
            raise OutcomeUnknown(f"uploading {protocol!r} or creating its run failed ({type(exc).__name__}); a "
                                 "protocol or an idle run may exist on the robot") from exc
        with self._stop_lock():
            # The e-stop cancels operations before it stops (server order): checked under the stop lock, a cancelled
            # operation never plays, and an e-stop never runs between this check and the play request.
            self.check_cancelled()
            try:
                self.native.start_run(run_id)
            except Exception as exc:  # noqa: BLE001 - the run may be playing
                raise OutcomeUnknown(f"play for run {run_id} failed ({type(exc).__name__}); the run may be "
                                     "executing") from exc
        return {"run_id": run_id, "protocol": protocol, "status": self._status(run_id)}

    @action(name="x-cap.sciencecorp.ot2_stop_run.v1", safe_state=True, risk="R2",
            description="Stop this endpoint's run and read its status until it is succeeded, stopped or failed",
            output={"run_id": Field("string", nullable=True, description="The run stopped (null: none of this "
                                                                           "endpoint)"),
                    "status": Field("string", nullable=True, description="Its terminal status (null: no run)")})
    def stop_run(self):
        return self._stop_owned_run()

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="run action stop", latency_ms=10000)
    def stop(self):
        """The runtime latches and cancels first; then this endpoint's run is stopped and its status confirmed."""
        self._stop_owned_run()

    def teardown(self):
        self.native.close()   # driver.py:308-315 (the port's): cancel and delete an active run
