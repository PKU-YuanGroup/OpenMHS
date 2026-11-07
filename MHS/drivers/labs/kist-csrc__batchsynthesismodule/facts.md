# Facts and tags for gh.kist-csrc/batchsynthesismodule

Every fact cites the clone at commit `5d0e9bb2ae49758f478021be35d7e5f6c2deac8f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| IKARETControlVisc is the class for the IKA RET control-visc hotplate stirrer and implements the English manual's serial command set | upstream_code | Stirrer/IKA_RET_Control_Visc.py:3-19 |
| The serial line is opened at 9600 baud with seven data bits, even parity and RTS/CTS flow control | upstream_code | Stirrer/IKA_RET_Control_Visc.py:68-72 |
| The command set uses IN_PV_1/IN_SP_1/OUT_SP_1 and START_1/STOP_1 for sensor 1, IN_PV_4/IN_SP_4/OUT_SP_4 and START_4/STOP_4 for the stirrer, START_80/STOP_80 for the pH meter, START_90/STOP_90 for weighing and RESET for the reset | upstream_code | Stirrer/IKA_RET_Control_Visc.py:85-100 |
| temperature_pv and temperature_sp address sensor 1, the medium (external) temperature sensor; the setter logs the set point in degrees Celsius | upstream_code | Stirrer/IKA_RET_Control_Visc.py:159-187 |
| stir_rate_pv and stir_rate_sp address the stirrer rate; the setter logs RPM and converts the value to an integer | upstream_code | Stirrer/IKA_RET_Control_Visc.py:118-157 |
| temperature_hot_plate_pv and temperature_hot_plate_sp address sensor 2, the hot plate temperature | upstream_code | Stirrer/IKA_RET_Control_Visc.py:283-308 |
| temperature_heat_transfer_medium_sp reads IN_SP_7 | upstream_code | Stirrer/IKA_RET_Control_Visc.py:278-281 |
| get_ph reads IN_PV_80 and get_weight reads IN_PV_90; the weight needs the weighing function started and takes about four seconds to calibrate | upstream_code | Stirrer/IKA_RET_Control_Visc.py:334-341 |
| temperature_hot_plate_safety_sp reads the hot plate safety set point and has no setter | upstream_code | Stirrer/IKA_RET_Control_Visc.py:320-328 |
| controlTemperature documents the target temperature as room temperature to 340 Celsius | upstream_code | Stirrer/hotplate.py:45 |
| controlStirrer documents the target stir rate as 0 to 1700 rpm | upstream_code | Stirrer/hotplate.py:69 |
| controlStop stops the stirrer and then the heater | upstream_code | Stirrer/hotplate.py:90-102 |
| set_watch_dog_temp, set_watch_dog_stir_rate, get_hot_plate_temp_current and get_viscosity_trend are empty methods in the upstream class and are not exposed | upstream_code | Stirrer/IKA_RET_Control_Visc.py:264-276 |
| SerialDevice raises OSError on an operating system other than Windows | upstream_code | Stirrer/serial_labware/serial_labware.py:104-108 |
| The command decorator queues each call to a background thread and blocks the caller until the reply is queued | upstream_code | Stirrer/serial_labware/serial_labware.py:31-57 |

Limits:

- `medium_setpoint` has an upper bound of 340 Cel, from `Stirrer/hotplate.py:45` (`controlTemperature` documents
  the target temperature as `roomtemp~340 celcius`).
- `stir_rate_setpoint` is 0 to 1700 rpm, from `Stirrer/hotplate.py:69` (`controlStirrer` documents
  `Limitation : 0~1700 rpm`).
- `hot_plate_setpoint` is `Limit.operator_required`: no line of the clone states a range for sensor 2.
- the `cap.thermal.setpoint.v1` `target_temperature` is `Limit.operator_required`: the catalogue class caps it at
  300 Cel, below the 340 Cel the clone documents for `controlTemperature`, so the site supplies the range of its
  unit in `site-limits.json`. `site-limits.example.json` is an example, not a statement about any unit.

Safety: no line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set. The
`@estop` method sends STOP_1 and STOP_4, and the same two native commands are the safe-state action
`x-cap.kist-csrc.stop_heating_and_stirring.v1`, which satisfies SAFE-045 for this R2 hardware driver.

Platform: the upstream `SerialDevice` refuses to initialise on a non-Windows system
(`Stirrer/serial_labware/serial_labware.py:104-108`). The hardware factory therefore cannot open a port on the
card's linux platform; the package is checked on the fake backend only.

Tags: hotplate, stirrer, ika, serial, thermal
