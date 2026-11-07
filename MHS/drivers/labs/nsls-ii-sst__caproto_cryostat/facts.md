# Facts and tags for gh.nsls-ii-sst/caproto_cryostat

Every fact cites the pinned clone at commit `bc89595479d634106426f698eef27a993a5cb99a`, file
`cryostat.py`. These are the same facts as `facts = [...]` in `driver.py`; the reference file is generated from
the driver, not from this page.

Tags: `cryostat`, `adr`, `epics`, `caproto`, `tag-bridge`, `temperature`.

## Facts

| fact | source | ref |
|---|---|---|
| ADR is documented as a class to read temperatures from NIST's adr_gui. | upstream_code | cryostat.py:17-20 |
| ADR declares TEMP as an ai pvproperty documented as 'temperature in k'. | upstream_code | cryostat.py:21 |
| ADR declares TEMP_SP as an ai pvproperty with the initial value 0.050, documented as 'temperature setpoint'. | upstream_code | cryostat.py:22 |
| The TEMP_SP putter sends the command set_temp_sp_k with the written value. | upstream_code | cryostat.py:65-67 |
| ADR declares TEMP_SP_RB as an ai pvproperty documented as 'temperature setpoint readback'. | upstream_code | cryostat.py:23 |
| The update hook writes TEMP_SP_RB from the controller message key temp_sp_rb. | upstream_code | cryostat.py:87-88 |
| ADR declares TEMP_RMS_UK as an ai pvproperty documented as 'temperature rms stability in uk'. | upstream_code | cryostat.py:24 |
| The update hook writes TEMP_RMS_UK from the controller message key stddev. | upstream_code | cryostat.py:82-83 |
| ADR declares ALT_TEMP as an ai pvproperty documented as '2nd channel temperature'. | upstream_code | cryostat.py:25 |
| The update hook writes ALT_TEMP from the controller message key alt_temp. | upstream_code | cryostat.py:75-76 |
| ADR declares HEATER_OUT as an ai pvproperty documented as 'heater'. | upstream_code | cryostat.py:26 |
| The update hook writes HEATER_OUT from the controller message key heater. | upstream_code | cryostat.py:80-81 |
| ADR declares STATE as a string pvproperty documented as 'ADR Mode'. | upstream_code | cryostat.py:27 |
| For the controller message key state, the update hook writes STATE only when the value differs from the current STATE value. | upstream_code | cryostat.py:77-79 |
| ADR declares CYCLE_UID as a string pvproperty documented as 'Cycle UID'. | upstream_code | cryostat.py:28 |
| For the controller message key uid, the update hook writes CYCLE_UID only when the value differs from the current CYCLE_UID value. | upstream_code | cryostat.py:84-86 |
| ADR declares PAUSE as a writable pvproperty documented as 'Pause PID Loop'. | upstream_code | cryostat.py:29 |
| The PAUSE putter sends pausePID when the written value is 1 and resumePID otherwise. | upstream_code | cryostat.py:53-58 |
| ADR declares START_CYCLE as a writable pvproperty documented as 'Start Cryo Cycle'. | upstream_code | cryostat.py:30 |
| The START_CYCLE putter sends start_mag_cycle when the written value is truthy. | upstream_code | cryostat.py:60-63 |
| The update hook is a 0.1 s scan that receives one JSON message from the ZeroMQ SUB socket and dispatches temperature, alt_temp, state, heater, stddev, uid and temp_sp_rb. | upstream_code | cryostat.py:69-88 |
| The ADR constructor connects a ZeroMQ SUB socket to the configured address and sub_port and subscribes to every message. | upstream_code | cryostat.py:33-40 |
| command serializes method, params and kwargs as JSON, sends it on a ZeroMQ REQ socket to the configured control_port, closes the socket and does not read a reply. | upstream_code | cryostat.py:43-51 |

## PV points (tag_config)

| point | PV suffix | codec | access | ref |
|---|---|---|---|---|
| temperature | TEMP | number | read | cryostat.py:21 |
| setpoint_readback | TEMP_SP_RB | number | read | cryostat.py:23 |
| temperature_rms | TEMP_RMS_UK | number | read | cryostat.py:24 |
| alternate_temperature | ALT_TEMP | number | read | cryostat.py:25 |
| heater_output | HEATER_OUT | number | read | cryostat.py:26 |
| state | STATE | string | read | cryostat.py:27 |
| cycle_uid | CYCLE_UID | string | read | cryostat.py:28 |

The same seven points are the output of the one observation capability, `x-cap.nsls-ii-sst.adr_readings.v1` (verb
`read`, no input). Units: `TEMP` is kelvin ('temperature in k') and `TEMP_RMS_UK` microkelvin ('in uk'); the clone
states no unit for `TEMP_SP_RB`, `ALT_TEMP` or `HEATER_OUT`, so they carry none. A string PV longer than 40 bytes
cannot be read through the `epics-ca` string codec; the clone does not show the length of the controller's cycle id.

The deployment PV prefix is not a fact: the upstream module's argument parser default can be overridden, and
`native.py` requires the operator to supply the installed prefix. The address and ports of the ZeroMQ sockets are
also deployment data and are not declared here.

## Scope and what is not covered

Model review (2026-11-05): the package is an R0 observer, the scope the tag-bridge preflight gives this card. The
author's version served `TEMP_SP` as a write, `PAUSE` and `START_CYCLE` as R2 commands, and bound `PAUSE=1`
confirmed by reading `PAUSE` back as the e-stop and safe-state action. That is not a stop: each putter only forwards
a JSON command on a ZeroMQ REQ socket that `command` closes without reading a reply (`cryostat.py:43-67`), and a
caproto pvproperty keeps the value its putter accepted, so the read-back proves only that the IOC stored the put,
not that the controller paused its PID loop; the clone has no heater-off command and nothing stops a started magnet
cycle. Without a source-backed stop the writes stay out:

- NOT COVERED `TEMP_SP` (`set_temp_sp_k`, `cryostat.py:65-67`), `PAUSE` (`pausePID`/`resumePID`, `:53-58`) and
  `START_CYCLE` (`start_mag_cycle`, `:60-63`): fire-and-forget commands to the external ADR controller with no
  acknowledgement and no stop route. `TEMP_SP` is not read either: it holds the last value put to the IOC (initially
  0.050, `:22`), not the controller's setpoint, which `TEMP_SP_RB` carries.
- Values arrive from the controller's ZeroMQ stream through a 0.1 s scan (`cryostat.py:69-88`); a read returns the
  IOC's last value, not a fresh sample, and a silent controller leaves the last values in place.
- The fake is a point store of the seven read PVs. It models no PID loop, heater, magnet cycle, ZeroMQ traffic,
  EPICS server error or network delay. All fake numbers are placeholders.
- Licence: the card records `NOASSERTION`; the clone has no licence file or package metadata to establish a licence.
  Publication waits for the owner's decision.
