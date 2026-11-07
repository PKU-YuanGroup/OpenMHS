# Facts and tags for gh.natlabrockies/multi-tube-od-reader

Every fact cites its source at commit `e3948da8586d40093ffb7cc64706f4c6defa6326`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Device is the Python object representing one Multi-Tube-OD-Reader instrument | upstream_code | my_app/classes/device.py:34-43 |
| The Device constructor keeps a list of Port objects for physical positions 1 through 16 | upstream_code | my_app/classes/device.py:57-58 |
| Device.discovery enumerates connected U3 devices with u3.openAllU3() and creates one Device per serial number | upstream_code | my_app/classes/device.py:89-108 |
| Device.connect opens u3.U3 by serial number and returns the LabJack U3 interface | upstream_code | my_app/classes/device.py:112-120 |
| Device.rename writes the new name with U3.setName and updates the Device name | upstream_code | my_app/classes/device.py:122-132 |
| Device.blink toggles the built-in LED and DAC0 in 25 passes with 0.15 s between passes | upstream_code | my_app/classes/device.py:134-148 |
| The clone opens and closes the LabJack connection at each timepoint so parallel experiments can share the hardware | upstream_code | my_app/classes/device.py:20-24 |
| After discovery the clone closes all U3 connections with Close() so other experiments can use the hardware | upstream_code | my_app/classes/device.py:108 |
| measure_voltage maps port numbers to AIN positions (port number minus one) and sets the FIO/EIO analog masks for the requested ports | upstream_code | my_app/timecourse.py:65-68 |
| DAC0 powers the LED/sensor relay and DAC1 the linear regulator to the sensors; the configured voltages are 5 V and 2.6 V | upstream_code | my_app/timecourse.py:11-16 |
| measure_voltage sets the DAC voltages before sampling and returns both DACs to 0 after sampling | upstream_code | my_app/timecourse.py:70-83 |
| measure_voltage averages n_reps calibrated analog voltage samples and returns one mean per requested port | upstream_code | my_app/timecourse.py:75-92 |
| measure_temp reads the U3 internal temperature in Kelvin and converts it to Celsius | upstream_code | my_app/timecourse.py:97-105 |
| The README states that the repository controls a 16-tube, in-line optical density monitoring device | vendor_doc | README.md:6 |
| The README says raw measurements are voltages and that log10(voltage) is fitted to known optical densities offline | vendor_doc | README.md:70-73 |
| The README requires a U3-compatible LabJack driver: UD on Windows, Exodriver on Linux/macOS | vendor_doc | README.md:83-85 |
| The pinned requirements file lists LabJackPython 2.1.0 | upstream_code | my_app/requirements.txt:6 |

Limits: none.  The driver declares no numeric write or invoke input: the only write is the firmware name (a
string), and the measurement input is a port number chosen from the enumerated 1..16 set.  The clone states no
voltage, current, temperature or timing bound for the instrument, so no Limit is declared and no operator overlay
is needed.  The 1..16 port set comes from the Device constructor (my_app/classes/device.py:58), not from a
constructor default of a library.

Shape: the clone's measurement entry point is the module function `timecourse.measure_voltage` (line 59), not a
`Device` method.  The driver uses `Device.connect()` (device.py:112-120), which returns the LabJack U3 handle, and
reads one calibrated analog input per call.  The DAC power-on/off sequence (timecourse.py:70-83) is implemented on
the hardware path in `native.py`; the upstream n_reps average is not reproduced (one sample per call), and the
fake returns one canned sample.  This is a faithful subset of the native analog input read, not a recording of a
device.

Safety: the package is R1 (the card floor).  The clone describes a reader that powers LEDs/sensors and measures
analog voltages; neither the README nor the code names a heater, pump, laser, motion axis or high-force actuator.
The native stop opens and closes the U3 handle so no connection is left open.  No line of the clone documents an
independent hardware e-stop, so `estop_physical_ref` is not set.  The e-stop is not a safety-rated stop, it does
not interrupt a blocking getAIN, and OpenMHS is not a safety certification.

Tags: optical density, growth monitoring, labjack u3, analog input, 16-port
