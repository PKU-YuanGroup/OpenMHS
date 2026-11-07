# Facts and tags for gh.pymodaq/pymodaq_plugins_daqmx

Every fact cites its source at commit `f2129a920a64338b2ca3b0e06614680b30385072`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The actuator plugin declares Volts as its controller units | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daq_NIDAQmx.py:633 |
| get_NIDAQ_devices returns the system device names reported by DAQmxGetSysDevNames | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:297-311 |
| getAOMaxRate reads the maximum analog output rate from the device | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:364-368 |
| getAIMaxRate reads the maximum single-channel analog input rate from the device | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:370-374 |
| getTriggeringSources lists PFI terminals of digital-triggering devices and analog input channels of analog-triggering devices | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:388-403 |
| writeAnalog stores the written array in write_buffer and writes a single sample with WriteAnalogScalarF64 when the array holds one value | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:642-647 |
| get_last_write returns the last element of write_buffer for a scalar write | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:613-615 |
| get_last_write_index returns the task's current write position, or -1 when no task exists | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:602-611 |
| getAOVoltageRange reads the device's analog output voltage ranges and uses a constant only when the query fails | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:723-730 |
| stop stops the NI task and start starts it | upstream_code | src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:732-738 |
| The scanner documentation states that one cannot read the current voltage applied at an analog output | vendor_doc | docs/source/user_guide/scanner_details.rst:28 |
| The upstream documentation describes an analog output driving a piezoelectric scanner through an amplifier | vendor_doc | docs/source/user_guide/scanner_use.rst:4 |

Limits: the one writable parameter, `analog_output` in Volts, is `Limit.operator_required`. The clone reads the
card's output window from the device at run time and falls back to a constant only when the query fails
(`daqmx.py:723-730`), so no text file states a fixed window for an installed card. The site supplies the window of
its hardware; `site-limits.example.json` shows the overlay with example values only.

Reads: `analog_output` is the last value the driver wrote to the task buffer, not a measured output voltage. The
clone says the applied analog output voltage cannot be read back
(`docs/source/user_guide/scanner_details.rst:28`); `get_last_write` returns `write_buffer[-1]` for a scalar write
(`daqmx.py:613-615`). `last_write_index` is the task write position, or -1 without a task (`daqmx.py:602-611`).

Safety: the e-stop is the native `stop()`, which stops the NI task (`daqmx.py:732-734`). The driver does not claim
that stopping the task resets the output level, so `safe_state` states only what the native stop does. No line of
the clone documents an independent hardware e-stop, and the card's floor is R1, so `estop_physical_ref` is not set
and no safe-state action is claimed. The analog output can drive a piezoelectric scanner through an amplifier
(`docs/source/user_guide/scanner_use.rst:4`), but the clone states no high-voltage output and no motion limit, so
the package keeps the card's R1 floor and leaves the output window to the operator.

Tags: ni-daqmx, daq, analog-output, pymodaq
