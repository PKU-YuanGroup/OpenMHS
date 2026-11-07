# Facts and tags for gh.prathameshnium/pica-python-instrument-control-and-automation

Every fact cites its source at commit `17ce57d76e679841379bcc13d33f77fe046f9c87`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The backend is for the Cryo-con Model 34 and its SCPI command set is shared across the Cryo-con family | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:547-551 |
| A Model 34 has four input channels, A, B, C and D | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:562 |
| Control loop 1 is the primary heater and is addressed as HEATER; loop 2 is AOUT | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:586 |
| The channel display units are K, C, F and S | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:589-594 |
| INPUT? reports in the channel's display units, not always Kelvin | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1071 |
| The suite's Cryo-con variants verify that the chosen channel is displaying Kelvin before a run starts | vendor_doc | docs/User_Manual.md:895-896 |
| set_setpoint_immediate validates 0 <= value <= 1000 in the loop's display units | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:845 |
| CONTROL activates every enabled control loop; STOP disengages all loops and disconnects the heaters | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1200-1205 |
| control_stop writes STOP | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1204-1207 |
| get_control_status queries CONTROL? and reports ON or OFF | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1209-1211 |
| set_load accepts only 50 or 25 ohm | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:946-948 |
| The loop control types are Off, PID, Man, Table and RampP | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:597-603 |
| The loop control source is one of the input channels A, B, C and D | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:562 |
| set_display_resolution accepts FULL, 1, 2 and 3 | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1225-1227 |
| The selectable display filter time constants are 0.5, 1, 2, 4, 8, 16, 32 and 64 | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:613 |
| set_display_time_constant sets the display filter time constant in seconds | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1239-1240 |
| set_input_name sets a custom name of at most 15 characters | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1129 |
| set_factory_sensor_index accepts an index >= 0 and 0 disables the curve | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1103-1106 |
| reset sends *RST, a ~15 s hardware reset to power-up defaults; this driver does not expose it | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1272-1275 |
| disconnect only closes the VISA resource; it sends no *RST, no STOP and no loop, heater or setpoint change | upstream_code | pica/cryocon/T_Control_CC34_DirectControl_GUI.py:551-556 |
| The manual's example address for a Cryo-con 34 is GPIB1::23::INSTR | vendor_doc | docs/User_Manual.md:958 |

## Limits

- `setpoint` (K), `max_power` (%), `max_setpoint` (K), `manual_power` (%) and `factory_sensor_index` are
  `Limit.operator_required`.  The clone validates the controller's own envelope (0 to 1000 in display units for a
  setpoint, 0 to 100 percent of full scale for power, and an index >= 0), but not the safe setpoint, heater power or
  installed sensor curve of a particular cryostat.  The site supplies those bounds; without an overlay every write is
  refused with `MHS.SAFETY.LIMITS_UNSET`.  `site-limits.example.json` is an example, not a statement about any unit.
- `loop_type` is restricted to Off, PID, Man, Table and RampP; `loop_source` to A, B, C and D;
  `display_time_constant` to 0.5, 1, 2, 4, 8, 16, 32 and 64 seconds; `load` to 25 or 50 ohm.  Those sets are cited
  in the table above.  Display resolution, input name, keypad lockout and factory sensor index are read-only in this
  package.

## Units and safety

- The controller reports temperature and setpoint in the display unit of the source channel.  The driver publishes
  kelvin and refuses a controller whose channel A or loop 1 source is not displaying K; it does not guess a conversion.
- The native stop is `control_stop()` (SCPI STOP): it disengages every control loop and disconnects the heaters
  (line 1205).  It is the `@estop` method and the safe-state action `x-cap.prathameshnium.control_stop.v1`.
- `control_engage` is the native CONTROL command (line 1200).  It engages the loops at the already configured
  setpoint; the setpoint write itself does not engage them.
- `reset` (`*RST`) is deliberately not exposed: it is a ~15 s hardware reset to power-up defaults (line 1273).

Tags: cryocon, temperature-controller, cryostat, gpib, direct-control
