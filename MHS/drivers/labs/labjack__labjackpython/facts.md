# Facts and tags for gh.labjack/labjackpython

Every fact cites its source at commit `a2f13eb548cca6416b1d44b08b63f7c5fd7f943b`: `upstream_code` for a line of the
clone or `vendor_doc` for a text document (the clone has no manual text; its README is the repository README and
states the U3 usage but no electrical bound). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| U3 is the LabJack U3 class of the LabJackPython package | upstream_code | src/u3.py:63-65 |
| The U3 names 20 digital I/O lines FIO0-FIO7, EIO0-EIO7 and CIO0-CIO3 (0-19) | upstream_code | src/u3.py:43-45 |
| getAIN is a convenience method that reads one analog input and returns its calibrated voltage | upstream_code | src/u3.py:588-631 |
| getTemperature reads the U3 internal temperature sensor and returns the temperature in Kelvin | upstream_code | src/u3.py:570-586 |
| configIO sends the configIO command and returns the FIOAnalog and EIOAnalog masks; with no argument it reads the current configuration | upstream_code | src/u3.py:312-421 |
| The analog and digital configuration parameters are binary-encoded 8-bit values, one bit per line; the configU3 example uses FIOAnalog = 255 and EIOAnalog = 255 | upstream_code | src/u3.py:160-186 |
| setDOState writes the state of one digital I/O line (0-19) and also sets its direction to output; state 1 is high and 0 is low | upstream_code | src/u3.py:513-530 |
| getDIOState reads the state of one digital I/O line (0-19) without changing its direction | upstream_code | src/u3.py:551-568 |
| U3.reset causes a soft or hard reset; a soft reset re-initializes most variables without re-enumeration | upstream_code | src/u3.py:954-977 |
| Device.close closes the device handle | upstream_code | src/LabJackPython.py:655-681 |

Limits: the FIOAnalog and EIOAnalog masks are the 8-bit values from `src/u3.py:160-186` (0-255); the digital line
number is 0-19 and the written state is 0 or 1 from the `setDOState` argument documentation (`src/u3.py:513-530`).

Safety: the e-stop and the safe-state action `x-cap.labjack.reset.v1` both call the native `U3.reset`
(`src/u3.py:954-977`). The card's floor is R1, and no line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set. The device is a USB DAQ; the package drives no heater, pump, laser or motion axis.

Not covered by this package: the UE9, U6 and U12 classes and their streaming, pulse and register APIs. The card's
hints for those classes mix device classes: the U12 streaming and pulse methods are not on U3; the register,
default-block and name methods the card names through UE9 do exist on U3 (inherited from `Device` or defined on U3)
but are not the convenience subset this package exposes. The card's candidate `cap.actuation.gpio.v1` binds only
`io.gpio` and `io.digital` resource kinds, so it cannot bind an `instrument.dmm` device together with
`cap.measure.voltage.v1`; the digital output uses `x-cap.labjack.set_digital_output.v1` with an inline schema instead.

Tags: daq, labjack, u3, analog input, digital io, usb
