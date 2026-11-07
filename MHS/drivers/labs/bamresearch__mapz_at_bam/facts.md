# Facts and tags for gh.bamresearch/mapz_at_bam

Every fact cites its source at commit `ad4cd71528aa7d9fa1b74379dcf02266318081cb`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The package binds
one of the card's five entry symbols, the IKA RCT digital 5 hotplate class
`Minerva.Hardware.Hotplates.IkaHotplate:RCTDigital5`.

| fact | source | ref |
|---|---|---|
| The class controls an IKA RCT digital 5 hotplate over a serial COM port | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:45-52 |
| The module names the NAMUR commands: IN_NAME for the device name, IN_PV_1 and IN_PV_2 for the external and hotplate temperatures, IN_PV_4 for the stirring speed, IN_PV_5 for the viscosity trend, and IN_SP_1, IN_SP_3 and IN_SP_4 for the setpoints | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:56-64 |
| The external thermocouple temperature is reported in degrees Celsius | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:238 |
| The hotplate temperature is reported in degrees Celsius | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:259 |
| The stirring speed is reported in rpm | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:280 |
| The temperature setpoint is reported in degrees Celsius | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:322 |
| The safety temperature is reported in degrees Celsius | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:341 |
| The stirring speed setpoint is reported in rpm | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:360 |
| The comment on READ_SAFETY_TEMPERATURE_VALUE says the target/set temperature may be 50 degrees beneath the safety temperature | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:63 |
| start_heating sets the temperature setpoint first when a value is given, then sends the start-heating command | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:432-434 |
| stop_heating switches the heating off and, with its default reset_setpoint=True, sets the temperature setpoint to 0 degrees Celsius | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:445 |
| stop_stirring switches the stirring off and, with its default reset_setpoint=True, sets the stirring setpoint to 0 rpm | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:487 |
| emergency_stop sets EMERGENCY_STOP_REQUEST and calls stop_heating and stop_stirring | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:760-763 |
| Commands and responses are terminated with CR LF | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:85 |
| The constructor prefixes a port with COM when the argument does not already start with COM | upstream_code | Minerva/Hardware/Hotplates/IkaHotplate.py:109-110 |

Limits: the temperature setpoint, the stirring speed setpoint, the heating target and the stirring start speed are
`Limit.operator_required`. The clone gives units and a relation between the target temperature and the safety
temperature (50 degrees beneath it, IkaHotplate.py:63), but no absolute setpoint or stirring range, so the site
supplies its examples in `site-limits.example.json`.

Safety: the e-stop calls the upstream `emergency_stop`, which sets `EMERGENCY_STOP_REQUEST` and calls `stop_heating`
and `stop_stirring`. The safe-state action `x-cap.bamresearch.stop_hotplate.v1` calls those two stop methods, which
switch both actuators off and reset both setpoints to zero. No line of the clone documents an independent hardware
e-stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: hotplate, magnetic stirrer, temperature-control, heating, serial
