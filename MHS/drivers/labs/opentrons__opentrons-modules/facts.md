# Facts and tags for gh.opentrons/opentrons-modules

Every fact cites its source at commit `bb98120ac93ccff0ae9224f95309604dd8b7d0aa`: `upstream_code` (a code or
comment line of the clone) or `vendor_doc` (a text file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The host-side Tempdeck class opens the module over pyserial at 115200 baud | upstream_code | stm32-modules/tempdeck-gen3/scripts/test_utils.py:194-200 |
| get_temperatures sends M105.D and returns plate1, plate2 and the heatsink temperature | upstream_code | stm32-modules/tempdeck-gen3/scripts/test_utils.py:227-239 |
| M105.D replies with PT1, PT2, HST, PA1, PA2 and HSA values and OK | upstream_code | stm32-modules/include/tempdeck-gen3/tempdeck-gen3/gcodes.hpp:244-253 |
| deactivate sends M18 and expects the reply M18 OK | upstream_code | stm32-modules/tempdeck-gen3/scripts/test_utils.py:241-242 |
| M18 turns off the thermal system | upstream_code | stm32-modules/include/tempdeck-gen3/tempdeck-gen3/gcodes.hpp:206-215 |
| M18 clears the fan manual mode and sets fan power 0, then clears the peltier target and disables the peltier | upstream_code | stm32-modules/include/tempdeck-gen3/tempdeck-gen3/thermal_task.hpp:233-246 |
| set_temperature sends 'M104 S<temp>' and expects the reply M104 OK | upstream_code | stm32-modules/tempdeck-gen3/scripts/test_utils.py:244-246 |
| M104 sets a temperature target for the peltiers; its one parameter is the target temperature | upstream_code | stm32-modules/include/tempdeck-gen3/tempdeck-gen3/gcodes.hpp:310-320 |
| set_fan_power sends 'M106 S<power>' and expects the reply M106 OK | upstream_code | stm32-modules/tempdeck-gen3/scripts/test_utils.py:256-261 |
| M106 sets the fan PWM between 0 and 1; the parser refuses a value outside that range | upstream_code | stm32-modules/include/tempdeck-gen3/tempdeck-gen3/gcodes.hpp:401-418 |
| M103.D returns the peltier current in mA, the fan RPM, the peltier PWM and the fan PWM | upstream_code | stm32-modules/tempdeck-gen3/scripts/test_utils.py:307-324 |
| M103.D replies with I, R, P and F values and OK | upstream_code | stm32-modules/include/tempdeck-gen3/tempdeck-gen3/gcodes.hpp:270-300 |
| The thermistor conversion yields a temperature in Celsius | upstream_code | stm32-modules/tempdeck-gen3/firmware/README.md:11 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| fan_power (ratio 0 to 1) | M106 | 0 to 1 | stm32-modules/include/tempdeck-gen3/tempdeck-gen3/gcodes.hpp:417-418 (min_power 0.0 and max_power 1.0; line 451 refuses a value outside them) |
| target_temperature (Cel) | M104 | `Limit.operator_required` | no text file of the clone states the operating temperature range; the site supplies it in `site-limits.json` (`site-limits.example.json` shows the overlay) |

Safety: the e-stop and the safe-state action `x-cap.opentrons.deactivate.v1` both call the native
`deactivate()` (`M18`), which clears the peltier target, disables the peltier and sets fan power 0
(`thermal_task.hpp:233-246`). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: opentrons, temperature module, tempdeck, thermal, peltier, serial
