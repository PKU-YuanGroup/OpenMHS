# Facts and tags for gh.openmhs-tutorial/thermostat

Synthetic tutorial: the references point into `vendor/` (the stand-in for an
upstream clone). Every fact is also written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver.

| fact | source | ref |
|---|---|---|
| The heater accepts setpoints from 5 to 80 Cel | vendor_doc | MANUAL.md:9 |
| emergency_off() cuts heater power and latches the controller | upstream_code | thermo/controller.py:39 |

Limits: setpoint 5..80 Cel (MANUAL.md:9), zone trim front -5..5 K and back -3..3 K
(thermo/controller.py:7), fan speed operator_required (no source states a range).

Tags: thermostat, tutorial
