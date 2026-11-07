# Facts and tags for gh.thedeanlab/navigate

Every fact cites its source at commit `da14920d7b40d048a5d2225a7846d11f78e05212`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MS2000Stage maps the software axes x, y and z to the controller axes X, Y and Z by default | upstream_code | src/navigate/model/devices/stage/asi.py:656-662 |
| get_axis_position asks the controller for the axis position in micrometres (get_axis_position_um) and returns inf when the axis has no mapping | upstream_code | src/navigate/model/devices/stage/asi.py:224-232 |
| The stage holds its axis positions in microns (x_pos, y_pos, ...; 'All units are in microns') | upstream_code | src/navigate/model/devices/stage/base.py:146-149 |
| The per-axis travel bounds x_min and x_max are read from the microscope stage configuration | upstream_code | src/navigate/model/devices/stage/base.py:150-158 |
| move_axis_absolute sends the target multiplied by 10 because the ASI controller unit is 1/10 micrometre | upstream_code | src/navigate/model/devices/stage/asi.py:288-293 |
| move_absolute takes positions in micrometres for the ASI API | upstream_code | src/navigate/model/devices/stage/asi.py:335-345 |
| stop() sends the controller stop command and aborts all stage movement | upstream_code | src/navigate/model/devices/stage/asi.py:380-383 |
| stop_scan() sends the controller scan stop command | upstream_code | src/navigate/model/devices/stage/asi.py:580-584 |
| connect() opens the Tiger controller over serial for the stage | upstream_code | src/navigate/model/devices/stage/asi.py:723-746 |

Limits: the travel range of the axes is `Limit.operator_required`. The stage class reads `x_min`/`x_max` from the
microscope configuration (stage/base.py:150-158), which is a property of one bench, and no text file of the clone
states a travel bound for the MS-2000; the site supplies it (`site-limits.example.json` shows the overlay).

Safety: the e-stop is the native `stop()` (stage/asi.py:380-383), which sends the controller stop command and aborts
all stage movement. The clone names no independent hardware e-stop, and this is an R1 driver, so `estop_physical_ref`
is not set and no safe-state action is declared.

Scope: the clone is a light-sheet microscope control framework (README.md:1-13); the card lists five entry symbols.
This package implements only the first one, `navigate.model.devices.stage.asi:MS2000Stage`. The others
(`MFC2000Stage` in the same file, `navigate.model.devices.pump.tecan:XCaliburPump`,
`navigate.model.devices.APIs.omicron.LuxxLaser:LuxxLaser` and
`navigate.model.devices.camera.synthetic:SyntheticCamera`) are other devices of the framework and are not covered.
The array output of the camera is not covered by this package either, because it is a different device class.

Tags: stage, microscope, motion, serial, asi
