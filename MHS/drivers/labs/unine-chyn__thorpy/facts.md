# Facts and tags for gh.unine-chyn/thorpy

Every fact cites its source at commit `e8f000bd8a5bcc5a11b52f59742024d929751827`, either `upstream_code` (a file
of the clone) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page. Nothing here was run on
hardware.

| fact | source | ref |
|---|---|---|
| The APT serial port opens at 115200 baud, 8 data bits, no parity, one stop bit and RTS/CTS flow control | upstream_code | thorpy/comm/port.py:20-24 |
| Port.create returns a SingleControllerPort unless the serial number starts with 70, 73 or 94, which selects the unimplemented CardSlotPort | upstream_code | thorpy/comm/port.py:181-193 |
| SingleControllerPort.get_stages accepts only channel 0x01 and returns a GenericStage for it | upstream_code | thorpy/comm/port.py:236-249 |
| A short APT frame is a little-endian 16-bit message id, two parameter bytes, a destination byte and a source byte | upstream_code | thorpy/message/_base.py:98-108 |
| The stage position is the encoder count divided by EncCnt | upstream_code | thorpy/stages/__init__.py:224-226 |
| The position setter multiplies the position by EncCnt and sends MGMSG_MOT_MOVE_ABSOLUTE_long | upstream_code | thorpy/stages/__init__.py:228-232 |
| The velocity conversion uses EncCnt and T, with T = 2048 / 6e6 | upstream_code | thorpy/stages/__init__.py:235-237 |
| A stage reports mm when its configured Units value is 1 and the degree sign when it is 2 | upstream_code | thorpy/stages/__init__.py:399-400 |
| status_homed is status bit 0x00000400 of the APT status word | upstream_code | thorpy/stages/__init__.py:275-277 |
| home_non_blocking sends MGMSG_MOT_MOVE_HOME and returns without waiting for the move to finish | upstream_code | thorpy/stages/__init__.py:455-461 |
| MGMSG_MOT_MOVE_ABSOLUTE_long is message 0x453 with a 16-bit channel and a signed 32-bit position | upstream_code | thorpy/message/motorcontrol.py:560-572 |
| MGMSG_MOT_MOVE_HOME is message 0x443 with a channel byte | upstream_code | thorpy/message/motorcontrol.py:625-635 |
| MGMSG_MOT_MOVE_STOP is message 0x465 with a channel byte and a stop mode (0x01 immediately, 0x02 controlled) | upstream_code | thorpy/message/motorcontrol.py:691-704 |
| MGMSG_MOT_SET_VELPARAMS is message 0x415 and carries min_velocity, acceleration and max_velocity | upstream_code | thorpy/message/motorcontrol.py:548-559 |

## Reads, writes and actions

The driver is a direct `Driver` over `thorpy.comm.port:Port`, not a `SerialDriver`: the APT protocol is a binary
frame built from a message id, a channel and a stop mode, and a text command table cannot express it.

| Role | Name | Unit | Binding | Source |
|---|---|---|---|---|
| read | position | mm | mhs.resource.read | the encoder count divided by EncCnt (stages/__init__.py:224-226) |
| read | max_velocity | mm/s | mhs.resource.read | velocity parameters (stages/__init__.py:313-317) |
| read | acceleration | mm/s2 | mhs.resource.read | velocity parameters (stages/__init__.py:318-320) |
| read | homed | boolean | mhs.resource.read | status bit 0x00000400 (stages/__init__.py:275-277) |
| write | position | mm | cap.device.configure.v1 | position setter starts MGMSG_MOT_MOVE_ABSOLUTE_long (stages/__init__.py:228-232) |
| write | max_velocity | mm/s | cap.device.configure.v1 | max_velocity setter sends the velocity parameters (stages/__init__.py:313-317) |
| write | acceleration | mm/s2 | cap.device.configure.v1 | acceleration setter sends the velocity parameters (stages/__init__.py:318-320) |
| action | home | none | x-cap.unine-chyn.stage_home.v1 | home_non_blocking sends MGMSG_MOT_MOVE_HOME (stages/__init__.py:455-461) |
| action | stop_motion | none | x-cap.unine-chyn.stage_stop.v1 (safe state) | MGMSG_MOT_MOVE_STOP, stop mode 0x01 immediately (motorcontrol.py:691-704) |

The driver serves linear translation stages only: it declares `mm` and the clone reports `mm` for a stage with
Units = 1, while a rotational stage reports degrees (`stages/__init__.py:399-400`). The `native` entry is the card's
entry symbol `thorpy.comm.port:Port`; `Port.create` produces the `SingleControllerPort` that implements `get_stages`
for channel 1 (`comm/port.py:181-193`, `236-249`).

## Limits

No line of the clone states a travel range, velocity range or acceleration range: those values belong to the
installed stage and its per-stage server configuration (the `.ini` file the clone reads in `GenericStage.__init__`),
not to the protocol. Every numeric write therefore uses `Limit.operator_required`, and the operator overlay
`site-limits.example.json` shows where the bench values go. Without an overlay every write is refused with
`MHS.SAFETY.LIMITS_UNSET`.

| parameter | limit | reason |
|---|---|---|
| position (mm) | operator_required | the travel range of the installed stage is per-stage configuration, not a protocol bound |
| max_velocity (mm/s) | operator_required | the usable velocity of the installed stage is not stated by the clone |
| acceleration (mm/s2) | operator_required | the usable acceleration of the installed stage is not stated by the clone |

The example overlay contains illustrative bench values only; an operator must replace them with the values of the
installed stage before a hardware use.

## Safety

The e-stop and the `x-cap.unine-chyn.stage_stop.v1` action send `MGMSG_MOT_MOVE_STOP` with stop mode 0x01
(immediately) on channel 1. The driver does not disable the channel, does not home as part of an e-stop and does
not reset the controller. The clone states no independent hardware e-stop, and none is needed at R1; the physical
e-stop of the bench stays authoritative. The home action polls only while it is not cancelled. This package is
model-authored and unreviewed; no hardware run was made.

## Honest limits of this package

- The fake is an in-memory stand-in for one channel, not a recording of an instrument. It does not reproduce the
  APT reader thread, the status-update stream or the timing of a real controller.
- The stop frame is the six bytes the upstream `MGMSG_MOT_MOVE_STOP` class serializes for channel 1 with the
  controller destination and host source the port uses; it was not sent to a controller here.
- Only channel 1 is served, matching `SingleControllerPort.get_stages` and its single-channel assertion
  (`comm/port.py:236-242`); `CardSlotPort` is unimplemented upstream (`comm/port.py:196-198`).
- The `cap.sensing.read.v1` id in the task card hints does not bind `motion.axis` (its resource kinds are sensor
  kinds). The catalogue motion classes declare a `speed_scale` (home) and a `deceleration` profile (stop) that the
  clone does not expose; this driver therefore serves the two operations it can honour as
  `x-cap.unine-chyn.stage_home.v1` and `x-cap.unine-chyn.stage_stop.v1`, and keeps the position, velocity and
  acceleration settings as `cap.device.configure.v1` writes.

Tags: thorlabs, apt, stage, motion, serial.
