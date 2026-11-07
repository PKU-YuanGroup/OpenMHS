# Facts and tags for gh.pyepics/newportxps

Every fact cites its source at commit `5ee41fced858f2db7edec1f75d2de52f144c51e4`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The constructor creates the low-level XPS client, calls connect, and keeps the group and stage dictionaries the controller reports | upstream_code | newportxps/newportxps.py:53-84 |
| connect opens a TCP connection with TCP_ConnectToServer, logs in, reads the firmware version and calls read_systemini | upstream_code | newportxps/newportxps.py:138-160 |
| read_systemini reads the group and stage names from system.ini and then reads each stage's maximum velocity/acceleration and user travel limits from the controller | upstream_code | newportxps/newportxps.py:204-256 |
| get_stage_position calls GroupPositionCurrentGet for one element and returns the value | upstream_code | newportxps/newportxps.py:752-767 |
| move_stage sends GroupMoveAbsolute, or GroupMoveRelative when relative is true, with the value in a one-element list | upstream_code | newportxps/newportxps.py:731-750 |
| get_group_status returns the GroupStatusStringGet text for every group | upstream_code | newportxps/newportxps.py:612-626 |
| get_hardware_status returns the PositionerHardwareStatusStringGet text for every stage | upstream_code | newportxps/newportxps.py:628-643 |
| get_positioner_errors returns the PositionerErrorStringGet text for every stage, and 'OK' when the text is empty | upstream_code | newportxps/newportxps.py:645-663 |
| get_tuning returns a dictionary of the twelve PID and feed-forward parameters of a stage | upstream_code | newportxps/newportxps.py:422-442 |
| home_group runs GroupHomeSearch, initializing the group first when its status says it is not initialized | upstream_code | newportxps/newportxps.py:570-586 |
| enable_group calls GroupMotionEnable and disable_group calls GroupMotionDisable | upstream_code | newportxps/newportxps.py:588-610 |
| abort_group calls GroupMoveAbort for the given group, or for the trajectory group when no group is given | upstream_code | newportxps/newportxps.py:685-693 |
| The low-level XPS transport sets a 3600 s socket timeout before each command | upstream_code | newportxps/XPS_C8_drivers.py:90-94 |
| The README lists moving stages and groups, homing, setting stage velocity, running trajectories and reading the gathering file among the supported operations | vendor_doc | README.md:71-86 |

## Binding, units and limits

The endpoint drives one stage of one group. The backend options `stage` and `group` select it; with no option the
driver takes the first stage the controller reports and the group part of its name (the upstream example stage names
are `<group>.<positioner>`, README.md:26-35, 55-56). The stage name is a controller configuration value, not a device
bound.

The clone never names a physical unit for a stage position: `read_systemini` asks the controller for
`PositionerUserTravelLimitsGet` and stores the two returned numbers as `low_limit` and `high_limit`
(newportxps/newportxps.py:250-253), and the XPS API takes positions in bare user units. Whether a stage is linear
(mm) or rotary (deg) depends on the installed stage, so the driver reports positions with the UCUM unit `1`
(dimensionless user units) and says so in the descriptions. The travel range is read at connection time from the
controller, so it cannot be a static `Limit`: both move inputs are `Limit.operator_required`. Every move is refused
`MHS.SAFETY.LIMITS_UNSET` until the operator's `site-limits.json` supplies the range of the installed stage in user
units. `site-limits.example.json` shows the shape with example bounds only; it is not a specification of any stage.

## Safety

The `@estop` calls the native `abort_group` for the bound group and then `disable_group` for it
(newportxps/newportxps.py:685-693, 600-610); the safe state is that no move is commanded on the bound group. The
`x-cap.pyepics.abort_group.v1` action calls the same native `abort_group`. The catalogue's `cap.motion.stop.v1` is not
bound: its optional `deceleration` input is in m/s2 and the XPS `GroupMoveAbort` call takes no profile, so accepting it
would mean ignoring a requested stop profile. No text file of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the driver is R1, and the independent-stop rule (SAFE-045) is required only at R2 and
R3.

The low-level transport sets a 3600 s socket timeout on every command (newportxps/XPS_C8_drivers.py:90-94). The e-stop
does not wait for the running action, but a lost network path can still block the native abort call for a long time; a
hardware deployment must supervise the link. The package is model-authored and unreviewed
(`driver.lock.json` `reviewed_by` is null), and no hardware was attached.

Tags: motion, positioner, stage, newport, xps
