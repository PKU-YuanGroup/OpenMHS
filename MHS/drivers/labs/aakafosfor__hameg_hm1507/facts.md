# Facts and tags for gh.aakafosfor/hameg_hm1507

Every fact cites the clone at commit `0a03fdc25414d400331769c9e125dd80e0cf5964`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The clone has no
README, manual, datasheet or licence file, so every fact here is `upstream_code`.

| fact | source | ref |
|---|---|---|
| The remote interface is a serial port opened at 19200 baud with RTS/CTS, two stop bits, no parity and a one-second timeout | upstream_code | HAMEG_HM1507.py:62-67 |
| connect() sends a single space after opening the port | upstream_code | HAMEG_HM1507.py:68 |
| A command is written one character at a time and then a carriage return | upstream_code | HAMEG_HM1507.py:77-82 |
| The class has no read or query method; the only readline call is commented out | upstream_code | HAMEG_HM1507.py:77-85 |
| autoset() sends AUTOSET | upstream_code | HAMEG_HM1507.py:87-88 |
| Only time bases A and B exist | upstream_code | HAMEG_HM1507.py:90-92 |
| A time base setting adds 32 for single sweep plus the index of the time/div value and sends TB<base>=<chr(settings)> | upstream_code | HAMEG_HM1507.py:93-100 |
| The time/div list has 29 entries from 50ns to 100s | upstream_code | HAMEG_HM1507.py:6-36 |
| Only channels 1 and 2 exist | upstream_code | HAMEG_HM1507.py:102-104 |
| A channel setting starts at 16, adds 32 for invert, 64 for AC coupling and the index of the volts/div value, then sends CH<channel>=<chr(settings)> | upstream_code | HAMEG_HM1507.py:105-114 |
| The volts/div list has 14 entries from 1mV to 20V | upstream_code | HAMEG_HM1507.py:37-52 |
| disconnect() sends rm0 and closes the port | upstream_code | HAMEG_HM1507.py:70-75 |
| The upstream GUI keeps separate settings for channels 1 and 2 and for time bases A and B | upstream_code | gui.py:15-36 |

Limits (all `upstream_code`):

| parameter | native command | limit | ref |
|---|---|---|---|
| timebase.base | TB<base>=<chr> | A or B | HAMEG_HM1507.py:91 |
| timebase.time_div | TB<base>=<chr> | one of the 29 time/div values, 50ns to 100s | HAMEG_HM1507.py:6-36 |
| channel.channel | CH<channel>=<chr> | 1 or 2 | HAMEG_HM1507.py:103 |
| channel.volts_div | CH<channel>=<chr> | one of the 14 volts/div values, 1mV to 20V | HAMEG_HM1507.py:37-52 |

The single-sweep, invert and mode_dc flags are booleans and need no numeric bound; the base and channel selectors are
explicit fields of the two objects, so the command always carries every setting the upstream call needs.

Safety: the e-stop is the upstream `disconnect()` (HAMEG_HM1507.py:70-75), which releases remote control with `rm0`
and closes the port. The scope has no commanded output through this interface: the commands set only the time base and
the input channels. The resource state reports the values the driver last sent, because the upstream class has no query
method (HAMEG_HM1507.py:77-85).

Tags: oscilloscope, hameg, hm1507, serial, instrument
