# Facts and tags for gh.urmel79/jupyter_pyvisa_lab

Every fact cites its source at commit `418a7f6bbef16a7c30ece599f8367fe5585291d9`: `vendor_doc` or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page. The clone's README has only three lines and no
manual is present, so every fact below is `upstream_code`.

| fact | source | ref |
|---|---|---|
| The module is a wrapper class for the DMM Benning MM12 | upstream_code | Benning_MM12_class.py:6 |
| The information request is the fixed frame 55 55 00 00 AA and the display request is 55 55 01 00 AB | upstream_code | Benning_MM12_class.py:15-16 |
| The function table maps codes 0x00 to 0x31 to a measuring mode and an SI base unit | upstream_code | Benning_MM12_class.py:21-72 |
| The range multiplier tables are indexed by the range code and differ per measuring function | upstream_code | Benning_MM12_class.py:74-144 |
| getDeviceInfos sends the information frame, reads 57 bytes and validates the reply 0x55550034 | upstream_code | Benning_MM12_class.py:282-301 |
| getDeviceInfos returns the model name, serial number, model ID and firmware version | upstream_code | Benning_MM12_class.py:303-337 |
| getMeasurement_baseUnits sends the display frame, reads 17 bytes and validates the reply 0x5555010C | upstream_code | Benning_MM12_class.py:340-359 |
| The MSB of the function and range codes marks auto or manual selection and is masked before lookup | upstream_code | Benning_MM12_class.py:369-381 |
| getMeasurement_baseUnits returns the function name, the value and its SI base unit | upstream_code | Benning_MM12_class.py:458-460 |
| The display unit is bits 7..3 and the display multiplier is bits 2..0 of the scope code | upstream_code | Benning_MM12_class.py:500-508 |
| getMeasurement_humanUnits returns the value in the unit shown on the display | upstream_code | Benning_MM12_class.py:486-513 |
| The three-byte measurement value is decoded as an unsigned little-endian integer (signed=False) | upstream_code | Benning_MM12_class.py:267-274 |
| The comment above the three-byte measurement field calls it a 24bit signed integer | upstream_code | Benning_MM12_class.py:453-456 |
| The serial port is opened at 9600 baud, 8 data bits, no parity, one stop bit and a 2 s timeout | upstream_code | Benning_MM12_class.py:193 |
| openConnection and closeConnection are the open and close methods of the serial port | upstream_code | Benning_MM12_class.py:203-233 |

Limits: none. The MM12 is a read-only meter. The upstream class has two query methods and one identity query; it
sends no set command and accepts no numeric setpoint. The only capability input is the ``fields`` array of channel
names, so there is no numeric write or invoke input for a Limit to bound. The range multipliers are conversion data
of the received display frame, not settable bounds.

Safety: the device is R0 and read-only. It has no actuator, heater, laser, motion or source output, so there is no
native stop, safe state or independent e-stop to claim. The driver never clamps, retries or actuates anything.

Classification: the driver uses ``device_kind = "sensor"`` because ``cap.sensing.read.v1`` binds the resource kinds
``sensor``, ``sensor.imu`` and ``sensor.force_torque``; it does not bind ``instrument.dmm``. The MM12 is a
multimeter, but the catalogue's generic sensing-read class is the class that carries its free-form
``function``/``value``/``unit`` display result. The driver does not switch the measuring function or range: the
front-panel selection is reported as read.

Mock path: the clone contains no simulator and no tests. The package fake is a recording stand-in with fixed replies;
every reply is placeholder test data, not a device fact. The upstream's measurement value is decoded with
``signed=False`` even though the comment calls it signed (see the two facts above), so a negative reading of the raw
frame would not be represented by the upstream method; the driver does not re-decode the frame.

Tags: multimeter, dmm, benning, serial, measurement
