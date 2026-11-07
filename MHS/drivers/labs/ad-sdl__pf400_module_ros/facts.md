OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.ad-sdl/pf400_module_ros

Every fact cites the pinned clone at commit `dad325c4bf86efda3b81f98d33837ec5ce21fc0c`. The TCP command server
files live under `resources/original_tcp_code/Tcp_cmd_server_3_0_c1_INSTALLATION/Tcp_cmd_server/` (not the `Tcp_cmd_server_pa`
tree). The same facts are in the package's `driver.py` (`facts = [...]`); the reference file is generated from it.

Tags: `pf400`, `arm`, `tcp`, `tcs`, `cobot`.

Author: Grok (grok-4.7, a model and not a human), 2026-11-05, authoring the package the blocked card left
without a driver (user decision of 2026-11-05: Grok authors, Codex reviews). Model-written; `reviewed_by` is null.

## Facts

| fact | source | ref |
|---|---|---|
| Startup declares Status1Port 10000 and Robot1Port 10100. StartMain opens the status port with TcpComMain(0, Status1Port) and TcpCom1 opens the robot port with TcpComMain(1, Robot1Port). The startup comment says a motion thread can block and the status thread does not. | upstream_code | Startup.gpl:42-157 |
| The status thread is robot 0 with IsStatus set, and after AcceptSocket it stops listening so the port serves one client. | upstream_code | Main.gpl:59-90 |
| NewRobNum is applied at the start of the next receive, before that receive's bytes are read. | upstream_code | Main.gpl:98-123 |
| A status command runs in the comm thread; a robot-port command is posted to the robot mailbox and the comm thread waits until the mailbox is clear. | upstream_code | Main.gpl:199-210 |
| After Handler returns, the robot thread sets the mailbox to Nothing and wakes the comm thread. | upstream_code | Main.gpl:603-607 |
| PC mode's default reply is 0. | upstream_code | Class_command.gpl:280 |
| The client states that a response begins with 0 when the command was successful, or a negative error code. | upstream_code | pf400_driver/pf400_driver/tcp_driver.py:23 |
| The PC-mode reply on the socket is Cmd.Reply followed by CR LF. | upstream_code | Main.gpl:225 |
| halt calls Robot.RapidDecel for the command's robot and the comment says motion stops with power left on; the handler does not clear a destination. | upstream_code | Cmd.gpl:1833-1841 |
| In PC mode, state replies 0 and the integer Robot.TrajState of the selected robot. | upstream_code | Cmd.gpl:1816-1828 |
| TrajState labels are 0 Halted, 1 Idle, 2 to 6 position-mode motion, 8 velocity, 9 homing, 10 jog, 11 external trajectory and 15 motion terminated nulling. | upstream_code | Globals.gpl:118-129 |
| Check_ProfIdx rejects an index below 1 or above N_PROF; success leaves the reply unchanged. | upstream_code | Cmd.gpl:111-122 |
| N_PROF is the constant 20. | upstream_code | Globals.gpl:82 |
| MoveJ takes a profile index and up to 12 angle parameters, calls Move.Loc when there are more parameters than axes, and does not change its reply to a reached flag. | upstream_code | Cmd.gpl:1688-1727 |
| Joint angles are degrees for rotary axes and millimetres for linear axes. | upstream_code | pf400_driver/pf400_driver/tcp_driver.py:486-488 |
| mspeed's optional parameter is the new system speed as a percentage and is stored in PDbNum 601; those lines state no numeric range. | upstream_code | Cmd.gpl:524-546 |
| On the status thread, selectRobot requests NewRobNum for the given robot; selecting the current robot leaves the reply at the default. | upstream_code | Cmd.gpl:565-593 |
| The command delegate is Cmd_ concatenated with the first token as received. | upstream_code | Class_command.gpl:304 |
| stop_robot assigns halt and sends it through send_command. | upstream_code | pf400_driver/pf400_driver/tcp_driver.py:399-409 |
| connect_robot connects to self.host and self.port. | upstream_code | pf400_driver/pf400_driver/tcp_driver.py:117 |
| send_command receives with recv and that line does not call settimeout. | upstream_code | pf400_driver/pf400_driver/tcp_driver.py:156 |
| The client states that a second command will not reply until the first motion is complete. | upstream_code | pf400_driver/pf400_driver/tcp_driver.py:19 |
| A socket.error around socket() falls off the end of connect_robot. connect() is outside that handler, so its socket.error propagates. send_command returns the string failed on socket.error. | upstream_code | pf400_driver/pf400_driver/tcp_driver.py:103-170 |
| The lab client's status-port init sends selectRobot 1 and then enable_power. | upstream_code | pf400_driver/pf400_driver/pf400_driver.py:275-278 |
| The lab client's movement-state comment labels 0 as power off and 1 as stopping. | upstream_code | pf400_driver/pf400_driver/pf400_driver.py:307-315 |

## Device choice

The card entered as family ros / RosDriver. The override `MHS/registry/overrides/p5-reauthor-pf400-routing.json`
re-selects `pf400_driver.pf400_driver.tcp_driver:PF400` (tcp_driver.py:12) as a direct Driver. The class's
`stop_robot` is not the stop this package uses.

## Scope

| capability | commands | note |
|---|---|---|
| `x-cap.ad-sdl.move_joints.v1` (R2) | `mspeed`, then `MoveJ`, on the robot port | the stop lock covers each send, not the connect and not the reply; cancellation and the e-stop epoch are checked again immediately before `MoveJ` |
| `x-cap.ad-sdl.halt.v1` (safe state, R2) | `selectRobot 1`, `halt`, `state` on the status port | one connection; one deadline for the connect and every reply byte; fails while a `MoveJ` reply is still outstanding |
| `traj_state` (state read) | `state` on the robot port | refused while a move is unconfirmed; the read itself does not hold the stop lock |
| e-stop | the halt action's sequence | confirmed by TrajState 0 or 1 only when no `MoveJ` is unanswered; the default budget is 4 s and includes the connect |

Not covered: power, attach, home, reset, gripper, plate transfer, kinematics, ROS, the camera, and any re-enable.

## Limits

Profile, each joint target and speed are `Limit.operator_required`. Cmd.gpl:116 shows the lower comparison `1` and
the name `N_PROF`. Globals.gpl:82 shows `N_PROF` as 20. One limit path cannot cite both files, so the package does
not declare a closed 1..20 profile limit. The example overlay's numbers are placeholders. `MoveJ` accepts at most 12
angle parameters (Cmd.gpl:1697); that is a schema bound, not a joint limit. A list shorter than the controller's axis
count is a negative reply (EcInvJa, Cmd.gpl:1725-1726). The axis count is `RobNumAxes`, not a fixed 6.

Profile is published as a count (`unit` `1`). Speed is published as a percentage (`unit` `%`) because Cmd.gpl:532
calls the parameter a percentage; the number is not scaled, and no range is declared. Joint numbers are published
with the dimensionless code `1` because a rotary axis is degrees and a linear axis is millimetres
(tcp_driver.py:486-488), which are not one UCUM unit. The driver sends those numbers unchanged. The command output
repeats the profile, the joint numbers and the speed that were sent, plus the reply. `accepted` is the reply's
first token being 0. Class_command.gpl:280 sets the default reply to 0. tcp_driver.py:23 says a leading 0 means
the command was successful. Neither line is a reached flag.

## Safety and stop

R2 (an arm). The e-stop and the safe-state action open the status port themselves. One deadline, `stop_confirm_s`,
covers the connect, both commands, every reply byte and the TrajState polls. It cannot be set above the declared
15 s e-stop latency. They send `selectRobot 1` and `halt` as two receives, then read `state` until TrajState is
0 (Halted, Globals.gpl:118) or 1 (Idle, Globals.gpl:119). The lab client's comment instead says 0 = power off and
1 = stopping (pf400_driver.py:309-310). Any other code, including 15, is not halted. A busy or unreachable status
port fails the stop (`MHS.SAFETY.SAFE_STATE_UNREACHED`, latch kept, retried). The package sends `halt` when the
status sequence gets that far, including when the arm already reads idle.

The stop lock is not held across a connect or a reply, so a trickled `recv` cannot postpone `halt`. A robot-port
handshake does not share a lock with the status port. Each caller binds `port` on its own thread, which is what
`connect_robot` reads (tcp_driver.py:117), and copies it before the handshake. Cancellation and publication of
that socket share one lock, and the lock is not held across the handshake. A timed-out wait closes a socket that
was already published. A socket that becomes ready after the wait was abandoned is closed by the worker and is
not published. Cancellation and the e-stop epoch are checked again under the stop lock immediately before `mspeed` and
immediately before `MoveJ`. A stop that has already started does not get a following `MoveJ`.

`Cmd_Halt` is `Robot.RapidDecel` (Cmd.gpl:1840-1842). The mailbox is cleared after `Handler` returns
(Main.gpl:605-607). The reply is sent after that wait (Main.gpl:207-209, then Main.gpl:225), so a complete MoveJ
reply is the retirement of that command. Until the reply arrives, the command can still be handled after TrajState
reads 0 or 1. The stop sends `halt` and then fails, and it keeps the fence. It does not report the safe state.
When the reply arrives the fence is cleared and the move's outcome is unknown. A later halt reads TrajState again
and can confirm 0 or 1. Main.gpl:398 flushes pending serial input. It is not the TCP mailbox.

`mspeed` is a persistent controller scale (PDbNum 601). The scale is not restored: the GPL states no safe default.
A `MoveJ` reply that arrives after this endpoint's halt is an unknown outcome, not success. This package does not
send `enable_power` (the lab client does, at pf400_driver.py:278). It does not unpause, re-enable power, attach
or home. The override does not set `capability_classes`. The source scan's candidate classes remain, including
`cap.motion.joint_position.v1`, and the card floor stays R1. This driver implements only the extension commands,
at R2.
