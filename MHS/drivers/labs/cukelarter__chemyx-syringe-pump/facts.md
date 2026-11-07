# Facts, limits and tags for gh.cukelarter/chemyx-syringe-pump

The clone is a Python/MATLAB control tree for CHEMYX syringe pumps.  `python_dist/CHEMYX_python/core/connect.py` is the
`Connection` class the card names; the Python GUI and the example scripts use it as `from core import connect`
(`CHEMYX_python/CHEMYX_GUI.py:31`, `CHEMYX_python/singlestep.py:15`).  The clone contains no README beyond a
three-line description, no manual, no datasheet and no protocol specification, so every statement below cites a line
of the code or of the text instructions.

This package uses a direct `Driver` rather than the card's `SerialDriver`: the upstream is a Python object whose
methods assemble a command, append a carriage return and return a **list of reply lines** (`connect.py:97-143`), and
the only parameter report is the multi-line `view parameter` reply (`connect.py:268-271`).  A line-oriented
command/parse table cannot express that reply or keep a written value in the resource state, so the driver calls the
upstream methods and the fake implements the same public methods.  This is the "DEVIATION FROM THE CARD" recorded in
`RESULT.json`.

Every fact cites its source at commit `14011ba2aeb2fcedff7a9b1718e58dc9acefb97f`; the same facts are written into
`driver.py` (`facts = [...]`), and the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| Connection controls serial interfacing with CHEMYX syringe pumps | upstream_code | python_dist/CHEMYX_python/core/connect.py:47-49 |
| The constructor takes a port and a baudrate that MUST match the pump's System Settings | upstream_code | python_dist/CHEMYX_python/core/connect.py:51-57 |
| openConnection opens the serial line with timeout 0 and calls getPumpStatus | upstream_code | python_dist/CHEMYX_python/core/connect.py:72-85 |
| A command is written as text followed by a carriage return | upstream_code | python_dist/CHEMYX_python/core/connect.py:113 |
| The upstream waits 0.4 s after a command before it reads the reply | upstream_code | python_dist/CHEMYX_python/core/connect.py:115 |
| In multipump mode a set command is prefixed with the current pump number | upstream_code | python_dist/CHEMYX_python/core/connect.py:109-110 |
| start, stop, pause and restart are sent as those four words | upstream_code | python_dist/CHEMYX_python/core/connect.py:163-216 |
| setUnits maps mL/min, mL/hr, microlitre/min and microlitre/hr to 0, 1, 2 and 3 | upstream_code | python_dist/CHEMYX_python/core/connect.py:221-222 |
| setDiameter, setRate, setVolume, setDelay and setTime send 'set <name> <value>' | upstream_code | python_dist/CHEMYX_python/core/connect.py:226-259 |
| setRate, setVolume and setDelay join a list value with commas for a multi-step run | upstream_code | python_dist/CHEMYX_python/core/connect.py:232-252 |
| getParameterLimits, getParameters, getDisplacedVolume, getElapsedTime and getPumpStatus send the query words 'read limit parameter', 'view parameter', 'dispensed volume', 'elapsed time' and 'pump status' | upstream_code | python_dist/CHEMYX_python/core/connect.py:263-284 |
| The GUI parses the getParameters reply by the line indexes 1, 2, 6, 3 and 7 for units, diameter, volume, rate and delay and takes the last space-separated token as the value | upstream_code | python_dist/CHEMYX_python/CHEMYX_GUI.py:233-237 |
| The GUI treats a negative volume as withdraw | upstream_code | python_dist/CHEMYX_python/CHEMYX_GUI.py:243-244 |
| The GUI labels the syringe diameter in millimetres and the delay in seconds | upstream_code | python_dist/CHEMYX_python/CHEMYX_GUI.py:156-159 |
| The upstream instructions say the baud rate must match the value in the pump's System Settings | vendor_doc | documentation/instructions/python_instructions.md:21 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| units | one of mL/min, mL/hr, microlitre/min, microlitre/hr | allowed set | `units_dict` at `python_dist/CHEMYX_python/core/connect.py:221-222` |
| diameter | mm | operator_required | the clone states no diameter range; the operator supplies the envelope of the installed syringe |
| rate | 1 (the unit selected by units) | operator_required | the clone states no flow-rate range; the operator supplies the range of the installed syringe and tubing |
| volume | 1 (the unit selected by units) | operator_required | the clone states no volume range; the operator supplies the volume envelope |
| delay | s | operator_required | the clone states no delay range; the operator supplies the delay envelope |
| time | 1 | operator_required | the clone sends the value without a unit and states no range; the operator supplies the envelope |

The five numeric writes are `Limit.operator_required` because no line of the clone states a numeric range.  The GUI
validators (`CHEMYX_GUI.py:106-112`) only keep the diameter, rate and delay non-negative in the UI; a widget bottom
is not a device bound, so they are not copied into a Limit.  `site-limits.example.json` is an example operator
overlay, not a statement about any syringe: without it every write of diameter, rate, volume, delay or time is
refused `MHS.SAFETY.LIMITS_UNSET`.

The rate, volume and time values are sent verbatim after the command word and their physical unit depends on the
unit set written earlier; the driver therefore publishes them with the dimensionless UCUM unit `1` and says so in
the field descriptions.  The diameter is always millimetres (the GUI label at `CHEMYX_GUI.py:156`); the delay is
labelled seconds (`CHEMYX_GUI.py:159`).

The read-only `dispensed_volume` and `elapsed_time` fields take the last number of their reply
(`_last_number` mirrors the GUI's last-token read at `CHEMYX_GUI.py:237`); the clone does not state their unit, so
they also carry the unit `1`.

## Safety

* The e-stop and the safe-state action `x-cap.cukelarter.stop.v1` both call `stopPump`, which sends `stop `
  (`connect.py:171-191`).  The pump stays stopped until a start action.
* The clone text names no independent hardware emergency stop, interlock, door or watchdog, so
  `estop_physical_ref` is not set and the safe-state action is the R2 stop path required by SAFE-045.
* A pump that dispenses liquid is at least R2 (`MHS/spec/04-safety.md`), so the driver is R2 even though the card's
  `risk_floor` is R1.
* Hardware was never attached and the hardware backend was never opened.  The package is model-authored and
  unreviewed (`driver.lock.json` `reviewed_by` is null), so the hardware backend stays refused at R2 until a human
  signs the lock.

## Tags

syringe pump, pump, serial, infuse, withdraw, chemyx
