# Facts and tags for gh.jasapp/rigol

Every fact cites its source at commit `602b8623f820f6b4db4d225b1d66f11b3bbb6d6a` from the clone root as it is.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.  The clone has no README, no docs directory and no text manual; every fact below comes from the
upstream code.

| fact | source | ref |
|---|---|---|
| The class is a control interface for the RIGOL DP832A power supply over USB TMC | upstream_code | rigol.py:1-4 |
| `DEFAULT_DEVICE` is `/dev/usbtmc2` | upstream_code | rigol.py:13 |
| `command()` opens the device file, writes the command plus a newline, waits 50 ms and closes the file | upstream_code | rigol.py:41-48 |
| `query()` writes the command plus a newline, waits 100 ms, reads up to 4096 bytes and strips the reply | upstream_code | rigol.py:50-59 |
| `output_on()` sends `:OUTP CH{channel},ON`, `output_off()` sends `:OUTP CH{channel},OFF`, and `get_output()` reads `:OUTP? CH{channel}` and compares the reply with `ON` | upstream_code | rigol.py:62-72 |
| `set_voltage()` writes `:SOUR{channel}:VOLT` and `get_voltage_setpoint()` reads `:SOUR{channel}:VOLT?`; `measure_voltage()` reads `:MEAS:VOLT? CH{channel}` | upstream_code | rigol.py:75-85 |
| `set_current()` writes `:SOUR{channel}:CURR` and `get_current_setpoint()` reads `:SOUR{channel}:CURR?`; `measure_current()` reads `:MEAS:CURR? CH{channel}` | upstream_code | rigol.py:88-98 |
| `measure_power()` reads `:MEAS:POWE? CH{channel}` | upstream_code | rigol.py:100-103 |
| `set_ovp()` writes `:OUTP:OVP:VAL CH{channel},{voltage}` and enables `:OUTP:OVP CH{channel},ON`; `set_ocp()` does the same with `:OUTP:OCP:VAL` and `:OUTP:OCP` | upstream_code | rigol.py:105-114 |
| `status()` returns one `ChannelStatus` with output, voltage_set, current_set, voltage, current and power | upstream_code | rigol.py:117-127 |
| `all_off()` turns the outputs of channels 1, 2 and 3 off | upstream_code | rigol.py:129-132 |
| `configure()` sets the voltage, then the current, then optionally turns the output on | upstream_code | rigol.py:134-140 |
| The REPL prints the status of channels 1, 2 and 3 | upstream_code | repl.py:26-28 |

Limits: the six numeric set-point writes (voltage and current of channels 1, 2 and 3) and the two protection
thresholds (OVP and OCP) are all `Limit.operator_required`.  The clone interpolates the caller's value into the
command (rigol.py:77, 90, 108, 113) and states no voltage, current or threshold range; there is no text manual to
cite.  The operator supplies the range of the installed unit in `site-limits.json`; `site-limits.example.json` is a
deliberately narrow example, not a statement about any unit.  Until an overlay is supplied, every one of those
writes and actions is refused `MHS.SAFETY.LIMITS_UNSET`.  The channel number of the two protection actions is
limited 1 to 3 by the upstream `all_off()` loop (rigol.py:131).

Safety: the output is the hazard this driver controls.  `@estop(native="all_off")` calls the upstream `all_off()`
(rigol.py:129-132), which turns channels 1, 2 and 3 off; the declared safe state is the same command sequence.  The
clone states no independent hardware e-stop and this package does not claim one.  The package is model-authored and
unreviewed, and at R1 the loader does not refuse its hardware backend, so a human review is required before hardware
use.

Tags: power-supply, dc-source, triple-channel, usb-tmc
