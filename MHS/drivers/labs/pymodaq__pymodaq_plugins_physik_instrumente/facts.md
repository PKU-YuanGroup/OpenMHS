# Facts and tags for gh.pymodaq/pymodaq_plugins_physik_instrumente

Every fact cites its source at commit `6fb8d954c432eac431e87c511a70e82c7b4df5f8`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PIWrapper wraps a pipython GCSDevice and its docstring lists the GCS2 controller families it supports | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:29-48 |
| PIWrapper.identify() returns the controller identity from GCSDevice.qIDN() | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:80-82 |
| PIWrapper.axis_names returns the controller's axes from GCSDevice.axes | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:84-87 |
| PIWrapper.get_axis_units() queries parameter 0x07000601 for every axis, returns the reported unit and falls back to the default 'mm' when the controller rejects qSPA | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:89-115 |
| PIWrapper.get_servo() reads the closed-loop state of an axis with qSVO | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:147-149 |
| PIWrapper.set_referencing() sends RON and FRF only for an axis that is already referenced | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:164-180 |
| PIWrapper.get_axis_limits() reads qTMN and qTMX for the axis and returns NaN when the command is not available | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:182-202 |
| PIWrapper.connect_device() connects over USB, TCP/IP or RS232 and opens an RS232 line at 19200 baud | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:233-244 |
| PIWrapper.is_referenced() reads the referenced state with qFRF when the device has it | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:261-276 |
| PIWrapper.stop() sends StopAll to the controller | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:278-280 |
| PIWrapper.get_axis_position() reads the position of the axis with qPOS | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:282-289 |
| PIWrapper.move_absolute() sends MOV with the axis name and the position | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:291-299 |
| PIWrapper.move_relative() sends MVR with the axis name and the position when the controller has MVR | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:301-310 |
| PIWrapper.move_home() calls set_referencing(), then GOH or FRF, and falls back to an absolute move to 0 | upstream_code | src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py:312-329 |
| The DAQ_Move_PI plugin declares um as its default controller unit | upstream_code | src/pymodaq_plugins_physik_instrumente/daq_move_plugins/daq_move_PI.py:42 |
| The DAQ_Move_PI plugin reads axis_names and get_axis_units from the wrapper at initialization | upstream_code | src/pymodaq_plugins_physik_instrumente/daq_move_plugins/daq_move_PI.py:109-110 |
| The DAQ_Move_PI plugin stops the controller with controller.stop() in stop_motion() | upstream_code | src/pymodaq_plugins_physik_instrumente/daq_move_plugins/daq_move_PI.py:136-141 |
| The README states that the PI actuator plugin covers all stages compatible with the GCS2 library and was tested on E-816, C-863, C-663 and E-545 | vendor_doc | README.rst:30-31 |

Limits: no text file of the clone states the travel range of an axis. `PIWrapper.get_axis_limits` queries the
controller's own qTMN/qTMX values at run time (pi_wrapper.py:182-202), and the same wrapper drives any GCS2 stage
(README.rst:30-31), so a fixed range would be a statement about one stage, not about the controller. Both move
inputs are therefore `Limit.operator_required`; `site-limits.example.json` shows the overlay that fills them. The
manuals under `docs/` are PDFs and were not cited because no page was read.

Safety: the e-stop and the safe-state action `x-cap.pymodaq.pi_stop_motion.v1` both call the native `stop()`, which
sends `StopAll` (pi_wrapper.py:278-280). The stop capability is an extension because the native stop takes no
deceleration profile and reports no stopped position, while `cap.motion.stop.v1` carries both. The clone documents no
independent hardware e-stop line in a text file, so `estop_physical_ref` is not set. The package risk is R1, matching
the card's floor; the catalogue motion classes that bind a motion axis are R1, and the clone states no voltage, force
or speed bound. This package is model-authored and unreviewed; nothing here ran on hardware.

The fake's axis names, units, positions, limits and identity are in-memory placeholders marked `# placeholder` in
`fake.py`; they are not facts and are not copied into a Fact or a Limit.

Tags: motion, stage, actuator, piezo, pi, gcs2
