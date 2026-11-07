# Facts and tags for gh.tiagocoutinho/vacuubrand

Every fact cites its source at commit `12b2e12aa43866ffa2ab986fc466c5548a7aba07`; the same facts are written into
`driver.py` (`facts = [...]`). The reference file is generated from the driver, not from this page. The only manual
is `docs/dcp_3000.pdf`, which is not cited here because no page of it was read.

| fact | source | ref |
|---|---|---|
| pressure() queries IN_PV_1 and returns the decoded pressure | upstream_code | vacuubrand/dcp3000/dcp3000.py:28-30 |
| decode_pressure converts a Torr reply to mbar and leaves an mbar or hPa reply numerically unchanged | upstream_code | vacuubrand/dcp3000/protocol.py:50-56 |
| transducer_pressure queries IN_PV_S<channel> and transducer_pressures queries IN_PV_X | upstream_code | vacuubrand/dcp3000/dcp3000.py:32-38 |
| decode_pressures returns its values in millibar | upstream_code | vacuubrand/dcp3000/protocol.py:59-66 |
| config() queries IN_CFG and decode_config returns the unit, the acoustic and connection flags and the transducer counts | upstream_code | vacuubrand/dcp3000/dcp3000.py:24-26 |
| decode_config maps the unit digit through a table of mbar, Torr and hPa | upstream_code | vacuubrand/dcp3000/protocol.py:11-11 |
| errors() queries IN_ERR and decode_errors returns the names of the error flags that are set | upstream_code | vacuubrand/dcp3000/dcp3000.py:66-68 |
| version() queries IN_VER and returns the reply text | upstream_code | vacuubrand/dcp3000/dcp3000.py:70-71 |
| event_time_interval writes OUT_SP_1 and reads IN_SP_1; recording_time_interval writes OUT_SP_2 and reads IN_SP_2 | upstream_code | vacuubrand/dcp3000/dcp3000.py:40-50 |
| decode_interval parses mm:ss and returns minutes*60+seconds | upstream_code | vacuubrand/dcp3000/protocol.py:77-80 |
| on_setpoint and off_setpoint accept a channel in 1 to 4, write OUT_SP_<on\|off><channel> with the value in mbar and read the matching IN_SP reply | upstream_code | vacuubrand/dcp3000/dcp3000.py:52-64 |
| switch_on writes REMOTE 1 and switch_off writes REMOTE - | upstream_code | vacuubrand/dcp3000/dcp3000.py:73-77 |
| close_venting_valve writes OUT_VENT 0, open_venting_value writes OUT_VENT 1 and vent writes OUT_VENT 2 | upstream_code | vacuubrand/dcp3000/dcp3000.py:79-87 |
| The protocol encodes every request as UTF-8 text plus a newline and strips the reply text | upstream_code | vacuubrand/dcp3000/protocol.py:83-88 |
| The protocol leaves 60 ms between commands, described as max 20 commands/s according to the documentation | upstream_code | vacuubrand/dcp3000/protocol.py:99-100 |
| An asyncio connection selects AIOProtocol, whose write_readline and write methods are coroutines | upstream_code | vacuubrand/dcp3000/protocol.py:113-143 |
| The Tango server opens the connection with connection_for_url, passes concurrency="async" and adds baudrate, bytesize and parity for serial schemes | upstream_code | vacuubrand/tango/server/dcp3000.py:41-55 |
| The Tango server device properties default to baudrate 9600, bytesize 8 and parity N | upstream_code | vacuubrand/tango/server/dcp3000.py:34-37 |
| The README connects through connection_for_url('serial:///dev/ttyS0') and wraps the connection in DCP3000 | vendor_doc | README.md:34-48 |
| The README documents a serial line baudrate of 19200 | vendor_doc | README.md:57-60 |

## Limits

- `event_time_interval` and the eight on/off set points are `Limit.operator_required`. No text file of the clone
  states a range: the upstream code only formats the interval as `mm:ss` (dcp3000.py:40-50) and writes the set point
  value in mbar (dcp3000.py:52-64). The only manual is `docs/dcp_3000.pdf`, and this package does not cite a page it
  did not read. The site supplies the ranges in `site-limits.example.json`; until then every write of those fields is
  refused `MHS.SAFETY.LIMITS_UNSET`.
- `recording_time_interval` is read-only. On an asyncio connection the upstream setter calls `self.write(...)`
  without awaiting the coroutine (dcp3000.py:46-50), so that write would never reach the device. The driver exposes
  only the read, which awaits the reply through `decode_interval`.

## Safety

- The e-stop sends `REMOTE -` and `OUT_VENT 0` (dcp3000.py:73-87). The two safe-state actions
  `x-cap.tiagocoutinho.switch_off.v1` and `x-cap.tiagocoutinho.close_venting_valve.v1` send the same two commands.
- The clone has no pump-state query, so the driver does not claim to observe or stop the pump itself; it only sends
  the controller's remote-release and venting-valve-close commands. The risk is R1 (a gauge/controller plus a venting
  valve), so no independent hardware e-stop is cited; the clone states none.
- This package is model-authored and unreviewed. The loader refuses the hardware backend of a model-written package
  only at R2 and R3; at R1 this package does not claim that protection.

Tags: vacuum, pressure, gauge, controller, setpoint, venting-valve, serial, asyncio
