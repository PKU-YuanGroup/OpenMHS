# Facts and tags for gh.pymodaq/pymodaq_plugins_keithley

This package drives the Keithley 2100 digital multimeter through the clone's `Keithley2100VISADriver`. The
clone is pinned at `7698a50e9f596e6655b33de2b88dedd4b79786f4`; every reference below is a path from the clone root.

The same facts are written into `driver.py` (`facts = [...]`); the generated reference file comes from the driver,
not from this page.

| fact | source | ref |
|---|---|---|
| The plugin lists the Keithley 2100 as a 0D viewer multimeter | vendor_doc | README.rst:43-47 |
| set_mode documents VDC, VAC, IDC, IAC, R2W and R4W as the supported measurement modes | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:87 |
| set_mode picks the function from the mode name: Ohm2/R2W -> RES, Ohm4/R4W -> FRES, VDC/V -> VOLT:DC, VAC -> VOLT:AC, IDC/I -> CURR:DC and IAC -> CURR:AC | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:99-110 |
| A configuration is sent as ':CONF:' followed by the function name, with an optional range and resolution appended | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:97-119 |
| read() sends READ? and converts the answer to float | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:79-80 |
| The identity, installed option card and last error are queried with *IDN?, *OPT? and SYST:ERR? | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:47-54 |
| reset() sends *CLS and then *RST | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:75-77 |
| The VISA resource is opened with a newline write termination | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:29-31 |
| close() opens all routes with ROUT:OPEN:ALL before it closes the VISA resource | upstream_code | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:43-45 |

Limits (all `upstream_code`):

| parameter | limit | ref |
|---|---|---|
| mode | one of VDC, VAC, IDC, IAC, R2W, R4W | src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py:87 |

No text file of the clone states a numeric range or resolution for this instrument. The driver therefore exposes
no range or resolution write: a bound for one would have to be supplied by the site, and an unsourced bound is not
written into the package. The `reading` value is in the unit of the active function (volts for VDC/VAC, amperes for
IDC/IAC, ohms for R2W/R4W, as the function map shows); the upstream class has no query that returns the active
mode, so the `mode` read reports the last mode this driver applied and `unknown` before that.

Safety: at R1 the package needs no physical e-stop. The e-stop calls the native reset (`*CLS`, `*RST`), the only
recovery the upstream class offers; the same reset is exposed as the extension action
`x-cap.pymodaq.keithley2100_reset.v1`. The driver does not set a watchdog. No hardware backend was run.

The upstream class docstring points to a vendor manual URL. That manual was not read and no number from it is used
here. The clone's other entry classes (2110, 2700, 2701, 2750) are outside this package: their constructors or
configuration readers depend on the PyMoDAQ configuration file, and this driver targets the self-contained 2100
class. The 2100 driver's `close()` sends `ROUT:OPEN:ALL` as the clone does, even though this package never selects
a route.

Tags: keithley, 2100, multimeter, dmm, visa, scpi
