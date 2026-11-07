# Facts and tags for gh.liamsgithub/as7265x-spectrometer

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

Every fact cites its source at commit `9b0ce11be6b904a89e907dc18dd10b03620cc90f`; the same facts are written into
`driver.py` (`facts = [...]`), and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a Python 2.7 module: line 341 is a print statement, so the Python 3 ast parser cannot read the file | upstream_code | spectrometer.py:341 |
| The module constructs SMBus(1) at import time and talks to the AS7265x at I2C address 0x49 | upstream_code | spectrometer.py:10-20 |
| init() writes register 0x04 with 1 and sleeps 4 seconds after the factory reset | upstream_code | spectrometer.py:155-160 |
| boardPresent() reads register 0x00 and returns True or False | upstream_code | spectrometer.py:167-172 |
| hwVersion() reads registers 0x00 and 0x01 and returns a tuple of the device type and hardware version | upstream_code | spectrometer.py:178-184 |
| temperatures() selects AS72651, AS72652 and AS72653 and reads register 0x06 from each into a list of three values | upstream_code | spectrometer.py:194-201 |
| setBlueLED(state) selects AS72651 and writes bit 0 of register 0x07 | upstream_code | spectrometer.py:208-220 |
| shutterLED(device,state) selects one of AS72651, AS72652 or AS72653 and writes bit 3 of register 0x07 | upstream_code | spectrometer.py:226-247 |
| setLEDDriveCurrent accepts 0, 1, 2 or 3 and writes bits 4-5 of register 0x07 on all three devices; the docstring maps them to 12.5, 25, 50 and 100 mA | upstream_code | spectrometer.py:252-269 |
| setIntegrationTime checks range(0,255), so it accepts 0 through 254, and writes register 0x05 on all three devices; the docstring says 0 to 255 | upstream_code | spectrometer.py:273-292 |
| setGain accepts 0, 1, 2 or 3 and writes bits 4-5 of register 0x04 on all three devices; the docstring maps them to 1x, 3.7x, 16x and 64x | upstream_code | spectrometer.py:296-318 |
| readRAW() reads six 16-bit register pairs from each of the three devices, giving 18 raw values, and reorders them into ascending frequency order | upstream_code | spectrometer.py:325-343 |
| readCAL() reads six IEEE754 quadruples from each of the three devices, giving 18 calibrated values, and reorders them into ascending frequency order | upstream_code | spectrometer.py:350-371 |
| reorderData maps the 18 values from the device read order to the monotonic frequency order | upstream_code | spectrometer.py:138-146 |
| The README calls the project a Python module to drive the SparkFun Triad Spectroscopy Sensor | vendor_doc | README.md:1-3 |
| The board consists of three devices with six sensors each and passbands from UV to IR; the three on-board LEDs peak at about 400, 475 and 875 nm | vendor_doc | README.md:5-9 |
| The README targets Python 2.7 on a Raspberry Pi 3B | vendor_doc | README.md:19 |
| The README lists setIntegrationTime legal input values 0 to 255, setGain 0 to 3 and setLEDDriveCurrent 0 to 3 | vendor_doc | README.md:66-87 |
| The README says readRAW and readCAL return 18 values sorted into ascending frequency order | vendor_doc | README.md:88-101 |

## Limits

| field | limit | source | ref |
|---|---|---|---|
| integration_time_register | min 0, max 254, unit 1; the clone's range(0,255) excludes 255 although its docstring says 0 to 255 | upstream_code | spectrometer.py:280 |
| gain | allowed 0, 1, 2, 3, unit 1 | upstream_code | spectrometer.py:303 |
| led_drive_current | allowed 0, 1, 2, 3, unit 1 | upstream_code | spectrometer.py:258 |

The wavelength axis of the 18 channels is not stated by the clone: README.md:5-9 names only the three LED peaks.
The raw and calibrated arrays therefore use the extension `x-cap.liamsgithub.read_spectrum.v1`; the scalar
`cap.measure.intensity.v1` action names a channel by its 1-through-18 position in the clone's ascending-frequency
order.

## Safety

The device's only active outputs are the on-board LEDs; the package is R1 and turns them off through the native
`setBlueLED(False)` and `shutterLED(device, False)` calls (spectrometer.py:208-247).  The e-stop and the
safe-state action `x-cap.liamsgithub.leds_off.v1` call that path: they attempt all four LEDs even when one call
fails, then read register 0x07 of the three devices back and succeed only when every LED reads off.  The e-stop
first marks the device stopped, so an effectful call that was admitted before the runtime latched but had not yet
reached the device is refused instead of writing after the stop; an accepted safety reset releases that mark and
writes nothing to the device.

`native.py` is the package's own Python 3 port, not the clone.  Each virtual-register transaction runs under one
bus lock, a read-modify-write holds it across its read and its write, and device selection (register 0x4F) is kept
per calling thread, so a stop never interleaves inside a transaction or redirects a running measurement to another
device.  Every status wait ends after 1 s and every bus-lock wait after 2 s with `TimeoutError`; these are host
bounds of the port, not device limits.  A single SMBus call that blocks inside the operating system cannot be
interrupted from Python: a stop that meets one fails, and the runtime keeps its latch
(`MHS.SAFETY.SAFE_STATE_UNREACHED`).  No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; no physical protection is claimed.  The hardware backend was never run.

## Tags

spectrometer, as7265x, sparkfun, triad, i2c, led
