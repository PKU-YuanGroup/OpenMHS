# Facts and tags for gh.boston-dynamics/spot-sdk

Every fact cites its source at commit `04537ddafe0641d1751af3eb9e76cb785fc18594`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The quickstart tells the operator to push the E-Stop button and watch the robot do a glide-stop | vendor_doc | docs/python/quickstart.md:379 |
| The E-Stop service is a heartbeat-based software service; its stop levels are CUT (actuator power is cut immediately), SETTLE_THEN_CUT (the robot stops, sits down, then cuts actuator power) and NONE | vendor_doc | docs/concepts/estop_service.md:11-19 |
| The robot can have software and hardware E-Stops at the same time, and if any one E-Stop is activated the robot cannot power on its actuators | vendor_doc | docs/concepts/robot_services.md:65 |
| Abruptly turning off motor power causes the robot to drop, so clients are encouraged to use SETTLE_THEN_CUT or SafePowerOffCommand; the safe power off sits the robot down before cutting motor power | vendor_doc | docs/concepts/robot_services.md:34-45 |
| Robot.power_on blocks until the robot powers on | upstream_code | python/bosdyn-client/src/bosdyn/client/robot.py:625-626 |
| Robot.power_off(cut_immediately=True) cuts power immediately; cut_immediately=False issues a safe power off command | upstream_code | python/bosdyn-client/src/bosdyn/client/robot.py:642-648 |
| Robot.get_cached_robot_id returns the RobotId proto, querying it from the robot if it is not cached | upstream_code | python/bosdyn-client/src/bosdyn/client/robot.py:300-309 |
| Robot.get_cached_hardware_hardware_configuration returns the cached HardwareConfiguration proto | upstream_code | python/bosdyn-client/src/bosdyn/client/robot.py:311-320 |
| Robot.get_cached_usernames returns the sorted usernames matching the serial number in the token cache | upstream_code | python/bosdyn-client/src/bosdyn/client/robot.py:476-484 |
| Robot.get_frame_tree_snapshot returns the kinematic state's transforms_snapshot | upstream_code | python/bosdyn-client/src/bosdyn/client/robot.py:704-719 |
| HardwareConfiguration.redundant_safety_stop_enabled says the robot is configured with a redundant safety stop | upstream_code | protos/bosdyn/api/robot_state.proto:63 |
| RobotId carries serial_number, species and nickname fields | upstream_code | protos/bosdyn/api/robot_id.proto:21-33 |

Limits: this driver declares none. Its only write is the boolean `motors_on`; the reads are identity and telemetry
values and carry no numeric bounds. No catalogue class bound was narrowed or invented.

Safety: the native stop is `Robot.power_off(cut_immediately=True)` (`@estop(native="power_off")`), which cuts motor
power immediately. The independent hardware stop is the physical E-Stop button documented by the quickstart
(`estop_physical_ref`, docs/python/quickstart.md:379) and satisfies SAFE-045 for this R2 hardware driver. The software
E-Stop service is a heartbeat service (`docs/concepts/estop_service.md:11-19`) and is not presented as a hardware
stop. The `motors_on` write uses `cut_immediately=False` for a nominal power-off, which the documentation says sits
the robot down first (`docs/concepts/robot_services.md:45`). No safe-state action is declared, so `safe_state` names
the immediate power cut rather than a stand or sit behaviour.

Tags: mobile robot, quadruped, spot, boston dynamics, motor power, robot state, e-stop.
