# Facts and tags for gh.usnistgov/ssmdevices

Every fact cites its source at commit `4680dde885660d6aa467dc883aec1226f401589a`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MiniCircuitsRCDAT is the Mini-Circuits USB switch attenuator class and fixes product ID 0x23 | upstream_code | src/ssmdevices/instruments/attenuators.py:13-15 |
| The Mini-Circuits USB base class declares vendor ID 0x20CE for USB HID devices | upstream_code | src/ssmdevices/instruments/_minicircuits_usb.py:15-18 |
| The uncalibrated attenuation_setting property is bounded to 0 to 115 dB with a 0.25 dB step | upstream_code | src/ssmdevices/instruments/attenuators.py:52-54 |
| attenuation_setting reads with command code 18 and writes with command code 19 | upstream_code | src/ssmdevices/instruments/attenuators.py:55-88 |
| The attenuation setter sends the whole-decibel part and the quarter-decibel part, plus the channel | upstream_code | src/ssmdevices/instruments/attenuators.py:78-86 |
| channel selects a port from 1 to 4, and None addresses a single attenuator | upstream_code | src/ssmdevices/instruments/attenuators.py:42-49 |
| frequency selects the calibration-table row and is bounded to 10 MHz to 6 GHz | upstream_code | src/ssmdevices/instruments/attenuators.py:17-24 |
| attenuation is the calibrated value from the table at calibration_path, indexed by frequency | upstream_code | src/ssmdevices/instruments/attenuators.py:90-97 |
| output_power is -attenuation + output_power_offset in dBm | upstream_code | src/ssmdevices/instruments/attenuators.py:99-103 |
| model and serial_number are read with command codes 40 and 41 | upstream_code | src/ssmdevices/instruments/_minicircuits_usb.py:231-249 |
| A command is at most 64 one-byte values and the reply must echo the command code within timeout | upstream_code | src/ssmdevices/instruments/_minicircuits_usb.py:62-92 |
| open() resolves the HID path and opens it in nonblocking mode | upstream_code | src/ssmdevices/instruments/_minicircuits_usb.py:35-43 |
| close() closes the HID backend | upstream_code | src/ssmdevices/instruments/_minicircuits_usb.py:52-54 |
| The USB command timeout defaults to 1 s and its minimum is 0.5 s | upstream_code | src/ssmdevices/instruments/_minicircuits_usb.py:33 |
| The serial number is required when more than one device is connected | upstream_code | src/ssmdevices/instruments/_minicircuits_usb.py:20-24 |

Limits: the attenuation setting is bounded to 0 to 115 dB by the upstream property declaration
(`src/ssmdevices/instruments/attenuators.py:52-54`), so the driver uses that source instead of an operator-required
bound. The device quantizes a setting to 0.25 dB because the upstream setter sends whole-decibel and quarter-decibel
bytes (`attenuators.py:79-85`).

Safety: the device has no separate stop command. The e-stop drives the attenuation setting to its maximum 115 dB,
which is the lowest RF level the attenuator can pass. The package is R1, so no independent hardware e-stop is
claimed and no safe-state action is needed.

NOT COVERED: the calibrated attenuation (`attenuation`, `attenuators.py:90-97`) and the calibrated output power
(`output_power`, `attenuators.py:99-103`), because their values derive from the calibration table and frequency
selected for the installed unit; the calibration table loading (the clone ships tables under
`src/ssmdevices/lib/cal/`) and the frequency/channel configuration (`attenuators.py:17-49`); and the other instrument
classes of the repository (the signal analyzers, the base-station emulators, the GPS simulator and the traffic
profiler). The fake is an in-memory stand-in, not a recording of a device.

Tags: attenuator, rf, usb, hid, minicircuits, rcdat
