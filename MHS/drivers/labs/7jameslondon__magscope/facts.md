# Facts and tags for gh.7jameslondon/magscope

Every fact cites its source at commit `d8f5f6036eb418335dff18c642998a2a6cbd4e06`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PythonMicroscopeFocusMotor is a FocusMotorBase adapter for a python-microscope stage or stage axis | upstream_code | magscope/python_microscope.py:142-143 |
| The adapter requires exactly one of device, device_factory or device_uri | upstream_code | magscope/python_microscope.py:33-37 |
| connect() enables the device, resolves the configured axis and marks the motor connected | upstream_code | magscope/python_microscope.py:170-176 |
| move_absolute() divides Z by position_scale and calls the axis' move_to() in device units | upstream_code | magscope/python_microscope.py:184-188 |
| get_current_z() reads axis.position and multiplies it by position_scale | upstream_code | magscope/python_microscope.py:190-192 |
| get_position_limits() reads the axis' limits.lower and limits.upper and converts both with position_scale | upstream_code | magscope/python_microscope.py:214-220 |
| get_is_moving() reads the axis' moving/is_moving attribute or get_is_moving() method, and otherwise compares the current Z with the last commanded target using at_target_tolerance | upstream_code | magscope/python_microscope.py:194-212 |
| FocusMotorBase defines move_absolute, get_current_z, get_is_moving and get_position_limits as its abstract device methods and has no stop primitive | upstream_code | magscope/hardware.py:201-215 |
| position_scale converts python-microscope stage units into the absolute Z units MagScope uses; for example 1000.0 converts an axis that reports micrometres into nanometres | vendor_doc | docs/source/connect_hardware.rst:75 |
| MagScope Z-Lock corrections are in nanometres | vendor_doc | docs/source/user_guide.rst:787 |

Limits: the Z target is `Limit.operator_required`. No text file of the clone states a Z travel range for a stage:
the adapter reads the connected axis' own bounds at run time (`magscope/python_microscope.py:214-220`), so the site
supplies the range of its stage (`site-limits.example.json` shows the overlay; its numbers are an example only).

Safety: `@estop` commands the axis to the position it reports now (`move_absolute(get_current_z())`). The upstream
adapter has no dedicated stop call; `move_absolute` is the only motion primitive (`magscope/hardware.py:201-215`).
This is a software path through the same single motion command, not an independent hardware stop, and the package
does not claim otherwise. The risk is R1 because the catalogue class `cap.imaging.focus.v1` is R1 and a focus axis
with a site-bounded travel range is below the R2 hazards of the safety spec.

Tags: microscope, focus, z-stage, python-microscope, magscope
