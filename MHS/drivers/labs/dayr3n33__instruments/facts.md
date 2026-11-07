# Facts and tags for gh.dayr3n33/instruments

Every fact cites the clone at commit `f7198e92172c7e069af7c79ebf7ed91c7fe25ef4`.  The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Ismatec is an Ismatec pump controller | upstream_code | src/instruments/ismatec/ismatec.py:20-21 |
| _process_request writes '1H' for the start request and '1I' for the stop request, each followed by chr(13) | upstream_code | src/instruments/ismatec/ismatec.py:44-49 |
| For set_flowrate _process_request writes '1S' followed by str(int(flowrate)).zfill(5); for get_flowrate it writes '1S', sleeps 0.3 and converts the reply line, split at '\r' and stripped of '*', with float() | upstream_code | src/instruments/ismatec/ismatec.py:50-57 |
| The set_flowrate and get_flowrate docstrings name the value pump rpm (1/min) | upstream_code | src/instruments/ismatec/ismatec.py:72-84 |
| _process_request calls the callback with its response and then sleeps 0.3; the response stays True for start, stop and set_flowrate, for which no reply is read | upstream_code | src/instruments/ismatec/ismatec.py:44-60 |
| start, stop, set_flowrate and get_flowrate only queue a request that carries the caller's callback | upstream_code | src/instruments/ismatec/ismatec.py:62-84 |
| The class body defines no run-state query; its only read of the serial line is the readline of the get_flowrate request | upstream_code | src/instruments/ismatec/ismatec.py:20-90 |
| Instrument.__init__ stores the port and creates the request queue, a queue.Queue | upstream_code | src/instruments/instrument.py:24-32 |
| _process_queue takes one request at a time from the queue and calls _process_request with it in a while True loop that has no exception handler | upstream_code | src/instruments/instrument.py:42-48 |
| _queue_request puts the request on the queue and returns | upstream_code | src/instruments/instrument.py:50-58 |
| _start_threads starts one daemon thread that runs _process_queue | upstream_code | src/instruments/instrument.py:60-63 |
| connect() creates Serial(port=self._port, baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=0.5) | upstream_code | src/instruments/ismatec/ismatec.py:39-40 |
| connect() then writes '@1' and '1M', each followed by chr(13) | upstream_code | src/instruments/ismatec/ismatec.py:41-42 |
| main() calls connect() and then _start_threads() | upstream_code | src/instruments/ismatec/ismatec.py:86-90 |
| ismatec.py imports Serial from serial and Instrument from instruments.instrument | upstream_code | src/instruments/ismatec/ismatec.py:8-9 |
| The project image installs pyserial, PyYAML, coloredlogs, numpy, scipy and opcua with pip | upstream_code | src/project/Dockerfile:6 |
| The project image's entry point runs python -m project.ismatec_deltav | upstream_code | src/project/Dockerfile:15 |
| project/ismatec_deltav.py constructs Ismatec('/dev/ttyUSB0') and calls main() at import; run_command calls start() when START_CONTROLLER is true and stop() when it is false, and main() sets run_command as the OPC subscriber's callback | upstream_code | src/project/ismatec_deltav.py:16-33 |
| docker-compose.yml builds the project image from src/project/Dockerfile and runs it with /dev/ttyUSB0 mapped in and restart unless-stopped | upstream_code | docker-compose.yml:4-14 |

## Selected entry

The card lists three entry symbols.  Only `Ismatec` is a working device implementation for this package:

- `Ismatec` inherits `Instrument` and defines the `_process_request` that `Instrument` lacks, so `_process_queue`
  can execute the queued start, stop, set and get requests (`src/instruments/ismatec/ismatec.py:44-60`,
  `src/instruments/instrument.py:42-48`).
  This is the driver's `native`.
- `Ika` queues requests but defines no `_process_request`; the inherited `_process_queue` calls
  `self._process_request(**request)` (`src/instruments/instrument.py:42-48`) and the class has no such method, so
  its queued commands never reach the line (`src/instruments/ika/ika.py:41-69`).
- `Bronkhorst` does not inherit `Instrument` and calls `super().__init__(port)` on `object()`; it has no `_queue`
  either, so it cannot be constructed or queued (`src/instruments/bronkhorst/bronkhorst.py:19-27`).

The clone holds three more Ismatec modules that are not on the card: `ismatec_synchronous.py` writes the same
commands directly, without a queue, and never reads the reply to `1S` (`ismatec_synchronous.py:43-66`);
`ismatec_asynchronous.py` constructs `Serial`, which it never imports (`ismatec_asynchronous.py:6-11, 39-40`);
`ismatec_queue.py` queues byte strings for an `Instrument` without `_process_request`, like `Ika`
(`ismatec_queue.py:20-76`).  None of them reads a run state or a reply to `1I` either.

## Limits

The clone names the unit of the pump speed (pump rpm, `1/min`) but no range.  `setpoint` is therefore
`Limit.operator_required`: every write is refused with `MHS.SAFETY.LIMITS_UNSET` until the operator overlay supplies
the range of this unit.  `site-limits.example.json` is an example only; it is not a statement about any pump head or
tubing.  The upstream truncates the value with `int()` and pads it to at least five digits; it does not refuse a
longer number (`ismatec.py:51`).  The values 555, 999 and 944 in the `__main__` blocks and the OPC test
controller's `random()*1000` are example inputs, not ranges.

## Safety (blocked)

The upstream stop is the command `1I` (`stop()`, `src/instruments/ismatec/ismatec.py:48-49, 67-70`).  Nothing
confirms it:

- The worker writes `1I` and calls the callback with `True` without reading a reply (`ismatec.py:44-49, 58-59`);
  the class has no run-state query, and the clone does not say what the pump answers to `1S` after a stop, so a
  speed read proves nothing about a stop.
- Every request shares one `queue.Queue` served by one daemon worker thread (`instrument.py:24-32, 42-48, 60-63`):
  a stop waits behind every request queued before it (each followed by a 0.3 sleep; a `get_flowrate` also sleeps
  0.3 and waits for its read).
- `_process_queue` has no exception handler (`instrument.py:42-48`).  A request that raises ends the worker thread:
  a `1S` reply that `float()` cannot parse (`ismatec.py:57`), which includes an empty read after `timeout=0.5`
  (`ismatec.py:39-40`) and a reply of only `*`, or a failed serial write.  After that no queued request, the stop
  included, is ever written, and `stop()` still returns normally.  The runtime reads `rate` before and after every
  effectful command, so a single such reply is enough.

The author bound the queued stop as the `@estop` and as the `safe_state=True` action `x-cap.dayr3n33.stop_pump.v1`,
both returning at once, so the SDK reported every e-stop completed with the safe state achieved; a probe that mirrors
the upstream queue and worker (`review/lists/hw2-dayr3n33-probe_dead_worker.py` in the review batch) got such a
completed e-stop while `1I` was never written.  Under the user's decision of 2026-11-04 (an actuator without a
source-backed, confirmed stop stays blocked) the e-stop now queues `1I` as a best-effort step and raises
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held (the runtime's background retry queues `1I` again), and
`stop_pump` is an ordinary action that waits for the callback.  No text of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set and the gate fails G3 (SAFE-045), the expected blocked state.

Unblocking needs a confirmation the clone does not have: the pump's status or acknowledgement reply from a cited
manual or pinned companion source, read by a stop that does not depend on the shared queue's worker.

## Hardware path

`native.py` imports the clone's `src` package (no packaging metadata; pyserial needed) and calls `main()`, which
opens the port, writes `@1` and `1M` (the clone does not say what they set) and starts the worker; nothing there
starts the pump.  The class has no close method, so the port and the worker stay open until the process ends.  The
clone's own docker-compose service opens the same `/dev/ttyUSB0` and starts or stops the pump from an OPC UA server
(`docker-compose.yml:4-14`, `src/project/Dockerfile:15`, `src/project/ismatec_deltav.py:16-33`); it must not run
beside this package.

## Tags

pump, peristaltic, serial, queued
