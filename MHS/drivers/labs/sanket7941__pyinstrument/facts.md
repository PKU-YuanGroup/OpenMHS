# Facts and tags for gh.sanket7941/pyinstrument

Every fact cites its source at commit `74278e53b075418f155d0567410e03a8503f347f`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PSupply stores the VISA resource it is constructed with as self.PS | upstream_code | pyinstrument/instrument.py:61-62 |
| PSupply.chk queries '*IDN?' on the resource | upstream_code | pyinstrument/instrument.py:64-65 |
| PSupply.on writes ':OUTPut:STATe 1' and PSupply.off writes ':OUTPut:STATe 0' | upstream_code | pyinstrument/instrument.py:73-79 |
| setVolt writes 'VOLT ' followed by the value | upstream_code | pyinstrument/instrument.py:81-82 |
| setCurr writes 'CURR ' followed by the value | upstream_code | pyinstrument/instrument.py:85-86 |
| measureVolt queries 'MEASure:VOLTage:DC?' and returns the resource's reply | upstream_code | pyinstrument/instrument.py:89-90 |
| measureCurr queries 'MEASure:CURRent:DC?' and returns the resource's reply | upstream_code | pyinstrument/instrument.py:92-93 |
| The upstream README lists a digital power supply among the instruments it controls over VISA | vendor_doc | README.md:2 |

Limits: the upstream code states no voltage or current range (it passes the caller's value straight into the
command, lines 82 and 86). Both setpoints are therefore `Limit.operator_required`; the operator supplies the bound
in `site-limits.json`, and `site-limits.example.json` shows the shape with example values. Until that overlay is
written, every setpoint write is refused `MHS.SAFETY.LIMITS_UNSET`. No bound is copied from a constructor default.

Safety: the native stop is `PSupply.off`, which writes `:OUTPut:STATe 0` (line 78); the `safe_state` sentence says
the output is disabled. The package is R1, so no independent hardware e-stop is cited. OpenMHS is not a safety
certification and not a safety-rated channel; the physical stop stays authoritative.

Tags: power supply, psu, scpi, visa, voltage, current.
