# Facts and tags for gh.tiagocoutinho/gepace

Every fact cites its source at commit `4caa5f8c404277281033bc7f10b280d42941dfeb`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The library controls basic features of a GE Pressure Automated Calibration Equipment (Pace) controller of models 1000, 5000 and 6000 | vendor_doc | README.md:5-6 |
| The core of the library is the Pace object, created with a connection object that provides write_readline and write, in a sync or async version | vendor_doc | README.md:22-34 |
| Module.pressure reads SENS<module>:PRES as a float | upstream_code | gepace/pace.py:224 |
| The tango server maps pace[1].pressure() to its Pressure attribute with unit bar | upstream_code | gepace/tango/server/pace.py:118-120 |
| Module.barometric_pressure reads SENS<module>:PRES:BAR as a float | upstream_code | gepace/pace.py:227 |
| Module.pressure_control reads and writes OUTP<module>:STAT as a bool | upstream_code | gepace/pace.py:240 |
| Module.start() sets the pressure control output of the module True and Module.stop() sets it False | upstream_code | gepace/pace.py:258-262 |
| A member read appends '?' to the command; a member write sends '<CMD> <value>;<CMD>?' so the setter is confirmed by a read-back | upstream_code | gepace/pace.py:144-161 |
| Pace.__call__(request) sends one request through Pace._query | upstream_code | gepace/pace.py:376-377 |
| idn, hw_test, mac, task, error, version, world_area and startup_mode query *IDN, *TST, INST:MAC, INST:TASK, SYST:ERR, SYST:VERS, SYST:AREA and SYST:SET | upstream_code | gepace/pace.py:401-408 |
| startup_mode returns a Mode and a float setpoint; Mode.Control is CONT and Mode.Measurement is MEAS | upstream_code | gepace/pace.py:207-219 |
| serial_numbers queries :INST:SN1 through :INST:SN7 in one request | upstream_code | gepace/pace.py:411-415 |
| The serial number reply maps to ui, ctrl1, ctrl2, ao1, ao2, vfc1 and vfc2 as integers | upstream_code | gepace/pace.py:60-63 |
| Module.unit reads and writes UNIT<module>:PRES as a string | upstream_code | gepace/pace.py:245 |
| Module.pressure_range reads SENS<module>:PRES:RANG through to_name, which strips the quotes | upstream_code | gepace/pace.py:225 |
| Module.pressure_in_limits reads SENS<module>:PRES:INL | upstream_code | gepace/pace.py:226 |
| The in-limits reply is parsed as a pressure and a boolean | upstream_code | gepace/pace.py:55-57 |
| The tango server reads module 1 for its pressure, source pressure, setpoint, rate, rate mode, control and unit attributes | upstream_code | gepace/tango/server/pace.py:29-36 |
| The tango server publishes pressure control as a bool attribute and writes it with pace[1].pressure_control(value) | upstream_code | gepace/tango/server/pace.py:168-175 |
| The tango server creates the device with connection_for_url(url, concurrency='async') and passes that connection to Pace | upstream_code | gepace/tango/server/pace.py:54-68 |
| Pace._ask appends one newline to the request bytes and uses write_readline for a request that contains '?' | upstream_code | gepace/pace.py:382-386 |

## Limits

None. The card lists no writes, and this package binds none: the exposed pressure, barometric pressure,
unit, range, in-limits flag and control state are reads, and the three extension actions take only the
boolean `enabled` input (or no input) and act on the pressure control output. The pressure setpoint, rate,
rate mode, overshoot, relays and the source pressure are not bound. No text file of the clone states a
pressure setpoint range (the manuals under `docs/` are PDFs), so a pressure setpoint write would need
`Limit.operator_required`; it is left out of the interface instead of being given an invented bound.
`site-limits.example.json` is not copied because there is no operator-required bound and no numeric input
to narrow.

## Safety

Risk R2: enabling the pressure control output can pressurize an external system, which is a high-energy
action that can be destructive if wrong (`MHS/spec/04-safety.md` R2). The `@estop` method sends
`OUTP1:STAT 0` through the upstream `Pace.__call__`, and the safe-state action
`x-cap.tiagocoutinho.stop_pressure_control.v1` sends the same request; together they satisfy SAFE-045.
No text file of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set.
This is a software stop, not a safety-rated channel; OpenMHS is not a safety certification.

## Control path

The pressure control output is module 1's `OUTP1:STAT` (`gepace/pace.py:240`). The request is the exact
setter+readback built by the upstream member: `:OUTP1:STAT <0|1>;:OUTP1:STAT?`
(`gepace/pace.py:144-161`). The driver sends it through `Pace.__call__` (`gepace/pace.py:376-377`), which
forwards it to `Pace._query` and the connection. `Module.start()` and `Module.stop()` build the same
request with `pressure_control(True/False)` (`gepace/pace.py:258-262`). The driver serves module 1, the
module the upstream tango server reads (`gepace/tango/server/pace.py:29-35`); module 2 and the source
pressure, setpoint, rate and relay members are not exposed.

## Tags

pressure, pressure-controller, calibration, gepace, pace, scpi, asyncio

## Not covered

The hardware backend (`native.py`) was never imported or run and no hardware was attached. The fake is a
deterministic in-memory stand-in, not a recording of a device; every literal in it is placeholder test
data. The pressure setpoint, source pressure, rate, rate mode, overshoot, relays, module 2, the serial
and tango clients and the upstream sinstruments simulator are not covered. The simulated unit and range
strings are placeholders, not the unit or range of any unit.

The `pressure` read declares `bar` because the upstream tango server publishes the same module value in
bar (`gepace/tango/server/pace.py:118-120`). The module's configured unit is readable as `pressure_unit`
and the driver does not convert the raw value; if a unit is configured other than bar, the runtime's
`bar` label follows the upstream convention and `pressure_unit` shows the discrepancy.
