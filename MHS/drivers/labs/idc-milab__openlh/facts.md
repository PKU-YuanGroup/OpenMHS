# Facts and tags for gh.idc-milab/openlh

Every fact cites its source at commit `6a7562c61656362bc70ce58b7f685090cceebda4`: `vendor_doc` (a text file of the
clone such as README.md or pyuf/doc/api/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The OpenLH is a liquid handling system based on the uArm Swift Pro robotic arm | vendor_doc | README.md:2 |
| SwiftWithUltrasonic is the API wrapper of swift and swift_pro; its defaults are dev_port=None, baud=115200, filters={'hwid': 'USB VID:PID=2341:0042'} and ultrasonic_port='D8' | upstream_code | pyuf/uf/wrapper/swift_with_ultrasonic.py:14-19 |
| get_position calls P2220 and returns an [x, y, z] float array of the arm's current location | upstream_code | pyuf/uf/wrapper/swift_api.py:248-261 |
| get_polar calls P2221 and returns an [rotation, stretch, height] float array | upstream_code | pyuf/uf/wrapper/swift_api.py:304-317 |
| The servo numbers are SERVO_BOTTOM 0, SERVO_LEFT 1, SERVO_RIGHT 2 and SERVO_HAND 3 | upstream_code | pyuf/uf/wrapper/swift_api.py:15-19 |
| get_servo_angle returns an array of float, or one float when a servo id is given, and reads P2200/P2206 | upstream_code | pyuf/uf/wrapper/swift_api.py:350-378 |
| set_servo_angle sends G202 N<servo> V<angle> and documents 0 - 180 degrees | upstream_code | pyuf/uf/wrapper/swift_api.py:319-335 |
| set_position sends G0 with X, Y, Z and F values; it documents x, y and z in mm and speed in mm/sec, and its return comment says the device returns ok even out of range | upstream_code | pyuf/uf/wrapper/swift_api.py:203-246 |
| set_pump writes the pump service value on or off and returns True when the reply starts with 'ok' | upstream_code | pyuf/uf/wrapper/swift_api.py:550-566 |
| set_gripper writes the gripper service value on or off and returns True when the reply starts with 'ok' | upstream_code | pyuf/uf/wrapper/swift_api.py:568-584 |
| get_ultrasonic calls 'get value' on the ultrasonic node and returns an int distance in cm | upstream_code | pyuf/uf/wrapper/swift_with_ultrasonic.py:91-103 |
| get_limit_switch reads P2233 and returns True for 'ok V1' and False for 'ok V0' | upstream_code | pyuf/uf/wrapper/swift_api.py:586-599 |
| get_is_moving reads M2200 and returns True for 'ok V1' and False for 'ok V0' | upstream_code | pyuf/uf/wrapper/swift_api.py:176-189 |
| The SwiftAPI class defines no motion stop, abort or halt method; its only connection-level stop is close_conn, and reset attaches the servos and moves to the default position | upstream_code | pyuf/uf/wrapper/swift_api.py:27-725 |
| The README says the arm runs a custom Marlin firmware and the OpenLH compiles Swift API calls to G-code over UART | vendor_doc | README.md:66-70 |

## Limits

The four servo angles are bounded 0 to 180 degrees by the upstream `set_servo_angle` docstring
(`pyuf/uf/wrapper/swift_api.py:321`; the API page repeats it at `pyuf/doc/api/swift_api.md:363`).

The three Cartesian workspace leaves and the speed are **not** stated by any text of the clone:
`set_position` comments that the device returns `ok` even out of range (`pyuf/uf/wrapper/swift_api.py:246`), and the
clone contains no workspace or speed range. The action therefore carries three `Limit.operator_required` leaves
(`position.x`, `position.y`, `position.z`). `site-limits.example.json` is an **example-only** overlay with arbitrary
numbers; it is not a statement about any OpenLH cell, and an operator must replace it with the travel of the actual
cell before any Cartesian move is accepted.

## Safety

`@estop` turns the pump and the gripper off. The upstream wrapper has no motion stop, abort or halt method:
`close_conn` closes the serial port (`pyuf/uf/wrapper/swift_api.py:117-119`) but cannot cancel a G-code move already
sent to the firmware, and `reset` is a motion to the default position (`pyuf/uf/wrapper/swift_api.py:121-137`). The
same tool-off routine is the safe-state action `x-cap.idc-milab.tool_off.v1`, which satisfies SAFE-045 for this R2
hardware driver. The clone documents no independent physical e-stop, so `estop_physical_ref` is not set and no
hardware e-stop is claimed.

## Tags

openlh, uarm, swift pro, liquid handling, robot arm, serial
