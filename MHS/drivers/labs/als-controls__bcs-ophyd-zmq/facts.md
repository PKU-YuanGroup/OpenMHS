# Facts and tags for gh.als-controls/bcs-ophyd-zmq

Every fact cites the clone at commit `c745feb95f84a5b0cee2c4f1951babb6097055dd`. The driver's `facts` list is the
machine-readable form; the table below repeats it (regenerated from reference.json in the model review of
2026-11-05) and the prose gives the reasoning a reviewer needs.

## Selected device and shape

The package is a direct `Driver` over `bcsophyd.zmq.bcs_motor:BCSMotor` (`src/bcsophyd/zmq/bcs_motor.py:21`), one BCS
motor axis. The card asks for `OphydDriver`; that family is config-only and binds classic
`Component(EpicsSignal, ...)` declarations with `source_ref`, which this class does not have (its values come from a
ZeroMQ `GetMotorFull` request), so the package uses a direct driver with a `native.py` factory. `BCSSignal`,
`BCSDeviceManager` and `BCSAreaDetector` are separate entries in the same repository and are not bound here.

## Facts

| fact | source | ref |
|---|---|---|
| BCSMotor is an Ophyd Device and PositionerBase for one motor controlled through the BCS ZeroMQ server | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:18-21` |
| BCSMotor's constructor reads name, originalName, itemType, prefix, units, bridgeIP, bridgePort, timeout and settle_time from its keyword arguments and creates a BCSServer | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:33-58` |
| move() sets moveComplete=False and isMoving=True, sends zmq_move_motor([originalName], [new_position]) and starts a monitor thread | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:143-164` |
| monitor_motor_status polls update() every check_interval=0.1 s and declares the move finished when moveComplete is true; the computed distance to the target is logged but not used | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:175-215` |
| stop() sends zmq_stop_motor([originalName]) and sets isMoving=False; it does not set moveComplete | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:270-280` |
| read() calls zmq_get_motor_full_async(originalName), stores the first data element's 'Raw Motor Position' in _position and returns it as a value with a timestamp under the motor name | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:229-262` |
| The constructor creates self._lock to prevent concurrent access to the ZeroMQ server | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:64-65` |
| None of the ZeroMQ wrappers acquires self._lock | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:311-436` |
| update() calls zmq_get_motor_full(originalName) and reads data[0]['Motor State']['Move Complete'] and data[0]['Raw Motor Position']; it catches and logs every exception without re-raising | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:284-305` |
| zmq_move_motor runs asyncio.run(_zmq_move_motor_async(...)) in a new Thread, joins it and returns nothing; it checks no result | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:378-391` |
| _zmq_move_motor_async raises when the MoveMotor reply is unsuccessful or lists the motor as not found or timed out | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:393-409` |
| zmq_stop_motor runs asyncio.run(_zmq_stop_motor_async(...)) in a new Thread, joins it and returns nothing; it checks no result | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:412-426` |
| _zmq_stop_motor_async raises only when the StopMotor reply success is false; it does not check the timed_out or not_found lists | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:428-436` |
| zmq_get_motor_full raises RuntimeError when the worker thread produced no result, so a failed GetMotorFull is visible to the caller | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:344-368` |
| zmq_get_motor_full_async raises RuntimeError when the response success is false | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:330-338` |
| parse_get_motor_full raises ValueError when the reply success is false or the data field is empty | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:443-458` |
| move_motor sends the MoveMotor request and documents timed_out and not_found lists in the reply | upstream_code | `src/bcsophyd/zmq/bcs_server.py:909-926` |
| stop_motor sends the StopMotor request; its documentation says the stop command is immediately sent to the motor controller, and timed_out means the command queue is unavailable | upstream_code | `src/bcsophyd/zmq/bcs_server.py:1187-1202` |
| get_motor_full sends the GetMotorFull request and returns a data list of state dictionaries | upstream_code | `src/bcsophyd/zmq/bcs_server.py:620-635` |
| MotorStatus is a Flag enum of status bits (HOME=1 through MOVE_LT_THRESHOLD=131072); FORWARD_LIMIT, REVERSE_LIMIT and the RAW_*_LIMIT members are bit flags, not position bounds | upstream_code | `src/bcsophyd/zmq/bcs_server.py:28-46` |
| bcs_request sends the JSON request on self._zmq_socket and awaits the reply; the method sets no receive timeout | upstream_code | `src/bcsophyd/zmq/bcs_server.py:123-148` |
| connect() fetches the server public key, configures CURVE keys and connects the REQ socket to port+1 | upstream_code | `src/bcsophyd/zmq/bcs_server.py:90-121` |
| The device manager builds the selected motor class through Happi with device_class='bcsophyd.zmq.bcs_motor.BCSMotor' | upstream_code | `src/bcsophyd/zmq/bcs_device_manager.py:297-298` |
| The device manager takes the motor's unit from the BCS configuration's General Parameters -> Units and also records Forward SW Limit (Units) and Reverse SW Limit (Units) in the Happi item | upstream_code | `src/bcsophyd/zmq/bcs_device_manager.py:290-313` |
| The device manager reads the motor parameter Stop Decel (c/s^2) into a stop_decel field | upstream_code | `src/bcsophyd/zmq/bcs_device_manager.py:350` |
| BCSMotor's constructor reads no travel limit: its settings are name, originalName, itemType, prefix, units, bridgeIP, bridgePort, timeout and settle_time | upstream_code | `src/bcsophyd/zmq/bcs_motor.py:33-58` |
| check_server_connection calls sys.exit(1) when the BCS server check returns false | upstream_code | `src/bcsophyd/zmq/bcs_device_manager.py:137-153` |
| BCSAreaDetector's image is one of three hard-coded 3x3 patterns and acquire_frame puts that pattern into the Signal, so it is a test pattern device rather than a camera read | upstream_code | `src/bcsophyd/zmq/bcs_area_detector.py:29-55` |
| The README describes BCSAreaDetector as '2D detector support (under development)' | vendor_doc | `README.md:18` |
| LICENSE.md contains a clause under which a user who makes Enhancements available publicly or to Lawrence Berkeley National Laboratory without a separate written licence grants a non-exclusive, royalty-free perpetual licence to them | vendor_doc | `LICENSE.md:28-37` |
| pyproject.toml declares the licence as BSD-3-Clause | vendor_doc | `pyproject.toml:12` |

## Limits and units

The move input is `Limit.operator_required`: no line of the clone states a travel range, and the configured
unit/limits live in the deployment's BCS configuration. `site-limits.example.json` shows the overlay shape; the values
in it are examples, not device data. The `MotorStatus` limit names are status bits, not position bounds. MHS requires a
unit on a numeric input, so the move target declares `1`; it stands for the motor's configured unit, which the clone
does not state. The outputs declare no unit. The `units` read returns the string the deployment passed to the
factory.

The stop is the extension `x-cap.als-controls.bcs_stop.v1`, not `cap.motion.stop.v1`. The catalogue stop class carries
an optional `deceleration` in m/s2 (and its example is `{"deceleration": 2.0}`), but `BCSServer.stop_motor` sends only
a `StopMotor` command with motor names and `BCSMotor.stop()` passes only the motor name; there is no deceleration
parameter to honour. The BCS configuration has a `Stop Decel (c/s^2)` motor parameter; the clone does not say how the
server applies it. The extension has no input and reports `stopped` only after two consecutive fresh `Move Complete`
reports.

## Model review (2026-11-05)

The package is blocked. `StopMotor` is a documented upstream stop, and the stop action's fresh `Move Complete` check
keeps its receipts honest, but the stop cannot always be delivered: every request of one `BCSServer` shares a single
ZeroMQ REQ socket with no lock and no receive timeout, `BCSMotor._lock` is created and never taken, and
`zmq_stop_motor` swallows a refused send in its worker thread. The runtime cancels a running move before it calls the
e-stop; when that move is waiting for a `GetMotorFull` reply, the cancelled receive leaves the REQ socket waiting for
it, so the e-stop's StopMotor, the safe-state action's StopMotor and every later request are refused, StopMotor never
reaches the server and the motor finishes its commanded move (reproduced by `review/lists/r22-probe_bcs_req_race.py`
with a REQ-modelling server). The author's fake answered every request at once and could not show it. The `@estop`
now sends StopMotor and reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held, so the gate fails
G6.ESTOP_FAILED and G8 SAFE-028. A `MoveMotor` that the server refuses is swallowed the same way and the move still
ends completed with the motor where it was; the move description says so. Unblocking needs every request serialised
(or a separate connection for StopMotor) and bounded receives.

## Not covered

`BCSSignal` (analog inputs through `get_freerun`) and `BCSDeviceManager` (Happi discovery) are separate interfaces of
the repository and are not bound in this package. `BCSAreaDetector` returns hard-coded 3x3 test patterns, so it is not
a camera read.

## Licence

`LICENSE.md` is the Lawrence Berkeley National Laboratory form of the BSD licence: besides the three BSD conditions it
contains a grant of a licence to publicly released Enhancements (`LICENSE.md:28-37`), while `pyproject.toml:12` and
the card say BSD-3-Clause. The owner decides whether the card needs a publication review.

## Tags

`ophyd`, `zmq`, `bcs`, `labview`, `motor`, `motion`.
