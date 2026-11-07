OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.shupx/fastswarmsim

Every fact cites the pinned clone at commit `56a6380fcd409a0700baedc39a632a823622d633`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. `vendor_doc` refs name a text file of the clone.
The same facts are written into `driver.py` (`facts = [...]`); the reference file
is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The time coordinator publishes rosgraph_msgs::msg::Clock on the absolute /clock topic with rclcpp::ClockQoS, which the source comment describes as best-effort and volatile. | upstream_code | src/fss_time/src/time_coordinator.cpp:181-183 |
| The coordinator publishes fss_time_interfaces::msg::SimClockStatus on the relative fss/sim_clock_status topic with KeepLast(10) and transient-local durability. | upstream_code | src/fss_time/src/time_coordinator.cpp:185-186 |
| The coordinator creates the relative fss/clock_control service of type fss_time_interfaces::srv::SimClockControl. | upstream_code | src/fss_time/src/time_coordinator.cpp:187-188 |
| The clock_control callback applies request->max_real_time_factor, then request->running, and always answers success=true with message "time_coordinator updated". | upstream_code | src/fss_time/src/time_coordinator.cpp:192-195 |
| set_running stores the flag, resets the regulator and real-time requests to the current simulation time and publishes the status message. | upstream_code | src/fss_time/src/time_coordinator.cpp:348-361 |
| set_max_real_time_factor stores the value, resets the regulator and real-time requests, resets the regulator timer and publishes the status message. | upstream_code | src/fss_time/src/time_coordinator.cpp:363-374 |
| should_advance returns false and reports RequestNotAdvanced while running_ is false. | upstream_code | src/fss_time/src/time_coordinator.cpp:695-700 |
| A 200 ms wall timer calls on_clock_status_tick. | upstream_code | src/fss_time/src/time_coordinator.cpp:341-344 |
| on_clock_status_tick updates the observed real-time factor, calls publish_clock_locked and publishes the status. | upstream_code | src/fss_time/src/time_coordinator.cpp:609-617 |
| publish_clock fills a rosgraph_msgs::msg::Clock from the current simulation time and publishes it when publish_clock_ and clock_pub_ are set. | upstream_code | src/fss_time/src/time_coordinator.cpp:785-791 |
| The fss_time README says the coordinator provides fss/clock_control to pause/resume the clock and set max_real_time_factor at runtime. | vendor_doc | src/fss_time/README.md:21 |
| The fss_time README documents max_real_time_factor default 1.0, says 2.0 allows up to 2x and a large positive value gives the highest practical speed. | vendor_doc | src/fss_time/README.md:43 |
| The fss_time README documents max_real_time_factor 0.0 as disabling periodic regulator requests and not as an unconstrained free-run mode. | vendor_doc | src/fss_time/README.md:221 |
| The coordinator sets has_parent_coordinator_ when the fss_time_parent_coordinator_endpoint parameter is not empty. | upstream_code | src/fss_time/src/time_coordinator.cpp:147-149 |
| receive_parent_grant sets sim_time_ns_ to a granted time newer than the current one and publishes the clock without checking running_. | upstream_code | src/fss_time/src/time_coordinator.cpp:502-525 |
| With follows_real_time_ set, should_advance advances to the real-time request (capped by the regulator request below a factor of 1.0) and waits only for a participant that neither follows real time nor has a new request. | upstream_code | src/fss_time/src/time_coordinator.cpp:707-725 |
| A child coordinator registers with its parent and passes its own follows_real_time setting. | upstream_code | src/fss_time/src/time_coordinator.cpp:278-288 |
| time_coordinator.launch.py declares start_coordinator_ui with the default true. | upstream_code | src/fss_time/launch/time_coordinator.launch.py:32-37 |
| time_coordinator.launch.py starts time_coordinator_ui.py when start_coordinator_ui is true. | upstream_code | src/fss_time/launch/time_coordinator.launch.py:115-124 |
| The coordinator UI's play/pause handler calls request_control(not self.bridge.running, self.bridge.expected_rtf). | upstream_code | src/fss_time/scripts/time_coordinator_ui.py:507-508 |

## Scope

The package covers the shared simulation-time environment control of `fss_time`:
the absolute `/clock` publication, the relative `fss/sim_clock_status` status
topic and the relative `fss/clock_control` service. It does not start the
coordinator, a ROS graph or rosbridge, and it does not import ROS or the clone.

The service is relative, so the driver records the upstream token
`fss/clock_control` as `source_name` and configures the resolved root endpoint
`/fss/clock_control`. The same applies to `fss/sim_clock_status`. A deployment
that pushes the coordinator into a namespace must expose the namespace-qualified
endpoints; `/clock` is absolute in the clone. Deployment namespace and remapping
assumptions are not upstream facts.

The service callback applies both request fields unconditionally. A pause
therefore also writes `max_real_time_factor`; this driver sends the documented
`0.0` value (periodic regulator requests disabled) while stopped. Resume
requires an operator-supplied factor, so the numeric input is
`Limit.operator_required` until a site envelope is supplied.

The clone also exposes the PX4/MAVROS setpoint, state, arming and mode
interfaces and the LiDAR point cloud. Those are NOT COVERED by this package;
vehicle motion is not claimed and no arm, takeoff, setpoint or mode command is
issued. The package controls simulation time only.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS canned-response fake
(event-driven clock control, no simulator)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, and no snapshot/restore.
The fake holds placeholder clock and status samples and does not advance them,
account for participants or schedule lock-step time. The gaps disclose the
absent coordinator, ZeroMQ participant network, PX4 dynamics and wall clock.

## Safety

The device is simulated at R0: only the shared simulation clock is controlled,
and the effects are confined to simulated state. `pause` is an input-free
`safe_state=True` action and the acknowledged `/fss/clock_control` service bound
as the simulator stop. After the service returns, `should_advance` refuses to
advance the clock while `running_` is false. The runtime latches in software
before calling it. The coordinator's 200 ms status timer is a source fact, not
a timing guarantee of the fake.

The pause holds only a root coordinator (no `fss_time_parent_coordinator_endpoint`,
the launch default). A child coordinator in the multi-machine hierarchy sets its
clock from every parent `GRANT` in `receive_parent_grant` without checking
`running_`, and a parent that follows real time does not wait for a child that
follows real time, so pausing a child does not hold its clock; pause the root
coordinator instead. Any client of `fss/clock_control` can resume the clock while
the MHS latch is held: the default `time_coordinator.launch.py` starts the
coordinator UI, whose play button sends `running=true`. The status publisher is
`KeepLast(10)` transient-local, so a new subscription may first receive a stored
sample from before the latest pause or resume.

This is not a physical emergency stop and does not stop a vehicle, a PX4
controller or an external ROS client. The fake has no physical stop and makes
no hardware-safety claim.

## Tags

`ros`, `ros2`, `simulation`, `fastswarmsim`, `px4`, `clock`, `pause`
