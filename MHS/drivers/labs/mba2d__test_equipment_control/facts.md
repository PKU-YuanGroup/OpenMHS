# Facts and tags for gh.mba2d/test_equipment_control

This card is a driver pack: the repository is a library of several lab instruments. One package covers one device
class, so this package covers the first entry symbol of the card,
`lab_equipment.Eload_A2D_Eload:A2D_Eload` (lab_equipment/Eload_A2D_Eload.py:8), the A2D electronic load on the RS485
bus.

Every fact cites its source at commit `34bb54c13c766fdfe7e6260872a03e8dfefd3ad2`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| A2D_Eload is the class that controls the A2D electronic load with pyvisa commands over the RS485 bus | upstream_code | lab_equipment/Eload_A2D_Eload.py:1-8 |
| The class declares max_channels = 32: at most 32 eloads are connected on the RS485 bus | upstream_code | lab_equipment/Eload_A2D_Eload.py:9 |
| initialize() splits the *IDN? reply into manufacturer, model number, serial number and firmware version | upstream_code | lab_equipment/Eload_A2D_Eload.py:25-29 |
| A model number containing 'Eload' sets max_current to 10.0 A | upstream_code | lab_equipment/Eload_A2D_Eload.py:31-32 |
| set_current writes 'CURR {channel},{current_setpoint_A}' and takes the absolute value of a negative setpoint | upstream_code | lab_equipment/Eload_A2D_Eload.py:49-52 |
| toggle_output writes 'INSTR:RELAY {channel},1' or 'INSTR:RELAY {channel},0'; closing the relay also sets the current to 0 first and writes the stored setpoint again | upstream_code | lab_equipment/Eload_A2D_Eload.py:55-62 |
| get_output queries 'INSTR:RELAY {channel}?' and converts the reply to bool | upstream_code | lab_equipment/Eload_A2D_Eload.py:65-66 |
| measure_voltage_supply queries 'MEAS:VOLT {channel}?' | upstream_code | lab_equipment/Eload_A2D_Eload.py:68-69 |
| measure_voltage_adc_supply queries 'MEAS:VOLT:ADC {channel}?' | upstream_code | lab_equipment/Eload_A2D_Eload.py:71-72 |
| measure_current returns the target current from 'CURR {channel}?' multiplied by -1 | upstream_code | lab_equipment/Eload_A2D_Eload.py:74-75 |
| measure_temperature queries 'MEAS:TEMP {channel}?' | upstream_code | lab_equipment/Eload_A2D_Eload.py:80-81 |
| set_led and set_fan write 'INSTR:LED {channel},1/0' and 'INSTR:FAN {channel},1/0'; get_led and get_fan query 'INSTR:LED {channel}?' and 'INSTR:FAN {channel}?' | upstream_code | lab_equipment/Eload_A2D_Eload.py:83-99 |
| reset writes '*RST' | upstream_code | lab_equipment/Eload_A2D_Eload.py:40-41 |
| get_rs485_addr and set_rs485_addr read and write 'INSTR:RS485' | upstream_code | lab_equipment/Eload_A2D_Eload.py:125-129 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| current (A) | CURR | at most 10.0 | lab_equipment/Eload_A2D_Eload.py:31-32 (`max_current = 10.0` for a model number containing 'Eload') |

The clone states no lower bound for the current: `set_current` takes the absolute value of a negative setpoint
(Eload_A2D_Eload.py:49-52), so the limit is a maximum only. No text file of the clone states a voltage range for the
load, so no voltage is written (the voltage is measured only).

Safety: the e-stop writes `INSTR:RELAY 1,0`, which opens the output relay (Eload_A2D_Eload.py:62) and leaves the load
sinking no current; the current setpoint is not changed. The clone states no independent hardware e-stop and none is
needed at R1.

Mock path: the card's `mock_strategy.preferred` is `upstream-sim` and it names `lab_equipment/Eload_Fake.py:4
Fake_Eload`. That class is a Python stand-in for the load's own high-level methods (it is used by the repository's GUI),
not a transport that answers SCPI lines, and a ScpiDriver needs a `write`/`read`/`query` transport. The mock path is
therefore a recording fake of the wire protocol (`fake.py`), which answers the queries of the clone and applies its
writes.

Not covered by this package (driver pack, one class per package):

- `lab_equipment.A2D_DAQ_control:A2D_DAQ` (lab_equipment/A2D_DAQ_control.py:10), the 64-channel DAQ board;
- `lab_equipment.PSU_SPD1000:SPD1000` (lab_equipment/PSU_SPD1000.py:13), the Siglent SPD1000 power supply;
- `lab_equipment.OTHER_Arduino_IO_Module:Arduino_IO` (lab_equipment/OTHER_Arduino_IO_Module.py:10), the Arduino I/O
  module;
- `lab_equipment.SMU_A2D_POWER_BOARD:A2D_POWER_BOARD` (lab_equipment/SMU_A2D_POWER_BOARD.py:7), the A2D power board.
- Inside the electronic load this package uses channel 1 of the RS485 bus only: it neither selects another channel nor
  reads or writes the RS485 address, and the calibration commands (CAL:V, CAL:I), the calibration reads and the
  INSTR:KICK command are not covered. The target current that the load reports with `CURR?` is exposed as the
  read-only field `current_reported`, with the load's own sign: the clone multiplies the reply by -1 to obtain the
  positive setpoint (Eload_A2D_Eload.py:74-75), and the SCPI bridge has no per-field sign conversion on a read, so
  the driver reports the reply as it comes. The write `current` takes the positive magnitude and sends `CURR 1,<value>`
  as the clone does (Eload_A2D_Eload.py:49-52), so a write of 2 A moves `current_reported` to -2 A.

Tags: electronic load, battery test, rs485, scpi, pyvisa
