# Facts and tags for gh.k-dense-ai/lab-instrument-mcps (JULABO circulator)

The upstream is a multi-package driver pack. This package selects one concrete device:
`labmcp_julabo.driver:JulaboCirculator` in
`servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:137`. The other servers
in the clone are not part of this driver. Every citation is at commit
`46545ea7eb818249a524c3340dc80657f448430f`; the same facts are in `driver.py`
(`facts = [...]`). The reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| bath_temperature_c reads in_pv_00, heating_power_pct reads in_pv_01, safety_sensor_temperature_c reads in_pv_03 and excess_temperature_protection_c reads in_pv_04 | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:227-245 |
| setpoint_c reads in_sp_00 and set_setpoint writes out_sp_00 with two decimals and reads it back | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:247-271 |
| is_running reads in_mode_05; start writes out_mode_05 1 and verifies is_running | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:254-281 |
| The upstream start_circulation tool reads the current set point and checks it against its operator safety limits before starting, because the set point may have been changed on the front panel | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/server.py:227-237 |
| stop writes out_mode_05 0, retries once and returns True only if in_mode_05 confirms the stop | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:283-296 |
| require_remote refuses settings when status has kind state and remote is False | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:215-223 |
| Status codes 0 to 3 are manual stop, manual start, remote stop and remote start | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:44-50 |
| parse_status classifies known command-error codes as command_error and other negative codes as alarm | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:122-134 |
| A set point outside the temperature limits set on the circulator is rejected with -13 | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:58 |
| RS-232 factory settings are 4800 baud, 7 data bits, even parity, 1 stop bit and RTS/CTS handshake | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:19-20 |
| CORIO CD has only in_pv_00/01/03/04, in_sp_00, in_mode_05, out_sp_00, out_mode_05, version and status; the external Pt100 sensor in_pv_02 needs MAGIO or DYNEO | upstream_code | servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:23-25 |
| The README describes stop_circulation as stopping temperature control and the pump, then confirming with in_mode_05 | vendor_doc | servers/chemistry/julabo-circulator/README.md:71 |
| The MCP server's set point safety limits default to 5 and 90 Cel and the README tells the operator to set them to the bath fluid's working range | vendor_doc | servers/chemistry/julabo-circulator/README.md:79-83 |

## Limits

The set point is the only numeric write. No text file of the clone states the working
temperature range of a circulator: the server's 5 and 90 Cel defaults are an
operator-configurable water-bath limit (the README tells the operator to change them),
not a device bound. The driver therefore declares
`Limit.operator_required(...)` on the `setpoint` field: every write is refused
`MHS.SAFETY.LIMITS_UNSET` until the site supplies the range of its installed unit and
bath fluid. `site-limits.example.json` is an example overlay, not a statement about
any unit. The circulator additionally enforces its own working range and warning
limits and rejects a value with command error `-13`.

## Safety

The device heats and cools a bath, so the risk is R2. The native stop writes
`out_mode_05 0` and returns True only if `in_mode_05` confirms the stop; both the
`@estop` method and the input-free `x-cap.k-dense-ai.stop_circulation.v1` safe-state
action call it and raise `DriverFailed` if the confirmation is missing. The safe
state is temperature control and the pump stopped. The bath and its fluid remain hot
or cold; the command is not a physical disconnection and the clone documents no
independent hardware e-stop, so `estop_physical_ref` is not set and the safe-state
action satisfies SAFE-045 for this R2 driver. Stopping is reversible with
`out_mode_05 1`, so the e-stop is not terminal.

The stop makes two attempts; each writes `out_mode_05 0`, waits the command delay
(0.25 s by default) and queries `in_mode_05` through a transport whose upstream server
sets a 3.0 s timeout (server.py:40). No `estop_latency_ms` is declared because the clone
states no latency bound for the stop. On a slow or silent link the runtime's default 1 s
e-stop budget can expire before the second query; the receipt is then failed with the
latch held and the safe state unachieved. That is the honest report, not a confirmed
stop, and the background retry keeps trying. The native stop is idempotent, so the
e-stop method and the safe-state action both reaching it is harmless.

## Coverage and omission notes

* Covered: bath temperature, heating/cooling power, safety-sensor temperature,
  excess-temperature protection setting, set point, running state, raw status line,
  firmware version, set point write, start and stop.
* External Pt100 temperature (`in_pv_02`) and warning limits (`in_sp_03`/`in_sp_04`)
  are omitted because CORIO CD does not have them and a single driver cannot report a
  required number that some supported models do not provide.
* The auxiliary `start_keepalive` background thread, the wait-for-temperature loop and
  the MCP server's tool layer are not re-exported; the driver exposes the underlying
  circulator control.
* The start action starts to the set point currently stored on the circulator. The
  runtime enforces the operator envelope on this driver's set point write, but the
  effective site overlay is not exposed to the driver, so the start action cannot
  repeat the upstream MCP server's check of a front-panel set point (server.py:227-237).
  A hardware deployment must set the target through this driver or verify that a
  front-panel set point is inside the operator envelope before starting.
* The fake is a fixed-state in-memory stand-in, not a recording and not the upstream
  simulator. It has no thermal model, so read values do not move and start/stop change
  only the running flag. Every fake number and canned reply is marked
  `# placeholder`; none is a fact or a limit. The fake also accepts
  `stop_confirmed=False` as a test option that models a circulator which never confirms
  `out_mode_05 0`; the package test uses it to show that the e-stop stays latched and
  the safe state is reported unachieved. That option is test data, not a device mode.

## Model review blocker

The start action currently bypasses the upstream server's check of a front-panel set point
(server.py:227-237). A regression in `test_driver.py` sets the fake's stored target to a placeholder
150 Cel and supplies the example 5..90 Cel overlay: start still completes and sets running to true.
The operator-required set-point write does not protect this input-free start. This package remains
blocked until start validates the actual target against the effective deployment envelope; operator
preflight is not endpoint enforcement. The stock gate assertion is retained, so G9 fails on this case.
The start/re-enable contract also needs to preserve SAFE-042: reset must release only the latch.

The native stop takes `self.t.lock` (driver.py:288-293), the same lock used by queries and writes
(driver.py:151-157, 181-192); it can wait behind an in-flight exchange. Its boolean confirmation is
real source behavior, but no hardware latency was measured. Other card entries are separate devices:
MTSICSBalance (balance), IKAStirrer (motor/heater), AlicatDevice (flow controller), and RigolScope
(oscilloscope); none is served by this JULABO package.
