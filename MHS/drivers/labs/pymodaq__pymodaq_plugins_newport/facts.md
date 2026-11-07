# Facts and tags for gh.pymodaq/pymodaq_plugins_newport

Every fact cites its source at commit `bad8a714aa079f9ae2aab95851efedc32a8505ba`: `vendor_doc` (a text file of the
clone, here `README.rst`) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone lists SMC100 as a single-axis motion controller | vendor_doc | README.rst:39 |
| SMC100 is the class for a controller device for positioners and works over USB | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:44-48 |
| Every command is prefixed with the controller's device number before it is written | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:91-94 |
| A query is prefixed with the device number and the first three characters of the reply are stripped | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:96-107 |
| move_abs sends PA followed by the position, which is in the stage's units | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:176-181 |
| move_rel sends PR followed by the distance, which is in the stage's units | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:169-174 |
| home sends PA0 and moves the device to position 0 | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:189-193 |
| homing sends OR and works only when the controller state is NOT REFERENCED | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:109-111 |
| stop sends ST to stop motion | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:201-203 |
| reset sends RS and leaves the controller in NOT REFERENCED state | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:195-199 |
| enable sends MM1 (READY) and disable sends MM0 (DISABLE) | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:120-126 |
| position queries PA? and returns the reply as a float | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:183-187 |
| speed queries VA? and is set with VA followed by the value | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:205-213 |
| acceleration queries AC? and is set with AC followed by the value | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:215-223 |
| is_moving reads the controller status with TS and compares it with 0x28 | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:134-140 |
| get_last_command_error queries TE and clears the controller's error buffer | upstream_code | src/pymodaq_plugins_newport/hardware/smc100.py:160-167 |
| The upstream plugin was tested with an SMC100PP controller and a URS150 rotation stage | vendor_doc | README.rst:68 |
| The PyMoDAQ move plugin sets the controller unit to degrees for its URS150 stage and says the unit should be changed for linear actuators | upstream_code | src/pymodaq_plugins_newport/daq_move_plugins/daq_move_Newport_SMC100.py:21-22 |
| The PyMoDAQ move plugin sets _controller_units to the degree sign for its SMC100 stage | upstream_code | src/pymodaq_plugins_newport/daq_move_plugins/daq_move_Newport_SMC100.py:39 |

Limits: the clone states no travel range for the SMC100 or for the installed stage; positions and distances are only
"in the stage's units".  The two move inputs therefore use `Limit.operator_required`, and
`site-limits.example.json` shows the operator overlay that fills them.  No speed or acceleration bound is written
either, so those values are read-only here.

Safety: the e-stop calls the upstream `SMC100.stop()`, which sends `ST`; the stop action binds the same method.  The
controller stays powered and enabled after `ST`.  At R1 no independent hardware stop is required by the SDK.

Tags: newport, smc100, motion controller, positioner, serial
