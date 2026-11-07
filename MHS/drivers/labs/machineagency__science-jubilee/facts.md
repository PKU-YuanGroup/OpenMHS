# Facts and tags for gh.machineagency/science-jubilee

Every fact cites its source at commit `bb918fa78f300f57cc379a80731cfca7bdb55c66` (`upstream_code`, a code line of the
clone, or `vendor_doc`, a text file of the clone). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Machine.gcode() posts each G-code command to http://{address}/machine/code | upstream_code | src/science_jubilee/Machine.py:491-494 |
| get_position() asks the Duet for M114 and returns the machine control point in mm keyed by axis | upstream_code | src/science_jubilee/Machine.py:1042-1070 |
| move_to() selects absolute positioning and calls _move_xyzev with x, y, z, e, v and the speed s | upstream_code | src/science_jubilee/Machine.py:801-830 |
| _move_xyzev formats each coordinate with two decimals and sends a G0 command; wait=True follows with M400 | upstream_code | src/science_jubilee/Machine.py:771-799 |
| set_tool_offset() requires a tool index, formats each offset with two decimals and sends a G10 command | upstream_code | src/science_jubilee/Machine.py:721-741 |
| home_all() parks the active tool when one is selected, sends G28 and marks X, Y, Z and U homed | upstream_code | src/science_jubilee/Machine.py:652-663 |
| home_z() asks the operator to confirm that the deck is free before sending G28 Z | upstream_code | src/science_jubilee/Machine.py:697-706 |
| The axis travel range is read from the Duet object model M409 move.axes as a min/max pair per axis | upstream_code | src/science_jubilee/Machine.py:397-426 |
| Jubilee has four axes by default: the X, Y and Z dimensional axes and the toolchanger U axis | vendor_doc | docs/getting_started/primer.md:24 |
| By default the machine uses millimetres | vendor_doc | docs/getting_started/primer.md:12 |
| The demo machine configuration sets software axis limits M208 X-13.75:313.75 Y-44:341 Z0:300 and M208 U0:200 | vendor_doc | docs/gcode/color_mixing_demo_config.g:132-133 |
| Tool offsets shift the usable coordinate range: a tool with a Z offset of 50 moves from Z-50 to Z250 while the firmware keeps motion inside the 300x300x300 mm build volume | vendor_doc | docs/getting_started/primer.md:72 |
| The clone documents the tool-ball crash trigger as an emergency stop that disables the steppers and resets the board, the same as the M112 G-code | vendor_doc | docs/building/tool_crash_detection.md:73 |

## Limits

The clone states no universal travel envelope: `Machine.axis_limits` reads the M409 `move.axes` min/max from the
machine's own configuration (`src/science_jubilee/Machine.py:397-426`), and the primer notes that tool offsets shift
the usable coordinates (`docs/getting_started/primer.md:72`). The demo configuration
(`docs/gcode/color_mixing_demo_config.g:132-133`) is one machine's M208 setting, not a bound of every Jubilee.
Therefore the X/Y/Z target-position limits and the tool-offset limits are `Limit.operator_required`: every move and
tool-offset write is refused `MHS.SAFETY.LIMITS_UNSET` until the site supplies its working envelope.
`site-limits.example.json` is an example overlay based on the demo configuration (X -13.75 to 313.75, Y -44 to 341,
Z 0 to 300; tools P0 to P3; the nominal tool offsets at lines 150, 163 and 171); it is not a statement about any
machine and the operator replaces it with the site's own numbers.

The U axis is the toolchanger lock axis (`docs/getting_started/primer.md:24`). The driver does not expose a U read or
a U move; `home` can home U individually, while Z is homed only by the all-axes routine because `home_z()` waits for
an operator answer on stdin (`src/science_jubilee/Machine.py:697-706`) and a server method must not prompt.

## Safety

Risk R2: the platform moves a tool carriage in three dimensions at high speed. `stop()` is the native stop and sends
the Duet `M112` emergency stop, which the clone describes as disabling the steppers and resetting the board
(`docs/building/tool_crash_detection.md:73`). The same paragraph documents the independent hardware stop: a tool-ball
trigger wired to the Duet and configured as an emergency stop (`estop_physical_ref`). This is a software mirror of a
device stop, not a safety-rated function.

## Tags

jubilee, motion, gantry, tool changer, gcode, duet
