# Facts and tags for gh.benpruitt/tecancavro

Every fact cites its source at commit `5267fd2ed48b7e38d2261459cbf4a381e54c33c1`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package controls Tecan Cavro syringe pumps; XCaliburD covers the XCalibur with a distribution valve | vendor_doc | README.md:3 |
| A command frame is built as STX, address, sequence byte, command payload, ETX and an XOR checksum | upstream_code | tecancavro/tecanapi.py:87-91 |
| The standard-mode plunger travel is 0 to 3000 encoder steps and 0 to 24000 in microstep mode | upstream_code | tecancavro/models.py:465-466 |
| A volume in microliters becomes encoder steps as volume * (3000 / syringe_ul) in standard mode | upstream_code | tecancavro/models.py:866 |
| The valve has 9 ports and the syringe 1000 uL by default; both are constructor options | upstream_code | tecancavro/models.py:42 |
| dispense() selects the port and then moves the plunger by minus the volume in steps | upstream_code | tecancavro/models.py:415-417 |
| A negative relative plunger move dispenses and a positive one extracts | upstream_code | tecancavro/models.py:498-499 |
| The command buffer status is 0 when empty and 1 when non-empty | upstream_code | tecancavro/models.py:690 |
| The encoder count of the plunger axis is read with ?4 | upstream_code | tecancavro/models.py:667-673 |
| setSpeed takes an OEM speed code from 0 to 40 and SPEED_CODES maps a code to pulses per second | upstream_code | tecancavro/models.py:34-40 |
| setStartSpeed states 50 to 1000 pulses per second and setTopSpeed 5 to 6000 | upstream_code | tecancavro/models.py:530-541 |
| setCutoffSpeed states 50 to 2700 pulses per second | upstream_code | tecancavro/models.py:548-549 |
| setSlope accepts a slope code from 1 to 20 | upstream_code | tecancavro/models.py:560-561 |
| Chainable commands are queued in cmd_chain and sent only when executeChain() sends the chain | upstream_code | tecancavro/models.py:283-292 |
| terminateCmd() sends T as an executable command, which terminates the running command | upstream_code | tecancavro/models.py:713-717 |
| setMicrostep sends N0 or N1 immediately instead of queueing it | upstream_code | tecancavro/models.py:701-707 |

Limits (all `upstream_code`):

| field | bound | ref |
|---|---|---|
| start_speed (1/s) | 50 to 1000 | tecancavro/models.py:531 (the docstring states `[50-1000]`) |
| top_speed (1/s) | 5 to 6000 | tecancavro/models.py:540 (the docstring states `[5-6000]`) |
| cutoff_speed (1/s) | 50 to 2700 | tecancavro/models.py:549 (the docstring states `[50-2700]`) |
| speed_code (1) | 0 to 40 | tecancavro/models.py:521 (the setSpeed validation) |
| slope (1) | 1 to 20 | tecancavro/models.py:560 (the setSlope validation) |
| x-cap.benpruitt.move_plunger.v1 position (1) | 0 to 3000 | tecancavro/models.py:478 (standard mode; 0-24000 in microstep mode, line 473) |
| x-cap.benpruitt.dispense.v1 port (1) | operator required | 1 to num_ports (tecancavro/models.py:441); num_ports is a constructor option, 9 by default (line 80) |
| x-cap.benpruitt.dispense.v1 volume (uL) | operator required | volume * 3000 / syringe_ul steps (tecancavro/models.py:866); syringe_ul is a constructor option, 1000 uL by default (line 42) |

The port and the volume of a dispense depend on the valve and the syringe that are fitted, which the upstream takes as
constructor options; a default of the library is not a bound of the device, so both are `Limit.operator_required` and
a dispense is refused (`MHS.SAFETY.LIMITS_UNSET`) until the site states them (`site-limits.example.json`).

Safety: the e-stop and the safe-state action `x-cap.benpruitt.stop.v1` both call the native `terminateCmd()`
(`T`, tecancavro/models.py:713-717), and the safe-state action also clears the queued command chain with
`resetChain()`. No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set;
the safe-state action satisfies SAFE-045 for this R2 hardware driver. The clone's manual is a PDF
(`docs/Tecan_Cavro_XCALIBUR_Manual.pdf`) and is not cited: no page of it was read.

Tags: syringe pump, cavro, xcalibur, distribution valve, serial
