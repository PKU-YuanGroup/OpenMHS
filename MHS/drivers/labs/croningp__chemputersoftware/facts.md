# Facts and tags for gh.croningp/chemputersoftware

Every fact cites its source at commit `0f249ce8f7c30e99bdf54f67cbd012d48e91dd3b`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The class controls an IKA RET Control Visc hotplate stirrer; the command implementation is based on the English manual version 20000004159, pages 31-34 | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:14-19 |
| temperature_pv reads IN_PV_1, temperature_sp reads IN_SP_1, and the temperature_sp setter writes OUT_SP_1 | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:81-83 |
| The temperature_sp setter targets sensor 1, the medium (external) temperature, and logs the set point in degC | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:162-179 |
| The executioner reads temperature_sp[0] and temperature_pv[0] as floats and logs both in degC | upstream_code | platform_server/tools/module_execution/stirrer_execution.py:73-84 |
| The executioner sets the hotplate temperature through temperature_sp and logs it in degC | upstream_code | platform_server/tools/module_execution/stirrer_execution.py:115-125 |
| stir_rate_pv reads IN_PV_4, stir_rate_sp reads IN_SP_4, and the stir_rate_sp setter writes OUT_SP_4 | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:78-80 |
| The stir rate setter converts the value with int() and logs it in RPM | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:140-146 |
| START_1/STOP_1 start/stop the heater and START_4/STOP_4 start/stop the stirrer | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:84-87 |
| start_heater sends START_TEMP, stop_heater sends STOP_TEMP, start_stirrer sends START_STIR, and stop_stirrer sends STOP_STIR | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:181-199 |
| get_ph sends GET_PH_PV | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:326-328 |
| GET_PH_PV is IN_PV_80 | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:102 |
| The valueanswer pattern captures a number and a status from a reply | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:71 |
| The serial line is configured for 9600 baud, 7 data bits, even parity and RTS/CTS | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:60-64 |
| get_weight sends GET_WEIGHT_PV; the comment says it only works with start weight and takes about 4 seconds, and no line states the unit of the value | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:330-333 |
| GET_WEIGHT_PV is IN_PV_90 | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:103 |
| set_watch_dog_temp, set_watch_dog_stir_rate and get_hot_plate_temp_current are stubs that return None | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:256-268 |
| get_viscosity_trend is a stub that returns None | upstream_code | platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:322-324 |

Limits: no line of the clone states a temperature range or a stir rate range. The two writable fields
(`temperature_setpoint`, `stir_rate_setpoint`) and the `cap.thermal.setpoint.v1` input `target_temperature` therefore
use `Limit.operator_required`: every call that sets them is refused `MHS.SAFETY.LIMITS_UNSET` until the operator's
`site-limits.json` supplies the range of the unit. `site-limits.example.json` shows the overlay grammar and is an
example for a bench, not a statement about any unit.

Not exposed: `set_watch_dog_temp`, `set_watch_dog_stir_rate`, `get_hot_plate_temp_current` and `get_viscosity_trend`
are stubs in the clone (`pass`), so they are not part of the contract. `get_weight` is also not exposed: the clone
names no unit for its value, and a number without a sourced unit would be an invented fact. The sensor-2 hot plate
temperature (`temperature_hot_plate_pv`/`temperature_hot_plate_sp`) is not exposed either: the clone names those
channels but states no unit for them, and the card's `get_hot_plate_temp_current` is one of the stubs above. The
weighing channel and the sensor-2 temperature channel are therefore NOT COVERED.

Safety: the e-stop `emergency_stop()` and the safe-state action `x-cap.croningp.stop_hotplate.v1` both send the two
native stop commands `STOP_1` (heater off) and `STOP_4` (stirrer off). No line of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware
driver. The set points are not changed by the stop.

Tags: hotplate, stirrer, temperature-control, serial
