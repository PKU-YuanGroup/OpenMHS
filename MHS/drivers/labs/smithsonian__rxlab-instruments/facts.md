# Facts and tags for gh.smithsonian/rxlab-instruments

Every fact cites its source at commit `2fbf8e6913e9eb2143088ed3a0b49d01a22fb93c`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| AgilentE8257D controls an E8257D PSG analog signal generator and is expected to work with the E8267D as well | upstream_code | labinstruments/agilent.py:49-53 |
| The repository lists the Agilent E8257D/67D PSG analog signal generator among the supported instruments | vendor_doc | README.md:37 |
| set_frequency writes ":FREQ <value><units>" | upstream_code | labinstruments/agilent.py:72 |
| get_frequency queries ":FREQ?" and divides the reply by the requested unit multiplier | upstream_code | labinstruments/agilent.py:86-87 |
| set_power writes ":POW <value><units>" | upstream_code | labinstruments/agilent.py:98 |
| get_power selects the unit with ":UNIT:POW <units>" and then queries ":POW?" | upstream_code | labinstruments/agilent.py:112-120 |
| power_on writes ":OUTP ON" and power_off writes ":OUTP OFF" | upstream_code | labinstruments/agilent.py:136-146 |
| get_output_state queries "OUTP:STAT?" and returns the reply as an integer | upstream_code | labinstruments/agilent.py:148-156 |
| get_id sends "*IDN?" and replaces commas with spaces | upstream_code | labinstruments/generic.py:59-63 |
| GenericInstrument.reset sends "*RST" and its docstring says "Reset instrument" | upstream_code | labinstruments/generic.py:65-68 |
| GenericInstrument opens the default port 5025 and reads the identity while connecting | upstream_code | labinstruments/generic.py:27-49 |
| The accepted frequency units are GHz, MHz, kHz and Hz | upstream_code | labinstruments/agilent.py:169-172 |
| The frequency setter defaults to GHz and the power setter to dBm | upstream_code | labinstruments/agilent.py:63-89 |
| The README example sets 15 GHz, -20 dBm and turns the RF output on | vendor_doc | README.md:63-66 |
| The two setters pass the caller's frequency and power into their commands without a range check | upstream_code | labinstruments/agilent.py:72-98 |

Limits: the upstream code states no frequency or power range. `set_frequency` and `set_power` format the caller's
value into their commands (agilent.py:72 and 98), and no text in the clone gives a bound. Both numeric setpoints are
therefore `Limit.operator_required`: the operator supplies the bound in `site-limits.json`, and
`site-limits.example.json` shows the shape with example values. Until that overlay is written, every setpoint write
is refused `MHS.SAFETY.LIMITS_UNSET`. No bound is copied from a constructor default.

Safety: the native stop is `power_off`, which writes `:OUTP OFF` (agilent.py:142-146); the `safe_state` sentence says
the RF output is off. The package is R1, so no independent hardware e-stop is cited. OpenMHS is not a safety
certification and not a safety-rated channel; the physical stop stays authoritative.

The safety reset sends nothing. `GenericInstrument.reset` writes `*RST` (labinstruments/generic.py:65-68). Its
docstring says "Reset instrument" and does not state the effect on the RF output, the frequency or the power, so
the call is not a reset step and not a declared re-enable (SAFE-042). It is the ordinary command
`x-cap.smithsonian.scpi_rst.v1`. The operator sends it explicitly and then confirms the instrument. The command is
not a safe-state action: an e-stop must not send `*RST`. A later read returns whatever the instrument replies;
this package does not state what `*RST` set.

Scope: this package binds the Agilent signal generator, one entry symbol of the family. The Keithley 2280 power
supply, the Rohde & Schwarz FSVA40 spectrum analyzer, the Hittite signal generator and the other classes of the clone
are not covered. The trace and array methods of the spectrum analyzer are therefore not covered either.

Tags: signal generator, rf, agilent, e8257d, e8267d, scpi.
