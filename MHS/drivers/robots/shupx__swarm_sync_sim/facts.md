# Facts and tags for gh.shupx/swarm_sync_sim

Every fact cites the pinned clone at commit `4837b511c3d2bcaa36448e5e5af51335004bafd8`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. `vendor_doc` refs name a text file of the clone.
The same facts are written into `driver.py` (`facts = [...]`); the reference file
is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The sim clock advertises rosgraph_msgs/Clock on the absolute /clock topic and std_msgs/Bool on the absolute /sss_clock_is_online topic, both as latched publishers. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:41-42 |
| TimeServer advertises the absolute /sss_clock_control, /sss_timeclient_register and /sss_timeclient_unregister services. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:43-45 |
| The clock-control callback sets is_paused_ from the proceed field, changes max_speed_ratio_ and the wall-timer period only when max_sim_speed is nonzero, and always answers success=true. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:101-116 |
| The speed-regulator wall timer requests and tries a clock update only while the clock is not paused. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:81-99 |
| The update-clock-request callback stores the client's request and calls try_update_clock without checking is_paused_. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:164-193 |
| try_update_clock publishes the minimum pending request on /clock only when every time client has a new request and that request is later than the current ROS time. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:248-284 |
| try_update_clock checks the clients from index 0 and does not publish when any of them, client 0 included, has no new request. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:248-272 |
| After publishing, try_update_clock clears has_new_request for every client whose request time is at or before the new sim_time_. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:286-297 |
| The TimeServer constructor registers time client 0 as the simulation speed regulator. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:58-62 |
| The regulator step speed_regulator_period_ is 0.01 s and its wall timer period is that step divided by max_speed_ratio_. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:67-68 |
| The node reads max_speed_ratio (default 100) and auto_start (default false) and starts with is_paused_ = !auto_start_. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:34-39 |
| sim_clock.launch defaults max_speed_ratio to 100, auto_start to true and open_ui to true, and starts clock_ui.py when open_ui is set. | upstream_code | src/sss_sim_env/launch/sim_clock.launch:4-23 |
| clock_ui.py calls /sss_clock_control with proceed=True from call_start, with proceed=False from call_pause, and with proceed=True and the new max_sim_speed from call_speed_change. | upstream_code | src/sss_sim_env/scripts/clock_ui.py:48-82 |
| clock_ui.py connects call_start to the Start button, call_pause to the Pause button and call_speed_change to the speed dial's valueChanged signal. | upstream_code | src/sss_sim_env/scripts/clock_ui.py:162-164 |
| Registering a time client appends it, returns client_id and success=true, and calls try_update_clock. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:119-136 |
| Unregistering client 0 is refused; a matching nonzero client id is erased and success set true, otherwise success stays false. | upstream_code | src/sss_sim_env/src/sim_clock/TimeServer.cpp:140-162 |
| The SimClockControl request carries proceed and max_sim_speed, and max_sim_speed 0 keeps the original simulation speed. | upstream_code | src/sss_sim_env/srv/SimClockControl.srv:3-6 |
| The SimClockControl response is a success boolean. | upstream_code | src/sss_sim_env/srv/SimClockControl.srv:7-8 |
| The TimeRequest message carries time_client_id and request_time. | upstream_code | src/sss_sim_env/msg/TimeRequest.msg:1-2 |
| The README describes swarm_sync_sim as a synchronized (lock-stepped) multi-robot swarm simulation platform based on ROS. | vendor_doc | README.md:5 |
| The README's first usage step launches sss_sim_env sim_clock.launch with max_speed_ratio and auto_start arguments. | vendor_doc | README.md:35-36 |

## Scope

The package covers the simulation-clock environment control of `sss_sim_env`:
the absolute `/clock` and `/sss_clock_is_online` publications and the absolute
`/sss_clock_control` service. It does not start the nodelet, a ROS graph or
rosbridge, and it does not import ROS or the clone.

`/sss_clock_control` has no relative name and is advertised on the node's root
namespace, so the driver records the upstream tokens as absolute endpoints.
Deployment namespace, remapping and rosbridge assumptions are not upstream
facts.

The service callback applies both request fields. `pause` sends
`max_sim_speed = 0.0`, the message's documented "keep original sim speed" value.
`resume` sends the caller's speed ratio, but the clone states no numeric maximum
and the launch value is a configurable default, so the input is
`Limit.operator_required` until the operator supplies the site envelope. The
example overlay is operator-only and narrows this example site to one approved
ratio; it is not a device fact.

Participant registration (`/sss_timeclient_register`,
`/sss_timeclient_unregister`) and per-client time requests
(`/sss_time_client/update_clock_request`), and therefore the lock-step stepping
loop itself, are not covered by this package: one rosbridge binding cannot
sequence register, request and wait for `/clock`, and a registered client with
no new request blocks clock updates. The simulated robots, PX4/MAVROS, tello
and UGV topics, physics, reset, snapshot, restore and rendering are also not
covered.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS recording transport
(event-driven clock control, no simulator)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, and no snapshot/restore.
The fake holds one placeholder clock sample and advances it by a fixed test step
on each observation while unpaused; it does not account for participants or
schedule lock-step time. The gaps disclose the absent TimeServer, nodelet
manager, ROS graph, time-client network and wall clock.

## Safety

The device is simulated at R0: this package controls only the simulation clock
of an isolated simulator. `pause` is an input-free `safe_state=True` action and
the acknowledged `/sss_clock_control` service bound as the simulator stop. The
runtime latches in software before calling it. After an e-stop the resume
command is refused until `mhs.safety.reset` clears the latch.

This is not a physical emergency stop. The clock-control callback stores the
pause flag and always answers `success=true`; its only consumer is the wall-timer
speed regulator, time client 0, which stops posting clock requests while paused
(`TimeServer.cpp:81-99`). The update-clock-request callback calls
`try_update_clock` without checking the pause flag, but `try_update_clock`
publishes `/clock` only when every client, client 0 included, has a new request
(`TimeServer.cpp:248-272`) and clears the requests it satisfied (`286-297`), so
after a pause time clients can complete at most the regulator's pending 0.01 s
step (`67-68`) and simulated time then holds (model review of 2026-11-04; the
author's text said simulated time was not guaranteed to stop). Nodes timed on
simulated time freeze while it holds.

Any ROS client can resume the clock with `proceed=true`. The shipped
`sim_clock.launch` starts `clock_ui.py` by default, and its Start button and any
speed-dial change send `proceed=true` (`clock_ui.py:48-82`, `162-164`); the MHS
latch refuses only this driver's commands. The fake has no physical stop and
makes no hardware-safety claim.

## Tags

`ros`, `ros1`, `simulation`, `swarm-sync-sim`, `clock`, `pause`, `lock-step`
