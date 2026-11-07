# Facts and tags for gh.akselov/digital-twin-opcua

Every fact cites its source at commit `adc30f46466595a278f87f23a304a3630deca4da`.  `upstream_code` is code or a
comment of the clone; the ref is the path from the clone root and the line as it exists at that commit.  The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

| fact | source | ref |
|---|---|---|
| The module is a KUKAVARPROXY communication module used by opcua-server-xml.py for a KUKA KR C4 robot controller | upstream_code | xml/KUKAVARPROXY_communication.py:2-5 |
| KUKA is the module's device class and its constructor connects the module socket to TCP port 7000, where KukaVarProxy listens | upstream_code | xml/KUKAVARPROXY_communication.py:22-28 |
| The module builds the KukaVarProxy frame from a message id, a message length, a read/write byte, a variable name and an optional value | upstream_code | xml/KUKAVARPROXY_communication.py:32-59 |
| read(var) reads one KRL variable and write(var, val) writes one through the same KVP socket | upstream_code | xml/KUKAVARPROXY_communication.py:79-91 |
| The upstream reader reads $AXIS_ACT, removes the commas and splits the text on spaces, taking the value token after each axis name | upstream_code | xml/KUKAVARPROXY_communication.py:121-127 |
| The upstream control server writes TARGET_AXIS as an E6AXIS string with A1 to A6 entries | upstream_code | opcua-control/opcua-control-server.py:187 |
| The KRL program initializes TARGET_AXIS from $AXIS_ACT and then loops PTP to TARGET_AXIS | upstream_code | opcua-control/opcua_ptp_movement.src:27-31 |
| The KRL program declares a global interrupt that calls the controller's IR_STOPM when $STOPMESS is true | upstream_code | opcua-control/opcua_ptp_movement.src:9-10 |
| The upstream velocity plotter reads each axis with $VEL_AXIS_ACT [n] | upstream_code | opcua-server/opcua-server-velocity.py:198-203 |
| The upstream torque plotter reads each axis with $TORQUE_AXIS_ACT [n] | upstream_code | opcua-server/opcua-server-torque.py:198-203 |
| The upstream current plotter reads each axis with $CURR_ACT [n] | upstream_code | opcua-server/opcua-server-current.py:198-203 |
| The upstream temperature plotter reads each axis with $MOT_TEMP [n] and subtracts an offset supplied to that script | upstream_code | opcua-server/opcua-server-temperature.py:212-217 |
| The upstream error handler closes the socket and raises SystemExit on a network or parsing error; the driver converts that process-level exit into a normal failed receipt | upstream_code | xml/KUKAVARPROXY_communication.py:98-108 |
| The KUKA KR 16-2 object XML defines the six axis variables A1 to A6 and an IP property | upstream_code | xml/KUKA_KR16_2_object.xml:64-140 |

## Limits

The clone states no axis travel range, velocity, torque or current envelope.  The only numeric input, the six target
axis values of `x-cap.akselov.joint_position.v1`, is therefore `Limit.operator_required`; the runtime refuses every
move with `MHS.SAFETY.LIMITS_UNSET` until the operator's `site-limits.json` supplies the range.  The example overlay
in `site-limits.example.json` is a narrow test envelope for the fake backend, not a statement about any robot.

| capability | path | bound | source | ref |
|---|---|---|---|---|
| x-cap.akselov.joint_position.v1 | joint_positions (six native axis values) | operator_required: the clone states no travel range | | |

## Safety

The KRL program declares a global interrupt on `$STOPMESS` that calls `IR_STOPM`
(`opcua-control/opcua_ptp_movement.src:9-10`); that controller-side stop path is the independent stop declared in
`estop_physical_ref`.  The clone exposes no KVP stop variable, so the `@estop` method writes the last read axis
position to `TARGET_AXIS` (the only hold the KVP client can request) and keeps the socket open.  The KRL loop then
uses that position as its next PTP target; the running PTP finishes before the loop reads the new target.

## Units

The clone calls the six values "axis variables" and the GUI plots the system variables without a unit.  The package
publishes them in the native unit `1` and says so in every description; it does not convert them to radians or
degrees, because the clone states no conversion.

Tags: kuka, kuka kr 16-2, kr c4, kukavarproxy, kvp, robot arm, six axes
