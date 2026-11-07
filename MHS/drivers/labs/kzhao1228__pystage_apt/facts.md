# Facts and tags for gh.kzhao1228/pystage_apt

Every fact cites its source at commit `34bf8886ae996f30469338be3b02c42455ffea65`: `vendor_doc` (a text file of the
clone such as README.rst) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| pystage-apt is a library to communicate with various Thorlabs APT single-channel controllers and control different types of Thorlabs actuator motors | vendor_doc | README.rst:7 |
| MotorCtrl manipulates an APT controller channel identified by chan_ident (0x01 for a single-channel controller) | upstream_code | stage/motor_ctrl/__init__.py:9-21 |
| MotorCtrl reads the per-stage Min Pos, Max Pos, Def Min Vel, Def Max Vel, Max Accn, Max Vel and homing parameters from the MG17APTServer.ini section of the detected stage | upstream_code | stage/motor_ctrl/__init__.py:41-59 |
| set_pos refuses (prints and keeps the current position) a target outside the stage configuration Min Pos and Max Pos before sending an absolute move | upstream_code | stage/motor_ctrl/__init__.py:281-297 |
| move_by refuses (prints and sends nothing) a relative distance that would leave the stage configuration Min Pos and Max Pos | upstream_code | stage/motor_ctrl/__init__.py:398-403 |
| set_vel_params requires Def Min Vel <= min_vel < max_vel <= Max Vel and 0 < accn <= Max Accn | upstream_code | stage/motor_ctrl/__init__.py:1053-1073 |
| The stage unit index is 1 for mm and 2 for degrees; the units property returns 'mm' or the degree sign | upstream_code | stage/motor_ctrl/__init__.py:1518 |
| Homing direction 1 is forward and 2 is reverse | upstream_code | stage/motor_ctrl/__init__.py:1263-1264 |
| The homing limit switch is 4 for the forward switch and 1 for the reverse switch | upstream_code | stage/motor_ctrl/__init__.py:1277-1278 |
| set_home_params requires Def Min Vel < home_velocity < Max Vel | upstream_code | stage/motor_ctrl/__init__.py:1307 |
| MGMSG_MOT_MOVE_STOP stops any type of motor move on a channel; stop_mode 0x01 stops immediately and 0x02 stops in a controlled (profiled) manner | upstream_code | stage/ctrl_msg/motorcontrol.py:691-703 |
| The upstream serial port opens at 115200 baud, 8 data bits, no parity, one stop bit and RTS/CTS flow control | upstream_code | stage/motor_ini/port.py:40-44 |

Limits: the position, maximum velocity, acceleration and relative-distance inputs are `Limit.operator_required`.
MotorCtrl compares them with the per-stage values read from MG17APTServer.ini (`stage/motor_ctrl/__init__.py:41-59`,
`:281-285`, `:398-403`, `:1053-1073`), so the bounds belong to the stage mounted on the controller and the site
supplies them. `site-limits.example.json` is an example overlay, not a statement about any stage. The homing
direction and homing limit switch are closed sets sourced from the clone: direction 1 or 2 (lines 1263-1264) and
limit switch 4 or 1 (lines 1277-1278).

Safety: the upstream MotorCtrl has no stop method. The APT protocol message `MGMSG_MOT_MOVE_STOP` stops any type of
motor move on the channel (`stage/ctrl_msg/motorcontrol.py:691-703`); native.py wraps the upstream port with a stop()
that sends stop mode 0x01 (immediate), and the driver's `@estop` and `cap.motion.stop.v1` safe-state action both use
it. The e-stop also writes the documented default minimum velocity 0 first, through `MotorCtrl.set_min_vel`
(`stage/motor_ctrl/__init__.py:971-980`). This is an R1 hardware driver; the package does not claim the loader's
R2/R3 unreviewed-hardware refusal.

Tags: thorlabs, apt, motion, stage, serial, usb
