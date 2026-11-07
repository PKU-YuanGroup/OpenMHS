# Facts and tags for gh.jjshoots/crazyflyt

Every fact cites its source at commit `85d99afa21cb5b90fd130cd480f0589a2b700b58`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The library is for flying real CrazyFlie 2.x drones, with a simulation environment via PyFlyt | vendor_doc | readme.md:5 |
| The upstream README says the library is in the developmental stage | vendor_doc | readme.md:3 |
| The hardware example opens a DroneController on a radio URI, selects position control, starts it, sends a hover setpoint at 0.5 m and then 0 m, stops it and ends it | upstream_code | examples/fly_single.py:25-44 |
| The hardware example sends the setpoint [0.0, 0.0, 0.5, 0.0] to hover at 0.5 m | upstream_code | examples/fly_single.py:31-32 |
| The setpoint is four numbers: (x, y, z, yaw) in position control or (vx, vy, vz, vyaw) in velocity control | upstream_code | CrazyFlyt/drone_controller.py:102-108 |
| The control thread repeats every period = 1/40.0 s | upstream_code | CrazyFlyt/drone_controller.py:29 |
| With running true, the control thread sends a position setpoint when pos_control is true and a world-frame velocity setpoint otherwise | upstream_code | CrazyFlyt/drone_controller.py:120-129 |
| The control thread multiplies the four-value setpoint by self.rad_to_deg before sending it | upstream_code | CrazyFlyt/drone_controller.py:120-129 |
| rad_to_deg is [1.0, 1.0, 1.0, math.pi / 180.0], so only the fourth value is converted from radians to degrees and the first three are passed unchanged | upstream_code | CrazyFlyt/drone_controller.py:39 |
| When running is false the control thread calls send_stop_setpoint every period | upstream_code | CrazyFlyt/drone_controller.py:130-133 |
| start() sets running true, stop() sets running false, and end() clears running, stops the logging configuration and closes the link | upstream_code | CrazyFlyt/drone_controller.py:80-92 |
| position_estimate holds the logged stateEstimate.x, .y and .z and the yaw converted from degrees to radians | upstream_code | CrazyFlyt/drone_controller.py:144-147 |
| position_estimate and setpoint are four-element numpy arrays initialised to zero | upstream_code | CrazyFlyt/drone_controller.py:35-36 |
| The velocity example describes the setpoint [1.0, 0.0, 0.0, 1.0] as flying in horizontal x with a 1 rad/s yaw rate | upstream_code | examples/sim_swarm.py:45-50 |
| The constructor opens a SyncCrazyflie link and starts a daemon control thread | upstream_code | CrazyFlyt/drone_controller.py:42-73 |

## Limits

The clone states no numeric envelope for a setpoint: the four values are passed to the flight controller
(`CrazyFlyt/drone_controller.py:123-129`) and the source only fixes the four-value layout. No catalogue or library
default is a bound of this device, so every motion input is `Limit.operator_required` and is refused with
`MHS.SAFETY.LIMITS_UNSET` until the site overlay supplies it.

| capability | path | bound | source |
|---|---|---|---|
| x-cap.jjshoots.position_setpoint.v1 | x, y, z (m) | operator_required: the clone states no position envelope | |
| x-cap.jjshoots.position_setpoint.v1 | yaw (rad) | operator_required: the clone states no yaw envelope | |
| x-cap.jjshoots.velocity_setpoint.v1 | vx, vy, vz (unit "1": the clone states no unit) | operator_required: the clone states no velocity envelope | |
| x-cap.jjshoots.velocity_setpoint.v1 | yaw_rate (rad/s) | operator_required: the clone states no yaw-rate envelope | |

`site-limits.example.json` shows the overlay form and fills these example bounds; it may only narrow and is not a
device fact. The catalogue class `cap.device.configure.v1` is bound by the writable `pos_control` flag; it carries no
numeric bound.

## Safety

The native stop is `DroneController.stop()` (`CrazyFlyt/drone_controller.py:84-86`): it clears `running`, and the
control thread then calls `send_stop_setpoint` every period (`CrazyFlyt/drone_controller.py:130-133`). The clone
documents no independent hardware e-stop, no kill switch and no power cut, so `estop_physical_ref` is not set. The
required independent stop for this R2 hardware package is the declared `safe_state` action
`x-cap.jjshoots.halt.v1`, which calls the same native `stop()`; `safe_state` states plainly that the link stays open
and that this is not a power cut. The e-stop and the safe-state action are software calls; the package claims no
protection beyond them.

The package is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null). The acceptance gate runs the
fake backend only; the hardware backend is refused by the loader at R2 until a human signs `reviewed_by`. Nothing in
this package ran on a drone or on the upstream simulator.

The fake (`fake.py`) stores setpoints and flags, does not open a radio link and does not integrate a trajectory; it
returns `position_estimate` at the constructor's zero array. It uses only members of `DroneController` at the pinned
commit; its numbers are test data.

## Tags

drone, uav, crazyflie, position control, velocity control, flight
