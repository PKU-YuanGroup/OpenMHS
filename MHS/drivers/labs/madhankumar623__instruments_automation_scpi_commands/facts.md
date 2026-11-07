# Facts and tags for gh.madhankumar623/instruments_automation_scpi_commands

Every fact cites its source in the upstream clone at commit
`2080effa969d0a911188f24e92f5d9551f1b22c9`. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a script of module-level functions: it opens three VISA resources and a Modbus client at import time, before any function is called | upstream_code | `PowerSupply_Automation.py:49-57` |
| DCsupply_1 is the VISA resource USB0::0x2A8D::0x1202::MY61005119::0::INSTR | upstream_code | `PowerSupply_Automation.py:11` |
| SUPPLY_CHANNEL_MAP maps S1 to powerSupply_1 channel 2 and S2 to powerSupply_1 channel 3 | upstream_code | `PowerSupply_Automation.py:60-66` |
| Set_Voltage selects the channel with INST:NSEL and writes VOLT | upstream_code | `PowerSupply_Automation.py:99-102` |
| Set_Current selects the channel with INST:NSEL and writes CURR | upstream_code | `PowerSupply_Automation.py:105-108` |
| Get_Voltage selects the channel with INST:NSEL and queries MEAS:VOLT? | upstream_code | `PowerSupply_Automation.py:111-114` |
| Get_Current selects the channel with INST:NSEL and queries MEAS:CURR? | upstream_code | `PowerSupply_Automation.py:117-120` |
| ON_OFF_Voltage selects the channel, accepts only ON or OFF and writes OUTP with that state | upstream_code | `PowerSupply_Automation.py:123-130` |
| DEFAULT_VOLTAGE = 13.6 V and DEFAULT_CURRENT_LIMIT = 0.1 A are the starting profile of initialize_supplies; the comment says they can be changed | upstream_code | `PowerSupply_Automation.py:26-28` |
| The README calls 13.6 V and 0.1 A default test parameters that can be changed before a new batch | vendor_doc | `README.md:39-48` |
| shutdown_supplies turns every mapped channel off through ON_OFF_Voltage | upstream_code | `PowerSupply_Automation.py:242-249` |
| The README maps five MCU samples S1-S5 onto three supplies | vendor_doc | `README.md:23-37` |
| The chamber temperature is read from a Modbus holding register, not from the supply | upstream_code | `PowerSupply_Automation.py:133-141` |
| The README says the temperature is a Modbus holding register value divided by 10.0 | vendor_doc | `README.md:125` |

## Limits

The clone states no output voltage or current range. `DEFAULT_VOLTAGE = 13.6` and `DEFAULT_CURRENT_LIMIT = 0.1` are
configuration macros of `initialize_supplies`, and the comment says they can be changed
(`PowerSupply_Automation.py:26-28`); they are not the installed unit's rating. Every numeric set point is therefore
`Limit.operator_required`, and the operator supplies the installed unit's range in `site-limits.json`:

| parameter | command | limit | source |
|---|---|---|---|
| `voltage_setpoint_ch2` (V) | `INST:NSEL 2;VOLT` | `Limit.operator_required`: the clone states no voltage range | `PowerSupply_Automation.py:26-28, 99-102` |
| `voltage_setpoint_ch3` (V) | `INST:NSEL 3;VOLT` | `Limit.operator_required`: the clone states no voltage range | `PowerSupply_Automation.py:26-28, 99-102` |
| `current_setpoint_ch2` (A) | `INST:NSEL 2;CURR` | `Limit.operator_required`: the clone states no current range | `PowerSupply_Automation.py:26-28, 105-108` |
| `current_setpoint_ch3` (A) | `INST:NSEL 3;CURR` | `Limit.operator_required`: the clone states no current range | `PowerSupply_Automation.py:26-28, 105-108` |

`site-limits.example.json` is an example operator overlay: it fills those four bounds with a deliberately narrow
bench example (0 to 5 V and 0 to 0.05 A) and is not a statement about any installed unit. Without an overlay every
one of those writes is refused `MHS.SAFETY.LIMITS_UNSET`.

## Safety

The supply can energize an external load, so the device is declared R2. The native stop is
`INST:NSEL 2;OUTP OFF;INST:NSEL 3;OUTP OFF`, which switches both controlled channels off; it is the same operation
the upstream `shutdown_supplies` loop performs for every mapped channel (`PowerSupply_Automation.py:242-249`). The
`x-cap.madhankumar623.output_off.v1` action carries `safe_state=True` and that command, so it is the independent
stop SAFE-045 requires. No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is
not set and no hardware stop is claimed. The software latch and the safe-state action are not a safety-rated
channel.

## Coverage and mock path

The package serves the first supply, `DCsupply_1` (`PowerSupply_Automation.py:11`), and the two channels the
upstream maps to it: channel 2 for S1 and channel 3 for S2 (`PowerSupply_Automation.py:60-66`). NOT COVERED: the
second and third supplies (`DCsupply_2`, `DCsupply_3`), the S3-S5 channels, and the Modbus Watlow F4 temperature
path (`PowerSupply_Automation.py:133-141`); one ScpiDriver transport opens one VISA resource and the temperature
controller is not SCPI. The upstream has no simulator or tests, so `fake.py` is an in-memory transport with the
`write/read/query/close` shape of the bridge, not a recording; every number in it is marked `# placeholder`. The
upstream module is never imported or run.

Tags: power-supply, dc-source, scpi, visa, mcu-monitoring
