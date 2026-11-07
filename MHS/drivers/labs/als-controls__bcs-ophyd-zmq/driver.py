"""OpenMHS driver for gh.als-controls/bcs-ophyd-zmq: one BCS motor over the BCS ZeroMQ server.

DEVIATION FROM THE CARD: the card asks for the ``OphydDriver`` family (``family-config``).  The selected entry class
``bcsophyd.zmq.bcs_motor:BCSMotor`` is a custom Ophyd ``Device``/``PositionerBase`` whose transport is a ZeroMQ client
and whose values are not declared as classic ``Component(EpicsSignal, ...)`` members, so the config-only OphydDriver
grammar cannot express it.  This package is therefore a direct ``Driver`` over the upstream class with a ``native.py``
factory that opens the BCS connection.

The device is one BCS motor axis served by an ALS Beamline Control System (BCS) LabVIEW server:

* reads: the raw motor position (``Raw Motor Position`` of a fresh ``GetMotorFull``), whether the server reports
  ``Motor State -> Move Complete``, and the motor's configured unit string;
* one motion action, the extension ``x-cap.als-controls.bcs_move.v1``: send ``MoveMotor`` and poll fresh
  ``GetMotorFull`` state until ``Move Complete``; the target has no sourced travel bound, so it is
  ``Limit.operator_required`` and every move is refused until the operator supplies the range of this motor;
* an extension stop action ``x-cap.als-controls.bcs_stop.v1``: the native ``StopMotor`` command, marked
  ``safe_state=True``; it reports ``stopped`` only after a fresh ``GetMotorFull`` shows ``Move Complete`` on two
  consecutive polls.  The StopMotor acknowledgement alone is not treated as quiescence.  The catalogue
  ``cap.motion.stop.v1`` is not bound: its schema/example carries a deceleration in m/s2, and the BCS StopMotor
  endpoint takes only motor names (the BCS configuration has a ``Stop Decel (c/s^2)`` motor parameter,
  bcs_device_manager.py:350; the clone does not say how the server applies it); advertising a field the native call
  cannot honour would misstate the interface.
* ``@estop``: the same native ``StopMotor`` command, after which it reports ``MHS.SAFETY.SAFE_STATE_UNREACHED``
  (model review, below).

Model review (2026-11-05): the package is blocked.  ``StopMotor`` is a documented upstream stop, but every request of
one ``BCSServer`` shares a single ZeroMQ REQ socket with no lock and no receive timeout (bcs_server.py:105, 123-148;
``BCSMotor._lock`` is created at bcs_motor.py:65 and never taken), and ``zmq_stop_motor`` swallows a failed send in its
worker thread (bcs_motor.py:412-436).  An e-stop cancels the running move first; when that move is waiting for a
``GetMotorFull`` reply, the cancelled receive leaves the REQ socket waiting for it, so the e-stop's StopMotor, the
safe-state action's StopMotor and every later request are refused, StopMotor never reaches the server and the motor
finishes its commanded move (review/lists/r22-probe_bcs_req_race.py).  The receipts stay honest (the stop action
needs fresh Move Complete evidence), but the stop cannot be delivered in that case, and the fake (instant replies, no
REQ state) could not show it.  The @estop therefore sends StopMotor and then refuses to certify a safe state; an
unblocking design must serialise every request (or give StopMotor its own connection) and bound every receive.

What the clone does not provide, and this package therefore does not claim:

* No text file states a travel range or an engineering unit for a configured motor.  BCSDeviceManager reads the unit
  from the BCS configuration (``General Parameters -> Units``) and the range is an operator decision; both are outside
  the driver.
  The ``FORWARD_LIMIT``/``REVERSE_LIMIT`` names in ``bcs_server.py`` are ``MotorStatus`` bit flags, not travel limits.
* No hardware emergency stop or safety-rated channel is documented.  The BCS motor configuration has ``Use
  Interlock`` and ``Interlock DIO`` fields (bcs_device_manager.py:331-332) whose behaviour the clone does not describe.
  The upstream stop is a software ``StopMotor`` request to the LabVIEW server; the clone contains no physical stop
  reference.
* The upstream send wrappers run each request in a worker thread and do not re-raise an exception from it, so a
  rejected ``MoveMotor``/``StopMotor`` exchange is not returned to the caller.  The driver relies on the subsequent
  fresh ``GetMotorFull`` state and reports that limitation in ``facts.md`` and ``RESULT.json``.
* ``BCSAreaDetector`` in the same repository is a synthetic 3x3 test-pattern device ("2D detector support (under
  development)" in the README), not a camera transport, so it is not bound here.  ``BCSSignal`` (analog inputs) and
  ``BCSDeviceManager`` are separate devices/configuration helpers and are not this motor.

Every Fact cites a line of the clone at the pinned commit c745feb95f84a5b0cee2c4f1951babb6097055dd.  The package is
model-authored and unreviewed (``reviewed_by`` is null); it is checked on the fake backend only and has never
connected to a BCS server.
"""

import asyncio
import time

from mhs.driver import (Cancelled, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read)

#: The selected upstream module, relative to the clone root.
SOURCE = "src/bcsophyd/zmq/bcs_motor.py"
SERVER = "src/bcsophyd/zmq/bcs_server.py"
MANAGER = "src/bcsophyd/zmq/bcs_device_manager.py"
DETECTOR = "src/bcsophyd/zmq/bcs_area_detector.py"

#: The one motion action.  It has no catalogue class: cap.motion.joint_position.v1 is specified in rad and in a
#: joint order, while a BCS motor's unit and range come from the deployment's BCS configuration (see facts.md).
MOVE = "x-cap.als-controls.bcs_move.v1"
#: The stop action.  cap.motion.stop.v1 is not bound: its catalogue example/schema carries a deceleration in m/s2,
#: and the BCS StopMotor endpoint takes only motor names (no deceleration parameter).
STOP = "x-cap.als-controls.bcs_stop.v1"
#: Polling interval of the fresh-state loop; not a device property.
POLL_S = 0.1
#: How long the stop action waits for two consecutive fresh "Move Complete" reports before it fails the receipt.
STOP_CONFIRM_S = 0.5


class BcsMotor(Driver):
    device_id = "bcs-motor"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "bcsophyd.zmq.bcs_motor:BCSMotor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBcsMotor"}
    vendor = "ALS Controls (BCS)"
    model = "BCSMotor over the BCS ZeroMQ server"
    display_name = "BCS motor (bcsophyd.zmq.bcs_motor.BCSMotor)"
    tags = ["ophyd", "zmq", "bcs", "labview", "motor", "motion"]
    safe_state = ("No safe state is certified: the e-stop sends StopMotor and the stop action requires two fresh "
                  "Move Complete reports, but StopMotor shares one REQ socket with the reads and moves, so an e-stop "
                  "that cancels a move waiting for a GetMotorFull reply leaves the socket refusing every request: "
                  "StopMotor never arrives and the motor finishes its commanded move; the e-stop reports "
                  "SAFE_STATE_UNREACHED with the latch held")

    @read("position", description="Raw motor position from a fresh GetMotorFull, in the motor's configured unit "
                                  "(the BCS configuration's General Parameters -> Units; the driver does not convert)")
    async def position(self):
        data = await self._motor_data()
        return data["Raw Motor Position"]

    @read("moving", type="boolean",
          description="True unless the fresh GetMotorFull state reports Motor State -> Move Complete")
    async def moving(self):
        data = await self._motor_data()
        state = data.get("Motor State") if isinstance(data, dict) else None
        if not isinstance(state, dict) or "Move Complete" not in state:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "GetMotorFull returned no Motor State -> Move Complete field", native_code=None)
        return not bool(state["Move Complete"])

    @read("units", type="string",
          description="The unit string the deployment passed to the factory (BCSMotor keeps it as given); "
                      "BCSDeviceManager would take it from the BCS configuration's General Parameters -> Units")
    async def units(self):
        return self.native.units

    @action(name=MOVE, description="Move the motor to a target in its configured unit: send MoveMotor, then poll "
                                   "fresh GetMotorFull state until Move Complete. Completed means the server reported "
                                   "Move Complete, not that the target was reached: a MoveMotor the server refuses is "
                                   "swallowed upstream and also ends completed; compare position with the target",
            input={"target_position": Field("number", unit="1",
                                            description="Target in the motor's configured unit (the BCS "
                                                        "configuration's Units), which the clone does not state; "
                                                        "MHS requires a unit on a numeric input, and 1 stands for "
                                                        "that unknown configured unit",
                                            limit=Limit.operator_required(
                                                "the clone states no travel range for a configured motor: the BCS "
                                                "configuration supplies the unit, forward and reverse software "
                                                "limits, and they are not carried by BCSMotor; the site must "
                                                "supply this motor's range before any move"))},
            output={"target_position": Field("number",
                                             description="The target that was sent, in the configured unit"),
                    "position": Field("number",
                                      description="Fresh Raw Motor Position observed when the move completed"),
                    "move_complete": Field("boolean",
                                           description="The fresh Motor State -> Move Complete at the last poll")},
            cancellable=True, max_duration_ms=120000)
    async def move(self, target_position):
        """Send MoveMotor and poll fresh state; on cancellation send the native stop."""
        motor = self.native
        target = float(target_position)
        try:
            motor.zmq_move_motor([motor.originalName], [target])
            deadline = time.monotonic() + float(motor.timeout)
            data = None
            while True:
                self.check_cancelled()
                data = await self._motor_data()
                state = data.get("Motor State") if isinstance(data, dict) else None
                complete = bool(state.get("Move Complete")) if isinstance(state, dict) else False
                if complete:
                    break
                if time.monotonic() >= deadline:
                    motor.stop()
                    raise OutcomeUnknown(
                        "MoveMotor was sent but the server did not report Move Complete within the motor's "
                        "configured timeout; the stop command was sent and the final state is unknown")
                await asyncio.sleep(POLL_S)
            return {"target_position": target,
                    "position": data["Raw Motor Position"],
                    "move_complete": True}
        except (asyncio.CancelledError, Cancelled):
            motor.stop()
            raise

    @action(name=STOP, safe_state=True,
            description="Stop the motor: send the native StopMotor command, then require two consecutive fresh "
                        "GetMotorFull reports of Move Complete before reporting stopped",
            output={"stopped": Field("boolean",
                                     description="True only after two consecutive fresh Move Complete reports"),
                    "position": Field("number",
                                      description="Fresh Raw Motor Position observed when the stop was confirmed")})
    async def stop_motion(self):
        self.native.stop()
        stopped, position = await self._confirm_stopped()
        if not stopped:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the BCS server did not report Move Complete on two consecutive fresh GetMotorFull "
                               "polls after StopMotor; the stop is not confirmed")
        return {"stopped": True, "position": position}

    @estop(native="stop")
    async def emergency_stop(self):
        """Send StopMotor, then refuse to certify a safe state (model review, 2026-11-05).

        BCSMotor.stop() swallows a refused send in its worker thread, and the shared REQ socket refuses StopMotor
        while a cancelled GetMotorFull still waits for its reply, so a normal return proves nothing.
        """
        self.native.stop()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "StopMotor was handed to BCSMotor.stop(), which swallows a refused send; the BCS client shares one REQ "
            "socket without a lock or receive timeout, so the stop cannot be confirmed as delivered",
            native_code=None)

    async def _motor_data(self):
        """One fresh GetMotorFull data element; the upstream method raises on a failed or empty reply."""
        data = await self.native.zmq_get_motor_full_async(self.native.originalName)
        if not data or not isinstance(data[0], dict):
            raise DriverFailed("MHS.DEVICE.FAULTED", "GetMotorFull returned no motor data element",
                               native_code=None)
        return data[0]

    async def _confirm_stopped(self):
        """Two consecutive fresh GetMotorFull reports with Move Complete and the same position."""
        deadline = time.monotonic() + STOP_CONFIRM_S
        previous = None
        position = None
        while time.monotonic() < deadline:
            data = await self._motor_data()
            state = data.get("Motor State") if isinstance(data, dict) else None
            complete = bool(state.get("Move Complete")) if isinstance(state, dict) else False
            position = data.get("Raw Motor Position")
            current = (complete, position)
            if complete and current == previous:
                return True, position
            previous = current
            await asyncio.sleep(0.05)
        return False, position

    facts = [
        Fact("BCSMotor is an Ophyd Device and PositionerBase for one motor controlled through the BCS ZeroMQ "
             "server", source="upstream_code", ref=f"{SOURCE}:18-21"),
        Fact("BCSMotor's constructor reads name, originalName, itemType, prefix, units, bridgeIP, bridgePort, "
             "timeout and settle_time from its keyword arguments and creates a BCSServer",
             source="upstream_code", ref=f"{SOURCE}:33-58"),
        Fact("move() sets moveComplete=False and isMoving=True, sends zmq_move_motor([originalName], [new_position]) "
             "and starts a monitor thread", source="upstream_code", ref=f"{SOURCE}:143-164"),
        Fact("monitor_motor_status polls update() every check_interval=0.1 s and declares the move finished when "
             "moveComplete is true; the computed distance to the target is logged but not used",
             source="upstream_code", ref=f"{SOURCE}:175-215"),
        Fact("stop() sends zmq_stop_motor([originalName]) and sets isMoving=False; it does not set moveComplete",
             source="upstream_code", ref=f"{SOURCE}:270-280"),
        Fact("read() calls zmq_get_motor_full_async(originalName), stores the first data element's 'Raw Motor "
             "Position' in _position and returns it as a value with a timestamp under the motor name",
             source="upstream_code", ref=f"{SOURCE}:229-262"),
        Fact("The constructor creates self._lock to prevent concurrent access to the ZeroMQ server",
             source="upstream_code", ref=f"{SOURCE}:64-65"),
        Fact("None of the ZeroMQ wrappers acquires self._lock", source="upstream_code", ref=f"{SOURCE}:311-436"),
        Fact("update() calls zmq_get_motor_full(originalName) and reads data[0]['Motor State']['Move Complete'] and "
             "data[0]['Raw Motor Position']; it catches and logs every exception without re-raising",
             source="upstream_code", ref=f"{SOURCE}:284-305"),
        Fact("zmq_move_motor runs asyncio.run(_zmq_move_motor_async(...)) in a new Thread, joins it and returns "
             "nothing; it checks no result", source="upstream_code", ref=f"{SOURCE}:378-391"),
        Fact("_zmq_move_motor_async raises when the MoveMotor reply is unsuccessful or lists the motor as not found "
             "or timed out", source="upstream_code", ref=f"{SOURCE}:393-409"),
        Fact("zmq_stop_motor runs asyncio.run(_zmq_stop_motor_async(...)) in a new Thread, joins it and returns "
             "nothing; it checks no result", source="upstream_code", ref=f"{SOURCE}:412-426"),
        Fact("_zmq_stop_motor_async raises only when the StopMotor reply success is false; it does not check the "
             "timed_out or not_found lists", source="upstream_code", ref=f"{SOURCE}:428-436"),
        Fact("zmq_get_motor_full raises RuntimeError when the worker thread produced no result, so a failed "
             "GetMotorFull is visible to the caller", source="upstream_code", ref=f"{SOURCE}:344-368"),
        Fact("zmq_get_motor_full_async raises RuntimeError when the response success is false",
             source="upstream_code", ref=f"{SOURCE}:330-338"),
        Fact("parse_get_motor_full raises ValueError when the reply success is false or the data field is empty",
             source="upstream_code", ref=f"{SOURCE}:443-458"),
        Fact("move_motor sends the MoveMotor request and documents timed_out and not_found lists in the reply",
             source="upstream_code", ref=f"{SERVER}:909-926"),
        Fact("stop_motor sends the StopMotor request; its documentation says the stop command is immediately sent to "
             "the motor controller, and timed_out means the command queue is unavailable",
             source="upstream_code", ref=f"{SERVER}:1187-1202"),
        Fact("get_motor_full sends the GetMotorFull request and returns a data list of state dictionaries",
             source="upstream_code", ref=f"{SERVER}:620-635"),
        Fact("MotorStatus is a Flag enum of status bits (HOME=1 through MOVE_LT_THRESHOLD=131072); "
             "FORWARD_LIMIT, REVERSE_LIMIT and the RAW_*_LIMIT members are bit flags, not position bounds",
             source="upstream_code", ref=f"{SERVER}:28-46"),
        Fact("bcs_request sends the JSON request on self._zmq_socket and awaits the reply; the method sets no "
             "receive timeout", source="upstream_code", ref=f"{SERVER}:123-148"),
        Fact("connect() fetches the server public key, configures CURVE keys and connects the REQ socket to port+1",
             source="upstream_code", ref=f"{SERVER}:90-121"),
        Fact("The device manager builds the selected motor class through Happi with "
             "device_class='bcsophyd.zmq.bcs_motor.BCSMotor'",
             source="upstream_code", ref=f"{MANAGER}:297-298"),
        Fact("The device manager takes the motor's unit from the BCS configuration's General Parameters -> Units "
             "and also records Forward SW Limit (Units) and Reverse SW Limit (Units) in the Happi item",
             source="upstream_code", ref=f"{MANAGER}:290-313"),
        Fact("The device manager reads the motor parameter Stop Decel (c/s^2) into a stop_decel field",
             source="upstream_code", ref=f"{MANAGER}:350"),
        Fact("BCSMotor's constructor reads no travel limit: its settings are name, originalName, itemType, prefix, "
             "units, bridgeIP, bridgePort, timeout and settle_time", source="upstream_code",
             ref=f"{SOURCE}:33-58"),
        Fact("check_server_connection calls sys.exit(1) when the BCS server check returns false",
             source="upstream_code", ref=f"{MANAGER}:137-153"),
        Fact("BCSAreaDetector's image is one of three hard-coded 3x3 patterns and acquire_frame puts that pattern "
             "into the Signal, so it is a test pattern device rather than a camera read",
             source="upstream_code", ref=f"{DETECTOR}:29-55"),
        Fact("The README describes BCSAreaDetector as '2D detector support (under development)'",
             source="vendor_doc", ref="README.md:18"),
        Fact("LICENSE.md contains a clause under which a user who makes Enhancements available publicly or to "
             "Lawrence Berkeley National Laboratory without a separate written licence grants a non-exclusive, "
             "royalty-free perpetual licence to them", source="vendor_doc", ref="LICENSE.md:28-37"),
        Fact("pyproject.toml declares the licence as BSD-3-Clause", source="vendor_doc", ref="pyproject.toml:12"),
    ]
