# Facts and tags for gh.petoicamp/opencat-quadruped-robot

Every fact cites its source at commit `24563ca2e0218150f6299d013cd3a20c45433467`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The firmware defines 16 degrees of freedom (DOF 16) | upstream_code | src/OpenCat.h:13 |
| The sketch drives up to 16 PWM servos | upstream_code | OpenCat.ino:4 |
| The serial query token '?' prints the model name and the software version, one per line | upstream_code | src/reaction.h:91-95 |
| The firmware converts the IMU yaw, pitch and roll from radians to degrees before printing | upstream_code | src/imu.h:204-208 |
| print6Axis prints ypr[1] and ypr[2] as two tab-separated columns followed by a newline | upstream_code | src/imu.h:168-188 |
| The 'v' token prints the gyro data once | upstream_code | src/OpenCat.h:236 |
| The 'j' handler prints the current joint angles with printTable | upstream_code | src/reaction.h:173-179 |
| printTable prints the joint indices 0 to DOF-1 and then the values separated by a comma and a tab | upstream_code | src/tools.h:33-46 |
| The joint angle unit of the serial commands is degree | vendor_doc | serialMaster/README.md:71 |
| The 'd' token puts the robot down and shuts down the servos | vendor_doc | serialMaster/README.md:84-86 |
| The rest handler in the firmware calls pwm.shutServos() and the firmware then echoes the command token | upstream_code | src/reaction.h:498-512 |
| Lowercase serial commands are terminated by a newline | upstream_code | src/io.h:21 |
| The firmware echoes the command token after the reply (postures and other tokens confirm completion that way) | upstream_code | src/reaction.h:511-512 |
| The serial monitor is set to no line ending at 115200 baud | vendor_doc | README.md:149 |
| The Python API opens the serial port with Communication(p, 115200, 1) | upstream_code | serialMaster/ardSerial.py:725 |

Limits: none. The driver exposes no numeric write or invoke input, so there is nothing to bound; the reads are
telemetry in degrees and the identity strings.

Safety: the device is a mobile quadruped, so the risk is R2. The `d` rest command puts the robot down and shuts the
servos down (serialMaster/README.md:84-86, src/reaction.h:498-512). It is bound as the safe-state action
`x-cap.petoicamp.rest.v1`, and the `@estop` method sends the same command. There is no vendor text that states an
independent hardware stop, so the safe-state action is the driver's independent stop path. `cap.motion.stop.v1` does
not fit: it takes an optional deceleration input the firmware's rest command does not have, so the extension id is
used instead.

Shape: the card names the `SerialDriver` helper, but the upstream Python layer assembles the wire commands from a
token and arguments and also uses binary frames, so this package is a direct `Driver` over
`serialMaster.SerialCommunication:Communication`. This is a deviation from the card, recorded in RESULT.json.

Coverage: identity (`?`), IMU pitch/roll (`v`), current joint angles (`j`) and rest (`d`). Locomotion skills, joint
commands, calibration, the buzzer and the optional sensor pack are not covered.

This package is model-authored and unreviewed; no hardware was attached.

Tags: quadruped, robot, opencat, bittle, nybble, serial, telemetry
