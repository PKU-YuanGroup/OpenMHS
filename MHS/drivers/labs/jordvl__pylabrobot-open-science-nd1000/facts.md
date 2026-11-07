# Facts and tags for gh.jordvl/pylabrobot-open-science-nd1000

Every fact cites its source at commit `db60b66494230b65d0c88bca07ce1304a1a974ee`: `vendor_doc` (a text file of the
clone, here `Code/NanoDropInstalInstructions.txt`) or `upstream_code` (`path/in/clone:LINE`). The same facts are in
`driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The USB device has VID 0x2457, PID 0x1002 and three endpoints (command, spectrum, text/status) | upstream_code | Code/nanodrop.py:7-12 |
| connect() finds the device, clears the endpoint halts, sends wake 0x08 and init 0x01, downloads the factory coefficients and calculates the wavelength axis | upstream_code | Code/nanodrop.py:23-44 |
| close() turns the lamp and magnet off, resets the USB device and disposes the resources | upstream_code | Code/nanodrop.py:46-56 |
| set_lamp(state) writes command 0x03 with 0xFF for on and 0x00 for off | upstream_code | Code/nanodrop.py:62-64 |
| set_magnet(state) writes command 0x0F with 0xFF for on and 0x00 for off | upstream_code | Code/nanodrop.py:66-68 |
| take_blank sets the magnet True before its dark reading, with the comment "Arm down" | upstream_code | Code/nanodrop.py:139-143 |
| measure_absorbance sets the magnet True before its sample reading | upstream_code | Code/nanodrop.py:160-162 |
| set_integration_time(ms) documents the valid range 3 to 65535 ms, clamps outside it and writes command 0x02 little-endian | upstream_code | Code/nanodrop.py:70-81 |
| _calculate_x_axis builds a 2048-element wavelength array in nanometres from coefficients 1 through 4 | upstream_code | Code/nanodrop.py:103-108 |
| get_raw_spectrum() sends command 0x09 and decodes 64 reads of 64 bytes into 2048 16-bit pixels | upstream_code | Code/nanodrop.py:111-131 |
| take_blank(integration_ms=20) captures a dark frame and then a blank frame and turns the lamp and magnet off | upstream_code | Code/nanodrop.py:134-153 |
| measure_absorbance(integration_ms=20) requires the stored dark and blank spectra and returns the wavelength axis with -log10((sample-dark)/(blank-dark)) | upstream_code | Code/nanodrop.py:155-179 |
| The example script plots the active sensor area roughly from 220 nm to 750 nm | upstream_code | Code/main.py:22-28 |
| The installation guide describes the old USB 1.1 microcontroller and the Zadig libusb-win32 driver replacement | vendor_doc | Code/NanoDropInstalInstructions.txt:3-20 |
| ThermoFisherNanoDrop1000 constructs one driver and one absorbance backend sharing it | upstream_code | Code/ThermoFisherNanoDrop1000_PLR_V1.py:220-235 |

## Limits

| input | bound | source | ref |
|---|---|---|---|
| integration_time / integration_ms | 3 to 65535 ms | upstream_code | Code/nanodrop.py:71 |
| wavelength_min | operator_required: the clone states no detector wavelength range | operator | site-limits.example.json |
| wavelength_max | operator_required: the clone states no detector wavelength range | operator | site-limits.example.json |

## Safety

The e-stop turns the lamp and the sample-arm magnet off (`set_lamp(False)`, `set_magnet(False)`), the commands the
upstream `close()` sends (Code/nanodrop.py:46-56). Both are unacknowledged USB writes; the clone comments only the
magnet-on command ("Arm down", Code/nanodrop.py:140) and states nothing about the arm after the magnet is released.
No independent hardware e-stop is documented in the clone, so `estop_physical_ref` is not set and the package is R1.
A USB read already in flight is not interrupted by the stop.

The upstream `set_integration_time` splits the value into two bytes with `&` and `>>` (Code/nanodrop.py:79-81), so a
float raises `TypeError` there; the driver passes whole milliseconds as an int and refuses a fractional value with
`MHS.CAPABILITY.INPUT_INVALID` instead of rounding it.

Tags: spectrometer, spectrophotometer, absorbance, uv-vis, nanodrop, usb, pylabrobot.
