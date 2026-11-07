# Facts and tags for gh.pymodaq/pymodaq_plugins_smaract

Every fact cites a line of the clone at commit `eeb3fa8ced4ce9eab102951a4ad482ee4152fe6c`. The same facts are written
into `driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this
page.

| fact | source | ref |
|---|---|---|
| The wrapper's API is the SmarAct MCS2 Programmers Guide and the channel configuration (sensor type) is done beforehand with the SmarAct MCS2ServiceTool software | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:40-45 |
| The base unit of a channel is generally a picometer for a linear positioner and a nanodegree for a rotary one | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:48-49 |
| get_position reads the POSITION property of the channel and returns an int in base units; its docstring also describes the value as picometers | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:124-145 |
| get_units returns the POS_BASE_UNIT enum name in lower case, or None when the base unit is BaseUnit.NONE | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:102-111 |
| get_base_resolution returns the POS_BASE_RESOLUTION property as an integer exponent | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:113-122 |
| get_positionner_type returns the POSITIONER_TYPE_NAME property of the channel | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:96-100 |
| get_number_of_channels returns the controller's NUMBER_OF_CHANNELS; the docstring says it is not the number of connected positioners | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:83-94 |
| absolute_move sets MOVE_MODE to CL_ABSOLUTE and calls Move with the value in base units | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:162-178 |
| relative_move sets MOVE_MODE to CL_RELATIVE and calls Move with the value in base units | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:180-197 |
| absolute_move and relative_move abort the movement without notice when a mechanical end stop is detected | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:163-167 |
| find_reference starts the reference search in the forward direction and resets the position to zero if the configuration says so | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:147-160 |
| stop calls Stop for the channel and also stops the hold position feature of closed-loop commands | upstream_code | src/pymodaq_plugins_smaract/hardware/mcs2/MCS2_wrapper.py:200-208 |
| The PyMoDAQ plugin converts a controller position to the plugin unit as 10**base_resolution times the position | upstream_code | src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS2.py:60-62 |
| The PyMoDAQ plugin applies the user-configured bounds with check_bound before an absolute move; the bound is a PyMoDAQ setting, not a controller limit | upstream_code | src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS2.py:135 |
| The MCS1 plugin's -61500 to 61500 um bounds correspond to one positioner, the SLC-24180 | upstream_code | src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS1.py:24-26 |
| The MCS1 plugin comments that the minimum and maximum bounds depend on which positioner is plugged | upstream_code | src/pymodaq_plugins_smaract/daq_move_plugins/daq_move_SmarActMCS1.py:63-64 |

Limits: the absolute position and the relative offset are in controller base units. No text file of the clone states
the travel range of a positioner attached to an MCS2 controller: `MCS2_wrapper.py` says the base unit and base
resolution depend on the configured positioner, and the only numbers in the clone are the MCS1 plugin's
-61500 to 61500 um for one SLC-24180, with a comment that the bounds depend on the positioner that is plugged. Both
inputs are therefore `Limit.operator_required` in base units: every move is refused `MHS.SAFETY.LIMITS_UNSET` until
the operator's site overlay supplies the range of the installed positioner. `site-limits.example.json` shows the
overlay shape with example bounds only.

Safety: the e-stop and the `x-cap.pymodaq.smaract_stop.v1` action both call the native `stop(channel)`
(`MCS2_wrapper.py:200-208`), which stops the movement and the closed-loop hold. The catalogue's
`cap.motion.stop.v1` is not bound: its optional `deceleration` input (m/s2) has no argument in the MCS2 `Stop` call,
so accepting it would mean ignoring a requested stop profile; the extension stop action declares no profile. No text
file of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set; the driver is R1, and
SAFE-045's independent stop is required only at R2 and R3. `safe_state` is no commanded motion on the bound channel.
The package is model-authored and unreviewed, and no hardware was attached.

Tags: positioner, motion, piezo, mcs2, smaract
