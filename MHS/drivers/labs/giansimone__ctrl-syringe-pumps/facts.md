# Facts and limits for gh.giansimone/ctrl-syringe-pumps

Every fact cites its source at commit `3b0d3154003498f65150d8f04905f3a27cdd9017`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| A command line is the address string, the command text and a carriage return | upstream_code | ctrl_syringe_pumps/control.py:33 |
| The pump address is written as a zero-padded two-digit number before the command | upstream_code | ctrl_syringe_pumps/interface.py:17 |
| The two default pump addresses are 0 and 1 | upstream_code | ctrl_syringe_pumps/interface.py:4-6 |
| DIAMETER_RANGE is [0.1, 50.0] | upstream_code | ctrl_syringe_pumps/interface.py:10 |
| The diameter unit is millimetres | upstream_code | ctrl_syringe_pumps/interface.py:43 |
| set_diameter sends 'DIA <value>' and accepts only 0.1 < value < 50.0, so the endpoints are rejected | upstream_code | ctrl_syringe_pumps/interface.py:39-43 |
| RATE_UNITS is ['UM', 'MM', 'UH', 'MH'] | upstream_code | ctrl_syringe_pumps/interface.py:8 |
| set_pumping_rate sends 'RAT <value> <rate_unit>' as one command | upstream_code | ctrl_syringe_pumps/interface.py:61-66 |
| The infuse direction is 'DIR INF', withdraw is 'DIR WDR' and reverse is 'DIR REV' | upstream_code | ctrl_syringe_pumps/interface.py:46-58 |
| The pump is started with 'RUN' and stopped with 'STP' | upstream_code | ctrl_syringe_pumps/interface.py:68-76 |
| The version/test command is 'VER' | upstream_code | ctrl_syringe_pumps/interface.py:31-34 |
| The serial defaults are 9600 baud and a 0.5 s timeout | upstream_code | ctrl_syringe_pumps/control.py:7-11 |
| The serial frame is eight data bits with no parity | upstream_code | ctrl_syringe_pumps/control.py:35-43 |

Limits:

| parameter | command | limit | source | ref |
|---|---|---|---|---|
| diameter (mm) | DIA | 0.1 to 50.0 | upstream_code | ctrl_syringe_pumps/interface.py:10 |
| direction | DIR | one of INF, WDR | upstream_code | ctrl_syringe_pumps/interface.py:46-58 |
| pumping_rate.value | RAT | operator_required: the clone states no numeric rate range | operator | site-limits.example.json |
| pumping_rate.rate_unit | RAT | one of UM, MM, UH, MH | upstream_code | ctrl_syringe_pumps/interface.py:8 |

The diameter bound is the constant `DIAMETER_RANGE = [0.1, 50.0]` (line 10).  The native method tests
`lower_val < val < upper_val` (line 40), so a real pump rejects exactly 0.1 and 50.0 even though the constant looks
inclusive; the driver declares the constant as its envelope, and the fake reproduces the native strict check.  This
is an upstream off-by-one, not a reason to widen the declared range.

The rate tokens are only strings in the clone; no line says whether UM is microlitres per minute or anything else.
The driver therefore passes the operator's number and token unchanged and declares no physical unit for the number.
The value is the only operator-required bound: the clone's `set_pumping_rate` accepts every number, and the runtime
refuses every rate write until the site supplies the range of its pump and tubing.

Safety: the native stop is `stop_pump` (`STP`, interface.py:73-76); it is the `@estop` method and, as the
`x-cap.giansimone.stop_pump.v1` action, the safe-state action required at R2.  The device can dispense fluid, so the
driver is R2 even though the task card's floor is R1.  No hardware e-stop is cited: the clone is software only and
does not describe one.  The package is model-authored and unreviewed; no hardware was attached.

Not covered: the clone has no query for the diameter, direction, pumping rate or run state, so the driver has no
`@read`; the runtime reports the values last written, and `VER` (the test action) is the only query the clone builds.
The two-pump network (`adr1`, `adr2`) is served as one device at the upstream's first address, `adr1` (0 by default).
