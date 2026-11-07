# Facts and tags for gh.cetuspcr/cetus-pcr

Every fact cites its source at commit `bbed1fd40257f5ba51bf4d9c9bc5fa328f28d7cb`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ArduinoPCR is the host-side serial controller class of the Cetus PCR | upstream_code | functions.py:72 |
| The application constructs the controller with baudrate 9600 and timeout 1 | upstream_code | interface.py:872 |
| The Arduino firmware opens the serial port at 9600 baud | upstream_code | arduino/cetuspcr/cetuspcr.ino:4 |
| The firmware announces 'Cetus is ready.' after its setup | upstream_code | arduino/cetuspcr/serialtools.h:31 |
| The firmware frames a command between '<' and '>' and splits its arguments on spaces | upstream_code | arduino/cetuspcr/serialtools.h:13-15 |
| The command <peltier state pwm_signal> uses state 0 to heat and state 1 to cool | upstream_code | arduino/cetuspcr/serialtools.h:81-102 |
| A heating command writes the heat PWM, clears the cool PWM and prints tempSample and tempLid | upstream_code | arduino/cetuspcr/serialtools.h:84-94 |
| A cooling command writes the cool PWM and clears the heat PWM | upstream_code | arduino/cetuspcr/serialtools.h:96-101 |
| The firmware ends every processed command with the line nextpls | upstream_code | arduino/cetuspcr/serialtools.h:108 |
| The firmware handles only the peltier and printTemps commands; it has no temperature setpoint command | upstream_code | arduino/cetuspcr/serialtools.h:81-107 |
| The controller sends <peltier 0 N> for heating and <peltier 1 N> for cooling, with N the integer PID output or its absolute value | upstream_code | functions.py:149-153 |
| The PID output is limited to -255 to 255 | upstream_code | functions.py:86 |
| On cancellation the upstream loop writes <peltier 0 0> and returns | upstream_code | functions.py:137-144 |
| The experiment loop checks is_running only inside the is_waiting branch | upstream_code | functions.py:135-137 |
| serial_monitor sets is_waiting True when a nextpls line arrives | upstream_code | functions.py:211-212 |
| serial_monitor parses tempSample and tempLid lines into current_sample_temperature and current_lid_temperature | upstream_code | functions.py:200-206 |
| run_experiment repeats the experiment steps n_cycles times | upstream_code | functions.py:123-125 |
| initialize_connection scans the serial ports, opens the matching port and checks the startup line before starting serial_monitor | upstream_code | functions.py:234-262 |
| The upstream close path clears is_running, clears is_connected and closes the serial device | upstream_code | interface.py:324-327 |

Limits: every numeric input of the experiment action is `Limit.operator_required`, because no text file of the clone
states a safe temperature range, a maximum hold time or a maximum cycle count for the machine. The firmware has no
temperature setpoint command; the host PID chooses the PWM (arduino/cetuspcr/serialtools.h:81-107, functions.py:86).
Until the operator supplies the ranges in site-limits.json every call is refused with
`MHS.SAFETY.LIMITS_UNSET`.

| input | unit | limit | why |
|---|---|---|---|
| temperature | Cel | operator_required | no safe sample-block temperature range is stated by the clone; the report's PCR phase temperatures are protocol examples, not device bounds |
| duration_s | s | operator_required | the upstream loop runs until the duration the operator entered (functions.py:131-170); no maximum is stated |
| cycles | 1 | operator_required | `range(int(n_cycles))` has no bound in the clone (functions.py:123) |

Safety: the safe-state action and the e-stop clear `is_running`, set `is_waiting` so the upstream loop takes its
cancellation branch (functions.py:135-137, 211-212), and write `<peltier 0 0>` through the open serial device, the
upstream cancellation path (functions.py:137-144). The firmware's heating command also clears the cooling
PWM and its cooling command clears the heating PWM (serialtools.h:84-101), so the zero command sets both drives to
zero. There is no independent hardware e-stop in the clone, so the package declares no `estop_physical_ref`; the
`safe_state=True` action satisfies SAFE-045 for a model-written R2 package.

Mock path: the card's preferred transcript cannot represent the unsolicited multi-line serial replies or the
experiment loop, so `fake.py` is a small in-memory controller with the upstream public methods and a pyserial-like
`serial_device`. The start temperatures and constructor values in it are test data and are marked `# placeholder`.

Tags: thermocycler, pcr, peltier, serial, temperature, thermal block
