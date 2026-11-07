"""OpenMHS driver for gh.dayr3n33/instruments: an Ismatec pump controller (blocked: no confirmed stop).

The card lists three classes of the clone.  This package drives
``instruments.ismatec.ismatec:Ismatec`` (the entry symbol at
``src/instruments/ismatec/ismatec.py:20``), a serial pump controller whose
public methods queue text commands for one worker thread.  The other two
card entries are not usable device implementations: ``Ika`` inherits
``Instrument`` but defines no ``_process_request``, so its queued commands
never reach the line (``src/instruments/ika/ika.py:41-69`` against
``src/instruments/instrument.py:42-48``), and ``Bronkhorst`` calls
``super().__init__(port)`` on ``object`` and has no ``_queue``
(``src/instruments/bronkhorst/bronkhorst.py:19-27``).  See facts.md.

The driver shape is a direct decorated ``Driver`` rather than the card's
``PythonObjectDriver`` helper: every upstream control returns immediately
and delivers its reply through a callback from the worker thread
(``src/instruments/ismatec/ismatec.py:44-60, 62-84``), which the family
grammar cannot express.  The driver queues a command and waits, within a
bound, for that callback.  The callback reports only that the worker wrote
the command to the serial port: for start, stop and set_flowrate the
upstream reads no reply (``ismatec.py:44-53, 58-59``).

The only writable parameter is the pump speed set point.  The clone names
its unit (pump rpm, ``1/min``) but no range, so the write is
``Limit.operator_required`` and the runtime refuses every write until the
site overlay supplies a range.

BLOCKED (model review, 2026-11-05).  The upstream stop is the command ``1I``
(``stop()``, ``ismatec.py:48-49, 67-70``), but nothing confirms it and its
delivery is not assured.  The worker writes ``1I`` and calls back with
``True`` without reading a reply, and the class has no run-state query.
Every request shares one queue served by one worker thread
(``instrument.py:32, 42-48, 60-63``), so a stop waits behind every request
queued before it; ``_process_queue`` has no exception handler, so a request
that raises (a ``1S`` reply that ``float()`` cannot parse, ``ismatec.py:57``,
an empty read after the ``timeout=0.5`` among them, or a failed serial
write) ends the worker, after which no queued request, the stop included, is
written, while ``stop()`` still returns normally.  The runtime itself reads
``rate`` before and after every effectful command, so one unparsable reply
is enough.  The author bound the queued stop as the ``@estop`` and as a
``safe_state=True`` action that returned at once, so every e-stop was
reported completed with the safe state achieved, also after the worker had
ended (``review/lists/hw2-dayr3n33-probe_dead_worker.py``).  Under the
user's decision of 2026-11-04 (an actuator without a source-backed,
confirmed stop stays blocked) the e-stop still queues ``1I`` as a
best-effort step and then raises ``MHS.SAFETY.SAFE_STATE_UNREACHED`` (the
latch stays engaged and the runtime's background retry queues ``1I`` again),
and the stop is an ordinary action.  The gate therefore fails G3 (SAFE-045:
an R2 hardware driver with neither an independent stop nor a safe-state
action); that is the expected blocked state.

The package is model-authored and unreviewed (``reviewed_by`` is null); it
was checked on the fake backend only and has never opened a serial port.
"""

from __future__ import annotations

import math
import threading

from mhs.driver import (
    Driver,
    DriverFailed,
    Fact,
    Field,
    Limit,
    OutcomeUnknown,
    action,
    estop,
    read,
    write,
)


class IsmatecPump(Driver):
    """An Ismatec pump controller over the upstream queued serial interface."""

    device_id = "ismatec"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "instruments.ismatec.ismatec:Ismatec"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeIsmatec"}
    vendor = "Ismatec"
    model = "pump controller"
    display_name = "Ismatec pump controller (instruments.ismatec.ismatec:Ismatec)"
    tags = ["pump", "peristaltic", "serial", "queued"]
    facts = [
        Fact("Ismatec is an Ismatec pump controller", source="upstream_code",
             ref="src/instruments/ismatec/ismatec.py:20-21"),
        Fact("_process_request writes '1H' for the start request and '1I' for the stop request, each followed by "
             "chr(13)", source="upstream_code", ref="src/instruments/ismatec/ismatec.py:44-49"),
        Fact("For set_flowrate _process_request writes '1S' followed by str(int(flowrate)).zfill(5); for "
             "get_flowrate it writes '1S', sleeps 0.3 and converts the reply line, split at '\\r' and stripped of '*', "
             "with float()", source="upstream_code", ref="src/instruments/ismatec/ismatec.py:50-57"),
        Fact("The set_flowrate and get_flowrate docstrings name the value pump rpm (1/min)",
             source="upstream_code", ref="src/instruments/ismatec/ismatec.py:72-84"),
        Fact("_process_request calls the callback with its response and then sleeps 0.3; the response stays True "
             "for start, stop and set_flowrate, for which no reply is read",
             source="upstream_code", ref="src/instruments/ismatec/ismatec.py:44-60"),
        Fact("start, stop, set_flowrate and get_flowrate only queue a request that carries the caller's callback",
             source="upstream_code", ref="src/instruments/ismatec/ismatec.py:62-84"),
        Fact("The class body defines no run-state query; its only read of the serial line is the readline of the "
             "get_flowrate request", source="upstream_code", ref="src/instruments/ismatec/ismatec.py:20-90"),
        Fact("Instrument.__init__ stores the port and creates the request queue, a queue.Queue",
             source="upstream_code", ref="src/instruments/instrument.py:24-32"),
        Fact("_process_queue takes one request at a time from the queue and calls _process_request with it in a "
             "while True loop that has no exception handler", source="upstream_code",
             ref="src/instruments/instrument.py:42-48"),
        Fact("_queue_request puts the request on the queue and returns", source="upstream_code",
             ref="src/instruments/instrument.py:50-58"),
        Fact("_start_threads starts one daemon thread that runs _process_queue", source="upstream_code",
             ref="src/instruments/instrument.py:60-63"),
        Fact("connect() creates Serial(port=self._port, baudrate=9600, bytesize=8, parity='N', stopbits=1, "
             "timeout=0.5)", source="upstream_code", ref="src/instruments/ismatec/ismatec.py:39-40"),
        Fact("connect() then writes '@1' and '1M', each followed by chr(13)", source="upstream_code",
             ref="src/instruments/ismatec/ismatec.py:41-42"),
        Fact("main() calls connect() and then _start_threads()", source="upstream_code",
             ref="src/instruments/ismatec/ismatec.py:86-90"),
        Fact("ismatec.py imports Serial from serial and Instrument from instruments.instrument",
             source="upstream_code", ref="src/instruments/ismatec/ismatec.py:8-9"),
        Fact("The project image installs pyserial, PyYAML, coloredlogs, numpy, scipy and opcua with pip",
             source="upstream_code", ref="src/project/Dockerfile:6"),
        Fact("The project image's entry point runs python -m project.ismatec_deltav", source="upstream_code",
             ref="src/project/Dockerfile:15"),
        Fact("project/ismatec_deltav.py constructs Ismatec('/dev/ttyUSB0') and calls main() at import; run_command "
             "calls start() when START_CONTROLLER is true and stop() when it is false, and main() sets run_command as "
             "the OPC subscriber's callback", source="upstream_code", ref="src/project/ismatec_deltav.py:16-33"),
        Fact("docker-compose.yml builds the project image from src/project/Dockerfile and runs it with "
             "/dev/ttyUSB0 mapped in and restart unless-stopped", source="upstream_code",
             ref="docker-compose.yml:4-14"),
    ]
    safe_state = ("none confirmed: the e-stop queues the native stop 1I and reports SAFE_STATE_UNREACHED; the upstream "
                  "reads no reply to 1I and has no run-state query, the stop waits behind requests queued before it, "
                  "and once a request raises, the single worker thread ends and nothing queued is written, so the "
                  "pump may still run")

    #: The driver-side bound on a queued request's callback (not a device fact).
    _CALLBACK_TIMEOUT_S = 5.0

    @classmethod
    def _call_and_wait(cls, method, *args):
        """Call a queued native method and wait for the callback that carries its reply.

        The upstream method returns before its worker thread has written the
        command.  The callback is the only completion signal the class offers,
        and for start, stop and set_flowrate it says only that the worker wrote
        the command.  A callback that never arrives (the worker is busy, or it
        ended after an exception) leaves the outcome unknown.
        """
        finished = threading.Event()
        replies = []

        def callback(value=None):
            replies.append(value)
            finished.set()

        method(*args, callback=callback)
        if not finished.wait(cls._CALLBACK_TIMEOUT_S):
            raise OutcomeUnknown(
                f"{getattr(method, '__name__', 'the native method')} did not invoke its callback within "
                f"{cls._CALLBACK_TIMEOUT_S:.0f} s; the request may still be written later, or never if the upstream "
                f"worker thread has ended"
            )
        return replies[0] if replies else None

    # -- reads ------------------------------------------------------------------------------------------------
    @read("rate", unit="/min",
          description="Pump speed reported by get_flowrate; the upstream docstring names it pump rpm, and the clone "
                      "does not say whether the pump answers with the set or the measured speed")
    def rate(self):
        value = self._call_and_wait(self.native.get_flowrate)
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"get_flowrate returned {value!r}, not a pump speed") from exc
        if not math.isfinite(number):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"get_flowrate returned {value!r}, not a finite pump speed")
        return number

    # -- the one write ----------------------------------------------------------------------------------------
    @write("setpoint", unit="/min",
           description="Pump speed set point; the native command carries int(value), zero-padded to at least five "
                       "digits",
           limit=Limit.operator_required(
               "no line of the clone states a pump speed range; the operator supplies the range of this unit"))
    def set_setpoint(self, value):
        applied = int(value)        # the same conversion the upstream applies before it writes '1S'
        self._call_and_wait(self.native.set_flowrate, applied)
        return applied

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.dayr3n33.start_pump.v1",
            description="Start the pump with the native start command 1H; the upstream reads no reply to it",
            output={"written": Field(
                "boolean",
                description="True once the upstream callback reported that its worker wrote 1H to the serial port; "
                            "not a pump acknowledgement")})
    def start_pump(self):
        self._call_and_wait(self.native.start)
        return {"written": True}

    @action(name="x-cap.dayr3n33.stop_pump.v1",
            description="Send the native stop command 1I (an ordinary command, not a confirmed safe state); the "
                        "upstream reads no reply to it",
            output={"written": Field(
                "boolean",
                description="True once the upstream callback reported that its worker wrote 1I to the serial port; "
                            "not a pump acknowledgement")})
    def stop_pump(self):
        self._call_and_wait(self.native.stop)
        return {"written": True}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="stop")
    def stop(self):
        """Queue the native stop 1I, then refuse to certify a safe state (model review, 2026-11-05).

        The runtime latches first.  stop() only queues the request: the upstream reads no reply to 1I, has no
        run-state query, serves the queue with one worker that ends on the first exception of any request, and
        returns normally either way, so a normal return would prove nothing.
        """
        self.native.stop()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the native stop 1I was queued for the upstream's single worker thread, which reads no reply to it and "
            "has no run-state query; the stop waits behind earlier requests and is never written once the worker "
            "has ended after an exception, so nothing confirms that the pump stopped")
