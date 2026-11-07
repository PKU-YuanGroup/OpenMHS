# Facts and tags for gh.alba-synchrotron/sls-detector

Every fact cites its source at commit `961d33152af298eb4cbd311d9d185683ba992199`. The same facts are written into
`driver.py` (`facts = [...]`); the reference files are generated from the driver, not from this page. No Fact, Limit
or action in this package comes from the exemplar.

| fact | source | ref |
|---|---|---|
| Detector is the upstream client class for one SLS detector; its constructor takes the host, the control port and the stop port and keeps one Connection object for each | upstream_code | sls/client.py:142-151 |
| DEFAULT_CTRL_PORT is 1952 and DEFAULT_STOP_PORT is 1953 | upstream_code | sls/protocol.py:14-15 |
| The Mythen layout comment draws 6 modules, 10 chips per module and 128 channels per chip | upstream_code | sls/client.py:2-11 |
| Connection.connect creates a socket, sets TCP_NODELAY and connects without setting a timeout; Connection.close closes the socket | upstream_code | sls/client.py:43-53 |
| Each control-port call runs inside 'with self.conn_ctrl' and each stop-port call inside 'with self.conn_stop', so every call connects and closes the detector's shared Connection object | upstream_code | sls/client.py:94-115 |
| request_reply writes the request, reads a ResultType and raises SLSError on ResultType.FAIL | upstream_code | sls/protocol.py:328-334 |
| run_status is a stop_property that calls protocol.get_run_status on the stop connection | upstream_code | sls/client.py:378-380 |
| RunStatus names are IDLE, ERROR, WAITING, FINISHED, TRANSMITTING and RUNNING | upstream_code | sls/protocol.py:190-196 |
| start_acquisition sends START_AND_READ_ALL when keep_connection is true and otherwise sends START_ACQUISITION through request_reply | upstream_code | sls/protocol.py:696-707 |
| stop_acquisition sends STOP_ACQUISITION through request_reply on the stop connection | upstream_code | sls/protocol.py:720-722 |
| Detector.stop_acquisition uses the stop connection and Detector.start_acquisition the control connection with keep_connection=False | upstream_code | sls/client.py:382-388 |
| Detector.acquire() runs an Acquisition context with progress_interval=None and yields each frame | upstream_code | sls/client.py:390-393 |
| The raw acquisition generator keeps the control connection open while it starts the acquisition and fetches frames; an SLSError is re-raised unless the Acquisition's own stop() set _stopped, and any other exception stops the acquisition before the control socket is closed because the comment says otherwise the detector hangs | upstream_code | sls/client.py:551-573 |
| Acquisition.stop sets _stopped and calls the detector's stop_acquisition | upstream_code | sls/client.py:610-612 |
| fetch_frames yields frames while fetch_frame returns OK and ends on FINISHED; a FAIL raises SLSError, which the comment says may come from an acquisition error or a stop | upstream_code | sls/protocol.py:668-687 |
| update_client returns data_bytes and dynamic_range among the client information | upstream_code | sls/protocol.py:337-356 |
| _to_numpy_meta decodes 24 and 32-bit frames as '<i4', 16-bit frames as '<i2' and 8-bit frames as '<i' | upstream_code | sls/protocol.py:305-313 |
| The timer wire value is an integer and acquisition time, frame period and delay after trigger are converted from seconds to nanoseconds on write and back to seconds on read | upstream_code | sls/protocol.py:500-512 |
| get_time_left converts acquisition time, frame period, delay after trigger, actual time and measurement time from nanoseconds to seconds | upstream_code | sls/protocol.py:488-497 |
| The client exposes exposure_time, nb_frames, nb_cycles, delay_after_trigger and frame_period as properties over the timer types | upstream_code | sls/client.py:288-333 |
| The detector threshold is held in eV | upstream_code | sls/shm.py:177-178 |
| The energy threshold client property reads and writes module -1 | upstream_code | sls/client.py:198-211 |
| The protocol comment says mod_nb -1 means ALL for the energy threshold | upstream_code | sls/protocol.py:474-476 |
| DetectorSettings names include STANDARD, FAST and HIGHGAIN; DetectorType names include MYTHEN | upstream_code | sls/protocol.py:139-163 |
| get_nb_modules queries the module count by dimension and get_module_serial_number queries a module's serial number through get_id | upstream_code | sls/client.py:159-171 |
| set_energy_threshold and the timer encoder pass the value into the request struct without checking a numeric range | upstream_code | sls/protocol.py:474-518 |

## Facts that are deliberately not used as limits

The task card lists the `MAX_*` constants in `sls/shm.py:20-28`. That module is a reader for the shared-memory
struct of `libSlsDetector.so`; the constants are capacities of its validation arrays (for example
`MAX_MODS = 24`), not limits of a Mythen II. They are therefore not driver limits. No line of the clone read for
this package states a valid energy threshold, exposure time, frame count, cycle count, frame period or delay range,
and the client functions encode whatever value they are given (`sls/protocol.py:474-518`). Those six writable parameters are
`Limit.operator_required`; without a site overlay every write is refused `MHS.SAFETY.LIMITS_UNSET`. The example
overlay in `site-limits.example.json` only illustrates the shape and is not a statement about any unit.

## Safety

The safe state is "acquisition stop requested with the native stop_acquisition command". `@estop stop` and the
safe-state action `x-cap.alba-synchrotron.stop_acquisition.v1` both call the upstream `Detector.stop_acquisition()`,
which sends STOP_ACQUISITION over the separate stop connection (`sls/client.py:383-385`,
`sls/protocol.py:720-722`). The e-stop does not wait for the running acquisition: the stop is a separate socket
command, and the acquiring generator stops itself on an unexpected exception before closing the control socket
(`sls/client.py:566-573`). The driver checks `self.cancelled()` between frames and reports a cancellation when the
runtime requested one. The stop command's reply is an acknowledgement (`request_reply` raises `SLSError` on a FAIL reply); the
driver reports the `run_status` read after it but does not claim an independently sensed quiescence, and no line of
the clone documents an independent hardware e-stop for the detector, so `estop_physical_ref` is not set. The device
is R1 (a detector: it senses, it does not move, dispense or emit).

The upstream sockets have no timeout (`sls/client.py:43-48`): a detector that accepts the connection but never
answers leaves the e-stop's native call waiting, and the runtime reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the
latch held after its e-stop budget. Because the package's e-stop calls `Detector.stop_acquisition()` directly, not
`Acquisition.stop()`, the acquisition's `_stopped` flag stays false: a FAIL frame result after the stop re-raises
`SLSError` (`sls/client.py:564-567`), which the driver reports as the cancellation the runtime requested.

## Thread safety of the upstream client

The upstream `Detector` keeps one `Connection` object per port, and every call connects and closes it
(`sls/client.py:94-115`, `:149-150`); two calls on the same port at once replace each other's socket. The runtime
serialises actions and writes under the driver lock, but reads do not take it. While `acquire` holds the control
connection open for its frames, the ten reads that use the control port (`detector_type`, `settings`, `nb_modules`,
`module_serial_number`, `energy_threshold`, `exposure_time`, `nb_frames`, `nb_cycles`, `frame_period`,
`delay_after_trigger`) return no value and are left out of the state rather than reconnect that socket; `run_status`
and `exposure_time_left` use the stop port and stay readable. A stop-port read that overlaps the e-stop (or the
upstream generator's own cleanup stop) can make the e-stop report its stop as not reached and retry; it cannot
report a stop that was not acknowledged. After the loop the driver closes the upstream generator at once, which runs
the upstream cleanup (`Acquisition.__exit__` stops an acquisition that ended with an exception).

## Mock path and fidelity

The upstream simulator (`sls/simulator.py`) is a gevent/scipy TCP server, not a local backend, and this package must
not import or run clone code. The gate therefore uses the package's in-memory analytic stand-in
`.fake:FakeDetector`, which mirrors the upstream `Detector` API. It is not a recording and it does not replay captured
traffic. The fake starts from placeholder values, shortens acquisition pacing to at most 5 ms per frame, and returns
a 16-element placeholder frame instead of a real one; those numbers are test data, not facts. A real frame holds
the `data_bytes` the detector reports (`sls/protocol.py:337-356`): 1280 counts per module (10 chips of 128 channels)
times the installed modules, for example 7680 for the 6 modules the drawing shows. The upstream decodes an 8-bit
frame with the 4-byte type `'<i'` (`sls/protocol.py:311-312`), so counts read at dynamic range 8 are not per-channel
values; the package does not set the dynamic range. The fake is thread-safe, which the upstream client is not (see
above). The `acquire` action returns only the last frame of a configured acquisition, not every frame.

Tags: detector, mythen, sls, photon-counting, tcp, acquisition
