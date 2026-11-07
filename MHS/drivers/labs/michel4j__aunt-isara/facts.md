# Facts and tags for gh.michel4j/aunt-isara

Every fact cites its source at commit `f95cff5e6cec38e0b9945ae5673251fa5d11466f`: `upstream_code` is a line of the
clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver,
not from this page.

| fact | source | ref |
|---|---|---|
| AuntISARAApp builds the AuntISARA process-variable model in self.ioc and connects the command and status clients to the controller | upstream_code | auntisara/ioc.py:561-585 |
| The controller status and action are the STATUS and ACTION process variables | upstream_code | auntisara/ioc.py:210-211 |
| ActionType bits are MOUNT, DISMOUNT, PREFETCH and ABORTING | upstream_code | auntisara/ioc.py:172-178 |
| StatusType values are IDLE, WAITING, BUSY, STANDBY and FAULT (0 to 4) | upstream_code | auntisara/msgs.py:5-6 |
| The emergency input is INP:emerg and the collision sensor input is INP:colSensor | upstream_code | auntisara/ioc.py:225-226 |
| position_fbk is STATE:pos, tool_fbk is STATE:tool and the mounted sample is STATE:onDiff | upstream_code | auntisara/ioc.py:241-277 |
| lid_fbk is STATE:lidOpen (0 CLOSED, 1 OPEN) | upstream_code | auntisara/ioc.py:261 |
| dewar_temp1_fbk and dewar_temp2_fbk are STATE:dewarT1 and STATE:dewarT2 | upstream_code | auntisara/ioc.py:280-281 |
| next_port is PAR:nextPort; tool_param, puck_param and sample_param are PAR:tool, PAR:puck and PAR:smpl | upstream_code | auntisara/ioc.py:285-289 |
| do_next_port validates a port and stores it in next_port, or empties it | upstream_code | auntisara/ioc.py:2069-2073 |
| A puck port is a PUCK_LIST prefix and a pin 1 to 16; PUCK_LIST holds 29 prefixes and NUM_PUCK_SAMPLES is 16 | upstream_code | auntisara/ioc.py:34-44 |
| PORT_PATT accepts a puck prefix and a pin 1 to 16 | upstream_code | auntisara/ioc.py:52 |
| send_command queues a command and formats arguments as command(arg,arg) | upstream_code | auntisara/ioc.py:968-978 |
| set_mount_params converts a port with port2args and writes tool_param, puck_param and sample_param | upstream_code | auntisara/ioc.py:1160-1170 |
| port2args converts a port such as 1A16 to puck, sample and tool for a UNIPUCK or DOUBLE tool | upstream_code | auntisara/ioc.py:356-369 |
| do_panic_cmd sends the native panic command | upstream_code | auntisara/ioc.py:1753-1755 |
| do_home_cmd sends the native home command with the current tool | upstream_code | auntisara/ioc.py:1821-1823 |
| abort_to_home sends abort, reset and safe and waits for HOME and IDLE | upstream_code | auntisara/ioc.py:1179-1190 |
| is_idle compares the controller status with StatusType.IDLE | upstream_code | auntisara/ioc.py:1665-1669 |

Limit: none. The clone gives the controller's own PV bounds (for example the speed PV is 0 to 100 %), but the
driver exposes no numeric write or invoke input, so no site bound is needed and `site-limits.example.json` is absent.
The dewar temperatures are published without a unit in the clone, so the reads carry no unit. The mount-port input is
validated by a pattern that spells out the 29 `PUCK_LIST` prefixes and the pin range 1 to 16.

Safety: `@estop stop` and the safe-state action `cap.motion.stop.v1` (`stop_all_motion`) both queue the native
`panic` command (`auntisara/ioc.py:1753-1755`). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver. The controller
emergency input `INP:emerg` and collision sensor `INP:colSensor` stay independent inputs of the controller.

The fake starts from placeholders (status 0 IDLE, position SOAK, tool 4 DOUBLE, dewar temperatures -185.0 and
-180.0, and so on). They are test data, not facts about any ISARA unit.

Tags: sample-handler, automounter, robot-arm, cryo, dewar
