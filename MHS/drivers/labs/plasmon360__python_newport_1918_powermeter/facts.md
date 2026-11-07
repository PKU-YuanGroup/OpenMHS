# Facts and tags for gh.plasmon360/python_newport_1918_powermeter

Every fact cites its source at commit `5c8ae02c1f9d412c0cbabec39141e99393e0f048`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README describes a Python module that communicates with a Newport 1918 power meter on a Windows computer through ctypes and Newport's usbdll.dll | vendor_doc | README.md:8 |
| The module is written for Python 2.7 and the README says it would need minor modifications for Python 3+ | vendor_doc | README.md:12 |
| The user-facing device class is Newport_1918c | upstream_code | newport_1918c.py:21 |
| The constructor loads usbdll.dll with windll.LoadLibrary, defaulting to the 32-bit Newport install path and product id 0xCEC7 | upstream_code | newport_1918c.py:24-27 |
| The constructor opens the device by product id and reads the device id, model number and serial number from get_instrument_list | upstream_code | newport_1918c.py:32-35 |
| open_device_with_product_id opens the instrument with newp_usb_open_devices and stores the connection state | upstream_code | newport_1918c.py:45-66 |
| get_instrument_list returns the device id, model number and serial number | upstream_code | newport_1918c.py:81-95 |
| ask sends a query with newp_usb_send_ascii and reads the reply with newp_usb_get_ascii | upstream_code | newport_1918c.py:99-127 |
| write sends a command string with newp_usb_send_ascii | upstream_code | newport_1918c.py:129-148 |
| set_wavelength converts a float wavelength to an integer, reads PM:MIN:Lambda? and PM:MAX:Lambda?, and writes PM:Lambda only when the value is inside that range | upstream_code | newport_1918c.py:150-162 |
| read_buffer writes the PM:DS:* datastore commands, polls PM:DS:COUNT?, and reads PM:Lambda?, PM:STAT:MEAN? and PM:STAT:SDEV? | upstream_code | newport_1918c.py:187-208 |
| read_instant_power sets the wavelength and returns the replies to PM:Lambda? and PM:Power? | upstream_code | newport_1918c.py:210-219 |
| close_device closes the instrument with newp_usb_uninit_system | upstream_code | newport_1918c.py:68-79 |
| The example measures at a 500 nm wavelength and sweeps 500 to 550 nm with an interval of 10 nm | upstream_code | newport_1918c.py:315-322 |

## What the package serves

- Reads: `wavelength_nm` (PM:Lambda?, the wavelength the meter is set to), `serial_number` and `model_number` (the
  values GetInstrumentList returns). The unit of the wavelength is nm, as the example comments call the 500 to 550
  values nanometres (`newport_1918c.py:315-322`).
- Writes: `wavelength_nm`, through the native `set_wavelength`, which writes PM:Lambda in whole nanometres
  (`newport_1918c.py:150-162`); the setter returns the wavelength the instrument reports after the write.
- `cap.measure.intensity.v1`: one power reading. Without a wavelength the driver asks PM:Power? at the wavelength the
  instrument already holds; with a wavelength it calls the native `read_instant_power`, which sets the wavelength and
  returns PM:Lambda? and PM:Power?. The class returns the PM:Power? reply as text and the clone states no unit for it,
  so the value is reported as the class returns it, in the dimensionless unit of the catalogue output field.
- The upstream datastore mean and standard deviation (`read_buffer`, `newport_1918c.py:187-208`) and the sweep
  helpers are not exposed: the package serves one scalar reading and does not invent a buffering contract.

## Limits

- `wavelength_nm` is `Limit.operator_required` on both the writable state parameter and the
  `cap.measure.intensity.v1` input. No text file of the clone states the wavelength range of the instrument:
  `set_wavelength` reads PM:MIN:Lambda? and PM:MAX:Lambda? from the device at run time (`newport_1918c.py:159`), and
  the 500 to 550 nm values in the example are calls, not bounds (`newport_1918c.py:315-322`). Until the operator
  supplies a range in `site-limits.json`, every write or call that carries a wavelength is refused
  `MHS.SAFETY.LIMITS_UNSET`; `site-limits.example.json` shows an example overlay, not a statement about any
  instrument.

## Safety

The device observes optical power and actuates no external output. Writing the configured wavelength is the
`cap.device.configure.v1` class, whose floor is R1, so the device is declared R1 above the card's R0 floor. The only
native stop the class has is `close_device` (`newport_1918c.py:68-79`), which closes the USB session with
newp_usb_uninit_system; it is exposed as the e-stop and the safe state is the closed USB session. This is a software
stop, not a safety-rated channel, and no independent hardware e-stop is claimed.

## Tags

optical-power, power-meter, newport, usb, ctypes, measurement
