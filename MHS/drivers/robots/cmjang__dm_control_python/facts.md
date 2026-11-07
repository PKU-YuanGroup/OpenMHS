# Facts and tags for gh.cmjang/dm_control_python

Every fact cites its source at commit `7da93877ba844d9587149d6f3a6385453aa8379f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. This package
drives one motor through `DM_CAN:MotorControl`; the library can address several motors on one CAN bus, but one
package instance holds the identity of one of them (the backend options `slave_id`, `master_id`, `motor_type`).

| fact | source | ref |
|---|---|---|
| The README builds a Motor from the motor type, its Slave ID (the CAN id) and a Master ID that must be unique and not 0x00 | vendor_doc | README.md:55-62 |
| The README opens the serial adapter with 921600 baud and a 0.5 s timeout and gives the port object to MotorControl | vendor_doc | README.md:64-73 |
| The README adds a motor to the MotorControl, enables it and documents disable as the way to switch the drive off | vendor_doc | README.md:81-119 |
| A Motor object holds the last feedback in state_q, state_dq and state_tau | upstream_code | DM_CAN.py:16-20 |
| recv_data(q, dq, tau) stores one feedback frame in the motor object | upstream_code | DM_CAN.py:28-31 |
| getPosition, getVelocity and getTorque return the stored feedback | upstream_code | DM_CAN.py:33-52 |
| A new Motor object starts in MIT control mode (NowControlMode = Control_Type.MIT) | upstream_code | DM_CAN.py:25 |
| A control method finds its motor by SlaveID in motors_map and returns without a command when the motor was not added | upstream_code | DM_CAN.py:147-149 |
| addMotor stores the motor under its SlaveID and, when that is not 0, under its MasterID too | upstream_code | DM_CAN.py:317-325 |
| control_Pos_Vel sends the desired position and velocity as float32 bytes on CAN id 0x100 + SlaveID | upstream_code | DM_CAN.py:150-156 |
| control_Vel sends the desired velocity as float32 bytes on CAN id 0x200 + SlaveID | upstream_code | DM_CAN.py:169-173 |
| enable, disable and set_zero_position send 0xFC, 0xFD and 0xFE as the last byte of an eight byte data frame | upstream_code | DM_CAN.py:327-329 |
| refresh_motor_status sends the status query and reads the answer back with recv() | upstream_code | DM_CAN.py:408-416 |
| switchControlMode writes the CTRL_MODE register and returns True when the motor reports the new value | upstream_code | DM_CAN.py:361-380 |
| The CTRL_MODE register is one of the integer registers (7 to 10, 13 to 16, 35 to 36), read and written as uint32 | upstream_code | DM_CAN.py:520-528 |
| The CTRL_MODE register takes the integer range [1,4] | vendor_doc | README.md:266 |
| Control_Type maps MIT to 1, POS_VEL to 2, VEL to 3 and Torque_Pos to 4 | upstream_code | DM_CAN.py:620-624 |
| A control mode change is temporary: the motor resets it after a power cycle | vendor_doc | README.md:209 |

Limits: none of the clone's texts states a mechanical travel of the joint or a site velocity, so both motion
envelopes and the duration of a velocity command are `Limit.operator_required`. The only numbers near them are the
motor's encoder range (`Limit_Param` `12.5` rad for every motor type, DM_CAN.py:71-75) and its `MAX_SPD` register
range (README.md:245), which are firmware settings of the motor, not limits of the mechanism.

Safety: the e-stop calls the upstream `disable()`, which sends 0xFD and switches the motor drive off; the motor is
then free and the last position or velocity command no longer acts. A disabled drive is the safe state this package
declares; it is not a brake, and a vertical axis needs a mechanical brake of its own. The package is R1 (the card's
floor) and there is no hardware e-stop reference in the clone, so none is claimed.

Tags: motor, can, damiao, joint, position control, velocity control
