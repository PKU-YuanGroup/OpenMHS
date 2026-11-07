# Facts and tags for gh.lachlangunn/oic

Every fact cites its source at commit `6c7ab800893dcd32584053b49a7825452e3119a9`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The firmware answers *IDN? with the exact line 'OIC,Embedded SCPI Example,1,10' | upstream_code | src/Examples/Meter/Meter.ino:78 |
| The host example requires that exact identity reply and closes the resource otherwise | upstream_code | src/Examples/Meter/test.py:14-19 |
| The serial link runs at 9600 baud and each command is one newline-terminated line of at most 256 bytes | upstream_code | src/Examples/Meter/Meter.ino:51-62 |
| The host example opens a VISA resource with a newline terminator | upstream_code | src/Examples/Meter/test.py:10 |
| Communication is over the device's virtual serial port with a bare-bones SCPI implementation | vendor_doc | README.md:37-38 |
| The README documents ':SOURCE:VOLTAGE 1V' on pin three and ':MEASURE:VOLTAGE?' on analogue input zero | vendor_doc | README.md:28-29 |
| The command tree registers *IDN?, :SOURCE:VOLTAGE, :SOURCE:VOLTAGE1, :MEASURE:VOLTAGE?, :MEASURE:VOLTAGE1? and :MEASURE:VOLTAGE2? | upstream_code | src/Examples/Meter/Meter.ino:33-43 |
| :MEASURE:VOLTAGE? returns analogRead(0) * 5.0f/1024, the voltage on A0 | upstream_code | src/Examples/Meter/Meter.ino:89 |
| :MEASURE:VOLTAGE1? returns analogRead(1) * 5.0f/1024, the voltage on A1 | upstream_code | src/Examples/Meter/Meter.ino:103 |
| :MEASURE:VOLTAGE2? returns analogRead(2) * 5.0f/1024, the voltage on A2 | upstream_code | src/Examples/Meter/Meter.ino:117 |
| scpi_parse_numeric takes (string, length, default_value, min_value, max_value) | upstream_code | src/ArduinoSCPIParser/scpiparser.h:223-224 |
| :SOURCE:VOLTAGE parses a voltage with min 0 and max 5, scales it by 5.0 V into 0-255 and writes PWM pin 3 | upstream_code | src/Examples/Meter/Meter.ino:140-144 |
| :SOURCE:VOLTAGE1 parses a voltage with min 0 and max 5, scales it by 5.0 V into 0-255 and writes PWM pin 5 | upstream_code | src/Examples/Meter/Meter.ino:187-191 |
| A source value is a number with an optional V suffix; a bare number is volts, and the NT unit selects a raw 0-255 duty | upstream_code | src/Examples/Meter/Meter.ino:141-149 |
| The host example writes source values as strings such as '0V' and '5V' | upstream_code | src/Examples/Meter/test.py:66-67 |
| The PWM outputs are initialised to zero at setup (analogWrite(3, 0) and analogWrite(5, 0)) | upstream_code | src/Examples/Meter/Meter.ino:48-49 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| voltage0 (V) | :SOURCE:VOLTAGE | 0 to 5 V | src/Examples/Meter/Meter.ino:140 (scpi_parse_numeric default 0, min 0, max 5; the declaration order is at src/ArduinoSCPIParser/scpiparser.h:224) |
| voltage1 (V) | :SOURCE:VOLTAGE1 | 0 to 5 V | src/Examples/Meter/Meter.ino:187 (the same parse for channel 1) |

The firmware clamps the PWM duty to 0-255 after scaling by 5.0 V (`Meter.ino:144`, `191`), so the driver accepts the
0-5 V full scale and refuses values outside it before any command reaches the wire.

Safety: the e-stop writes `:SOURCE:VOLTAGE 0V` and then `:SOURCE:VOLTAGE1 0V`, the lowest value of the only outputs
this driver sets.  It does not touch the input channels.  There is no hardware e-stop to cite at R1.

Tags: arduino, daq, dmm, scpi, serial, pwm
