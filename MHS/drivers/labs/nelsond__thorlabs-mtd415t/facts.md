# Facts and tags for gh.nelsond/thorlabs-mtd415t

The clone is a small serial wrapper around the Thorlabs MTD415T OEM temperature controller. This package is a
direct Driver over `thorlabs_mtd415t.mtd415t_device:MTD415TDevice` (the card's `decision` is direct-driver); every
request is assembled from a setting letter plus `?` or a decimal value
(`thorlabs_mtd415t/mtd415t_device.py:70-78, 94-104`).

Every fact cites its source at commit `c53ec5c7db67f4cb47619d2ceaa4aead5e583923`: `upstream_code` is a code,
docstring or comment line of the clone; `vendor_doc` is a text file of the clone. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The class controls and configures the Thorlabs MTD415T digital temperature controller over a serial port | upstream_code | thorlabs_mtd415t/mtd415t_device.py:30-32 |
| The constructor passes the port and baudrate 115200 to SerialDevice | upstream_code | thorlabs_mtd415t/mtd415t_device.py:55 |
| SerialDevice opens the port with serial_for_url(port, baudrate=baudrate, **kwargs) | upstream_code | thorlabs_mtd415t/serial_device.py:22-24 |
| A query appends '?' to the setting name and retries once after 100 ms when the reply is 'unknown command' | upstream_code | thorlabs_mtd415t/mtd415t_device.py:70-78 |
| write appends a newline to the bytes and read returns one line of the serial port | upstream_code | thorlabs_mtd415t/serial_device.py:69-91 |
| idn queries the setting 'm' and strips the reply | upstream_code | thorlabs_mtd415t/mtd415t_device.py:138 |
| uid queries the setting 'u' and strips the reply | upstream_code | thorlabs_mtd415t/mtd415t_device.py:143 |
| temp queries 'Te' and divides the reply by 1000, so it is a temperature in degrees Celsius | upstream_code | thorlabs_mtd415t/mtd415t_device.py:192-196 |
| temp_setpoint queries 'T' and divides the reply by 1000; the docstring states 5.000 to 45.000 degrees Celsius | upstream_code | thorlabs_mtd415t/mtd415t_device.py:199-202 |
| The temperature setpoint setter validates the range 5 to 45 degrees Celsius and writes 'T' with the value in millidegrees | upstream_code | thorlabs_mtd415t/mtd415t_device.py:204-211 |
| tec_current queries 'A' and divides the reply by 1000, so it is a current in amperes | upstream_code | thorlabs_mtd415t/mtd415t_device.py:180-184 |
| tec_voltage queries 'U' and divides the reply by 1000, so it is a voltage in volts | upstream_code | thorlabs_mtd415t/mtd415t_device.py:186-190 |
| tec_current_limit queries 'L' and divides the reply by 1000; its setter range is 0.2 to 2 amperes | upstream_code | thorlabs_mtd415t/mtd415t_device.py:165-178 |
| error_flags queries 'E', decodes the reply as 16 binary digits and returns the bits with the least significant bit first | upstream_code | thorlabs_mtd415t/mtd415t_device.py:145-150 |
| The error register bits are the MTD415T datasheet errors (not enabled, sensor, TEC, range and command errors) | upstream_code | thorlabs_mtd415t/mtd415t_device.py:40-51 |
| errors returns the text of every error bit that is set | upstream_code | thorlabs_mtd415t/mtd415t_device.py:152-163 |
| close closes the serial connection | upstream_code | thorlabs_mtd415t/serial_device.py:50-54 |
| is_open reports whether the serial port is open | upstream_code | thorlabs_mtd415t/serial_device.py:93-96 |
| The README describes the repository as a wrapper for the Thorlabs MTD415T OEM temperature controller module | vendor_doc | README.md:3 |

## Limits

None. This package binds no `@write` parameter and no numeric invoke input: every method is a read or the
temperature measurement, so there is no field whose bound the runtime would enforce and no `Limit` to declare.
The numeric ranges the upstream setter code states (setpoint 5 to 45 degrees Celsius,
`thorlabs_mtd415t/mtd415t_device.py:208`; TEC current limit 0.2 to 2 amperes, `mtd415t_device.py:175`; and the PID
and timing ranges, `mtd415t_device.py:224-330`) are recorded above as facts of the write paths this package does
not bind.

## Scope and safety

The reader methods are `MTD415TDevice.temp`, `temp_setpoint`, `tec_current`, `tec_voltage`, `tec_current_limit`,
`errors`, `idn`, `uid` and the inherited `SerialDevice.is_open` (`thorlabs_mtd415t/mtd415t_device.py:126-333`,
`thorlabs_mtd415t/serial_device.py:93-96`). `cap.measure.temperature.v1` is the only capability and returns
`temp`.

The upstream also offers setters: `temp_setpoint` (heating/cooling), `tec_current_limit`, `status_temp_window`,
`status_delay`, `critical_gain`, `critical_period`, `cycling_time`, `p_gain`, `i_gain` and `d_gain`
(`mtd415t_device.py:171-333`), plus `save` and `clear_errors` (`mtd415t_device.py:112-124`). None is bound: a
temperature setpoint is a heating/cooling actuation (R2 or above under `MHS/spec/04-safety.md`) and the clone has no
output-disable, stop or safe-state command -- `errors` even lists a `not enabled` bit
(`mtd415t_device.py:42`), but the wrapper exposes no request that would disable the TEC output. With no honest native
safe state for a heating driver, this package stays observational: it reads state and never changes the controller's
stored regulation. Its risk class is the class floor of its only bound capability, R0.

The hardware path was never run: `native.py` opens the upstream class, the gate never imports it, and
`driver.lock.json` `reviewed_by` is null. No claim of hardware testing or human review is made.

Tags: thorlabs, mtd415t, temperature, thermometer, tec, serial
