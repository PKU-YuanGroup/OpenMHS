# Facts and tags for gh.aics-int/microscope_automation

Every fact cites its source at commit `cdac7bdb191ea2d85965574b32ec65e3c2a7e22d`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ConnectMicroscope(connect_dll=False) loads the connect_zen_blue_dummy module and runs the class against simulated hardware | upstream_code | microscope_automation/connectors/connect_zen_blue.py:66-71 |
| snap_image stores the acquired image in self.image and uses the active experiment when experiment is None | upstream_code | microscope_automation/connectors/connect_zen_blue.py:182-190 |
| live_mode_start starts ZEN live mode and returns the live ZenImage; live_mode_stop stops it | upstream_code | microscope_automation/connectors/connect_zen_blue.py:382-439 |
| get_stage_pos returns the stage x and y position in micrometers | upstream_code | microscope_automation/connectors/connect_zen_blue.py:499-506 |
| get_objective_name returns the name of the objective in imaging position and get_objective_position returns its turret position | upstream_code | microscope_automation/connectors/connect_zen_blue.py:1037-1077 |
| get_microscope_name returns the fixed string 'get_microscope_name not implemented' | upstream_code | microscope_automation/connectors/connect_zen_blue.py:1164-1176 |
| stop() writes only the log line 'Microscope operation aborted' and sends no command | upstream_code | microscope_automation/connectors/connect_zen_blue.py:1178-1180 |
| trigger_pump starts the RS232 Braintree pump and sleeps for the requested number of seconds | upstream_code | microscope_automation/connectors/connect_zen_blue.py:1121-1156 |
| Braintree.close_connection stops the pump and closes the serial port | upstream_code | microscope_automation/hardware/RS232.py:56-66 |

## Shape and scope

The card proposes the `PythonObjectDriver` helper. The scan lists `Pump`, `Camera` and `Stage` as entry symbols, but every
method of those classes takes a ZEN COM `communication_object`; the object that owns the ZEN application and performs
the operations is `ConnectMicroscope`. This package is a direct `Driver` over that connector, which is also an
entry symbol (`microscope_automation/connectors/connect_zen_blue.py:41`). This is the deviation recorded in
`RESULT.json`.

The driver binds only observational state and live-mode/image actions:

* reads: `stage_x`, `stage_y`, `objective_name`, `objective_position`, `microscope_name`, `live`;
* actions: `x-cap.aics-int.live_mode_start.v1`, `x-cap.aics-int.snap_image.v1`, and the safe-state action
  `x-cap.aics-int.live_mode_stop.v1`.

No numeric input is taken, so the package declares no `Limit` and needs no `site-limits.example.json`. The stage
travel range, the focus travel range and the pump duration are not stated by a text file of the clone, and the
connector's `stop()` does not command hardware. For that reason the driver does not expose `move_stage_to`,
`move_focus_to`, `switch_objective` or `trigger_pump`.

## Safety

The safe state is "live acquisition stopped (ZEN live mode off)". The `@estop` method and the
`x-cap.aics-int.live_mode_stop.v1` safe-state action both call the upstream `live_mode_stop`. The clone does not
document a hardware emergency stop or an independent stop path for the stage, focus or pump, so
`estop_physical_ref` is not set and no physical protection is claimed. The driver cannot start those actuators,
so this package cannot leave them running. MHS is a software envelope, not a safety-rated channel.

The upstream `stop()` is not used as the e-stop: it only logs `Microscope operation aborted`
(`microscope_automation/connectors/connect_zen_blue.py:1178-1180`).

## Limits

None. The only inputs are optional ZEN experiment names (strings), and the driver exposes no numeric write or
invoke input.

Tags: microscope, zeiss, zen, imaging, live-mode, windows.
