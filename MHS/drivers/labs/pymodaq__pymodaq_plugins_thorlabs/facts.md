# Facts and tags for gh.pymodaq/pymodaq_plugins_thorlabs

Every fact cites its source at commit `4aaf06acf6ea46b93fb900b76701f077dee44e28`: `vendor_doc` for text of the
clone (here `README.rst`) or `upstream_code` for code of the clone. The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The Kinesis wrapper loads the Thorlabs Kinesis .NET assemblies through pythonnet and appends 'C:\Program Files\Thorlabs\Kinesis' to sys.path | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:1-13 |
| The module builds the device list at import and filters the connected serial numbers by device prefix | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:40-52 |
| Kinesis.connect connects the device, waits up to 5000 ms for settings initialization and starts polling every 250 ms | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:61-64 |
| Kinesis.close stops polling, disconnects and disposes the device | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:66-73 |
| Kinesis.stop calls Stop(0) on the device | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:91-92 |
| Kinesis.move_abs converts the position to System.Decimal and calls MoveTo with a callback (or 0); home calls Home with the same callback handling | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:97-116 |
| is_homed, is_moving and is_homing read the IsHomed, IsInMotion and IsHoming flags of the device Status | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:118-128 |
| get_target_position returns the device Position converted from System.Decimal to float | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:133-134 |
| get_units returns the unit converter's RealUnits, or default_units when reading it fails | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:136-144 |
| BrushlessDCMotor.connect accepts a serial number from the controller's device list and init_channel creates and connects a BrushlessMotorChannel | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:224-233 |
| BrushlessDCMotor forwards get_position, move_abs, home, is_homed, stop, get_units and get_target_position to the channel selected by channel index | upstream_code | src/pymodaq_plugins_thorlabs/hardware/kinesis.py:235-275 |
| The PyMoDAQ BrushlessDCMotor plugin reads the position with get_position(axis) and the unit with get_units(axis) | upstream_code | src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:58-68 |
| The PyMoDAQ plugin maps the axis names '1', '2' and '3' to controller channel indices 1, 2 and 3 | upstream_code | src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:27-28 |
| The PyMoDAQ plugin applies its user-configured bounds with check_bound before an absolute move; the bound is a PyMoDAQ setting, not a controller limit | upstream_code | src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:121-133 |
| The PyMoDAQ plugin implements a relative move by adding the offset to the current position and calling the controller's absolute move | upstream_code | src/pymodaq_plugins_thorlabs/daq_move_plugins/daq_move_BrushlessDCMotor.py:135-147 |
| The README describes the BrushlessDCMotor plugin as Kinesis control of a DC brushless motor tested with the BBD201 controller | vendor_doc | README.rst:44 |
| The package declares pythonnet and pywin32 as dependencies | upstream_code | pyproject.toml:16-17 |

Limits: the absolute target and the relative offset are in the controller position unit reported by the `units`
read, not a converted physical unit. No text file of the clone states the travel range of the stage attached to the
controller: the PyMoDAQ plugin keeps the bounds in its own settings and applies them with `check_bound` before a move
(`daq_move_BrushlessDCMotor.py:121-133`). Both inputs are therefore `Limit.operator_required`: every move is refused
`MHS.SAFETY.LIMITS_UNSET` until the operator's site overlay supplies the travel of the installed stage in controller
units. `site-limits.example.json` shows the overlay shape with example values only.

Safety: the e-stop and the `x-cap.pymodaq.thorlabs_stop.v1` action both call `BrushlessDCMotor.stop(channel)`, which
forwards to the channel and calls `Stop(0)` (`kinesis.py:260-263`, `91-92`). The catalogue's `cap.motion.stop.v1` is
not bound: its optional `deceleration` input (m/s2) has no argument in the Kinesis stop call, so accepting it would
mean ignoring a requested profile; the extension stop action declares no profile. No text file of the clone documents
an independent hardware e-stop, so `estop_physical_ref` is not set; the driver is R1, and the independent stop of
SAFE-045 is required only at R2 and R3. `safe_state` is no commanded motion on the bound channel. The package is
model-authored and unreviewed, no human review or test is claimed, and no hardware was attached.

What the package does not cover: the hardware path (`native.py`, the Kinesis .NET import, the real serial number and
the controller's asynchronous move completion) was never run. The fake is an in-memory object, not a recording. The
driver binds one controller channel and exposes no stage-configuration write (`BrushlessMotorChannel.set_property`
is not bound): the stage axis parameters have no unit and no range in the clone, and the position/offset inputs wait
for the operator's overlay. The unit string comes from the controller at run time; the fake's `mm` is a placeholder,
not a device fact.

Tags: thorlabs, kinesis, brushless, motor, stage, motion
