# Facts and tags for gh.amandavical/comunication-instrument

Every fact cites its source at commit `051c4277fb025ceaec5514e920e3554ff49b9719`: `vendor_doc` (README.md, a text
file of the clone) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project simulates data collection from a virtual instrument using serial communication | vendor_doc | README.md:3 |
| The virtual instrument has temperature, voltage and current attributes | vendor_doc | README.md:17 |
| Client wraps a serial.Serial and writes a request as UTF-8 bytes followed by CRLF | upstream_code | modules/comunication_client.py:21-44 |
| read_response reads one line, decodes it and strips the surrounding whitespace | upstream_code | modules/comunication_client.py:59 |
| The simulated instrument dispatches the first three characters of a request as STA, TYP, VOL, TMP or CUR | upstream_code | modules/simulated_instrument.py:58-80 |
| STA returns a random integer from 0 to 0xFFFFFFFF | upstream_code | modules/simulated_instrument.py:62-63 |
| TYP returns one of a, b, c or abc | upstream_code | modules/simulated_instrument.py:66-67 |
| VOL returns a random integer from 0 to 220 | upstream_code | modules/simulated_instrument.py:70-71 |
| TMP returns a random integer from 0 to 85 | upstream_code | modules/simulated_instrument.py:74-75 |
| CUR returns a random integer from 0 to 2000 | upstream_code | modules/simulated_instrument.py:78-79 |
| The README describes 20 temperatures, 20 voltages, 5 statuses and 30 currents per collection | vendor_doc | README.md:52-77 |
| collect_types sends one TYP request per iteration of range(1, 6) | upstream_code | data_collection/type_collection.py:25-29 |
| The README checks temperatures above 80 degrees, voltages above 190 volts and currents outside 25 to 800 mA | vendor_doc | README.md:53-78 |
| check_temperatures raises TemperatureTooHighError above 80 degrees | upstream_code | utilities/temperature_check.py:26-28 |
| check_voltages raises VoltageTooHighError above 190 volts and reports a voltage equal to 0 | upstream_code | utilities/voltage_check.py:28-33 |
| check_current_threshold prints a threshold alert below 25 | upstream_code | utilities/current_check.py:11-12 |

Limits: none.  The upstream sends only the five read requests; it has no numeric setpoint, no write request and no
bounded invoke input.  The thresholds above are checks the demo applies to values it read; they are neither device
limits nor limits of a driver input, so they are facts, not Limits.

Safety: the e-stop closes the serial port the upstream ``Client`` wraps and sets ``Client.ser`` to ``None``
(``Client.write_request`` writes through ``self.ser``, modules/comunication_client.py:44).  The clone contains no stop
request, and a read-only client has no other native disable path.  This is R1; no independent hardware e-stop is
required, and none is claimed.

Tags: serial, measurement, virtual instrument, status, temperature, voltage, current
