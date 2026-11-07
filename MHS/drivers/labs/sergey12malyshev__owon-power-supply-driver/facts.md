# Facts and tags for gh.sergey12malyshev/owon-power-supply-driver

Every fact cites its source at commit `37ec9d93df28640d7522162922472cc531be7758` from the clone root as it is.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| The class opens a pyserial port with the port, baud rate and timeout given to `__init__` and keeps the port object in `serial_port` | upstream_code | owon_ps.py:18-24 |
| `send()` appends a newline to the command and reads one reply line | upstream_code | owon_ps.py:33-41 |
| `output_on()` and `output_off()` send `OUTPut ON` and `OUTPut OFF`, and `get_outputState()` sends `OUTPut?` | upstream_code | owon_ps.py:45-52 |
| `get_identity()` sends `*IDN?` and `reset_config()` sends `*RST` | upstream_code | owon_ps.py:54-59 |
| `set_voltage()` writes `VOLTage` with three decimals and `get_voltage()` reads `VOLTage?` | upstream_code | owon_ps.py:67-71 |
| `measure_voltage()` reads `MEASure:VOLTage?` | upstream_code | owon_ps.py:73-74 |
| `set_voltage_limit()` writes `VOLTage:LIMit` with three decimals and the code comments a 1 V minimum | upstream_code | owon_ps.py:76-77 |
| `get_voltage_limit()` reads `VOLTage:LIMit?` | upstream_code | owon_ps.py:79-80 |
| `set_current()` writes `CURRent` with three decimals and `get_current()` reads `CURRent?` | upstream_code | owon_ps.py:82-86 |
| `measure_current()` reads `MEASure:CURRent?` | upstream_code | owon_ps.py:88-89 |
| `set_current_limit()` writes `CURRent:LIMit` with three decimals and the code comments a 100 mA minimum | upstream_code | owon_ps.py:91-92 |
| `get_current_limit()` reads `CURRent:LIMit?` | upstream_code | owon_ps.py:94-95 |
| `get_power()` reads `MEAS:POW?` | upstream_code | owon_ps.py:97-98 |
| `get_all_parametrs()` sends `MEASure:ALL:INFO?` and returns the reply unparsed | upstream_code | owon_ps.py:100-101 |
| The upstream example names the tested model SPE3051 as a 30 V, 5 A, 150 W supply | upstream_code | example.py:3-5 |
| The README describes the package as a SCPI driver for the OWON power supply, tested on the SPA3051 model, connected as a virtual COM port | vendor_doc | README.md:3-5 |

Limits: the voltage and current set points and the voltage and current limit settings are all
`Limit.operator_required`. The clone states a 1 V minimum for the voltage limit (owon_ps.py:77) and a 100 mA
minimum for the current limit (owon_ps.py:92), but no upper bound for the generic class; example.py:4 names 30 V and
5 A only for the tested SPE3051. The site overlay supplies the complete range of the installed unit:
`site-limits.example.json` is an example for that model, not a statement about any unit, and a widening overlay is
refused by the endpoint. Until an overlay is supplied, every one of those writes is refused
`MHS.SAFETY.LIMITS_UNSET`.

The three PDF files under `_pdf/` were not cited: no page was read, so no page number is claimed. The facts above
come from the text files and from the code of the clone.

Safety: the output is the hazard this driver controls. `@estop(native="output_off")` sends `OUTPut OFF`, and the
declared safe state is the same native command; `x-cap.sergey12malyshev.output_off.v1` is the `safe_state=True`
action that SAFE-029 requires of a hardware device. The upstream class states no independent hardware e-stop, so the
package does not claim one. This package is model-authored and unreviewed; at R1 the loader does not refuse a
hardware backend, so a human review is required before hardware use.

Tags: power-supply, dc-source, scpi, serial
