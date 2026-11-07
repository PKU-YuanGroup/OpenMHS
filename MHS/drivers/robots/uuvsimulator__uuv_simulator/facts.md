# Facts and tags for gh.uuvsimulator/uuv_simulator

Pinned upstream: `robots/uuvsimulator/uuv_simulator` at
`bfb40cb153684a0703173117b6bbf4258e8e71c5` (Apache-2.0).

The selected device is the `UnderwaterCurrentROSPlugin` world plugin from
`uuv_world_ros_plugins`: the simulated water-current environment exposed
through relative ROS services and a stamped flow-velocity topic.  This is a
configuration-only ROS 1 `RosDriver` over rosbridge; no Python native class is
declared and no ROS, Gazebo or hardware process is started by this package.

## Native interface

File: `uuv_world_plugins/uuv_world_ros_plugins/src/UnderwaterCurrentROSPlugin.cc`

| kind | native item | source |
|---|---|---|
| service | relative `set_current_velocity`, request `uuv_world_ros_plugins_msgs/SetCurrentVelocity` | `UnderwaterCurrentROSPlugin.cc:110-114`, type include on `UnderwaterCurrentROSPlugin.hh:36` |
| service | relative `set_current_horz_angle`, request `uuv_world_ros_plugins_msgs/SetCurrentDirection` | `UnderwaterCurrentROSPlugin.cc:116-120`, type include on `UnderwaterCurrentROSPlugin.hh:37` |
| service | relative `set_current_vert_angle`, request `uuv_world_ros_plugins_msgs/SetCurrentDirection` | `UnderwaterCurrentROSPlugin.cc:122-126`, type include on `UnderwaterCurrentROSPlugin.hh:37` |
| publisher | relative `current_velocity`, `geometry_msgs/TwistStamped` | topic default `uuv_world_plugins/uuv_world_plugins/src/UnderwaterCurrentPlugin.cc:81-86`; advertise `UnderwaterCurrentROSPlugin.cc:70-72`; type include `UnderwaterCurrentROSPlugin.hh:33` |

The plugin reads the optional `<namespace>` SDF element and creates its ROS
node handle from it (`UnderwaterCurrentROSPlugin.cc:62-68`).  The shipped
`uuv_gazebo_worlds/worlds/auv_underwater_world.world:78-105` configures the
plugin under `hydrodynamics`, with current velocity `0..5 m/s` and angles
`-pi..pi`.  These are example deployment configuration, not a fixed device
bound; the package uses `Limit.operator_required` and expects the operator to
supply the actual world's ranges.

## Control and stop trace

`UpdateCurrentVelocity` calls `SetMean` on the velocity, horizontal-angle and
vertical-angle Gauss-Markov models and sets `success` true only when all three
calls succeed (`UnderwaterCurrentROSPlugin.cc:170-193`).
`GaussMarkovProcess::SetMean` returns false when the requested mean is outside
the model's configured minimum/maximum
(`uuv_world_plugins/uuv_world_plugins/src/GaussMarkovProcess.cc:41-49`).  The
model ranges come from the `constant_current` SDF block
(`UnderwaterCurrentPlugin.cc:91-116` for velocity and `:122-190` for the
angles).

The fixed zero-current action calls the same service with
`velocity=0`, `horizontal_angle=0` and `vertical_angle=0`.  It is an
acknowledged software action on the model means; it does not stop the vehicle
or the Gazebo world.  `SetMean` resets the process state to the new mean
(`GaussMarkovProcess.cc:35-49`), so the flow is zero from the next world update
while the velocity model's `noiseAmp` is zero; `GaussMarkovProcess::Update`
adds `noiseAmp` noise and clamps to the configured range
(`GaussMarkovProcess.cc:74-86`).  The action fails closed when any of the three
configured ranges excludes zero, because `SetMean` then returns false.  The
callback calls `SetMean` in the order velocity, horizontal, vertical and stops at
the first refusal, so a refused request can leave the velocity mean already
changed (model review note, 2026-11-04).

`OnUpdateCurrentVel` publishes the flow vector from the current field in the
`/world` frame when at least 0.05 s has passed since the last publication
(`UnderwaterCurrentROSPlugin.cc:133-148`); the constructor sets that period
(`UnderwaterCurrentROSPlugin.cc:21-25`).

## Facts copied into `driver.py`

| fact | source | ref |
|---|---|---|
| Reads the optional namespace SDF element and creates the ROS node handle from it. | upstream_code | `uuv_world_plugins/uuv_world_ros_plugins/src/UnderwaterCurrentROSPlugin.cc:62-68` |
| Advertises a `geometry_msgs/TwistStamped` flow velocity on the configured topic. | upstream_code | `.../UnderwaterCurrentROSPlugin.cc:70-72` |
| Defaults the flow topic name to `current_velocity` when the SDF topic element is absent. | upstream_code | `uuv_world_plugins/uuv_world_plugins/src/UnderwaterCurrentPlugin.cc:81-86` |
| Advertises the relative services `set_current_velocity`, `set_current_horz_angle` and `set_current_vert_angle`. | upstream_code | `.../UnderwaterCurrentROSPlugin.cc:110-126` |
| The header includes `TwistStamped`, `SetCurrentVelocity` and `SetCurrentDirection`. | upstream_code | `.../UnderwaterCurrentROSPlugin.hh:33-37` |
| `UpdateCurrentVelocity` requires all three `SetMean` calls to succeed. | upstream_code | `.../UnderwaterCurrentROSPlugin.cc:170-193` |
| `GaussMarkovProcess::SetMean` rejects a mean outside the model range. | upstream_code | `uuv_world_plugins/uuv_world_plugins/src/GaussMarkovProcess.cc:41-49` |
| `Reset` sets the process state to the mean; `SetMean` calls it after storing an in-range mean. | upstream_code | `uuv_world_plugins/uuv_world_plugins/src/GaussMarkovProcess.cc:35-49` |
| `Update` scales the state by `(1 - step * mu)`, adds `noiseAmp` times a uniform number in [-0.5, 0.5] and clamps to [min, max]. | upstream_code | `uuv_world_plugins/uuv_world_plugins/src/GaussMarkovProcess.cc:74-86` |
| The velocity model range is read from the `constant_current` SDF block. | upstream_code | `uuv_world_plugins/uuv_world_plugins/src/UnderwaterCurrentPlugin.cc:91-116` |
| The horizontal-angle model range is read from the `constant_current` SDF block. | upstream_code | `uuv_world_plugins/uuv_world_plugins/src/UnderwaterCurrentPlugin.cc:122-153` |
| The vertical-angle model range is read from the `constant_current` SDF block. | upstream_code | `uuv_world_plugins/uuv_world_plugins/src/UnderwaterCurrentPlugin.cc:161-190` |
| The shipped world configures `0..5 m/s` and `-3.141592653589793238..3.141592653589793238 rad` under `hydrodynamics`. | upstream_code | `uuv_gazebo_worlds/worlds/auv_underwater_world.world:78-105` |
| `OnUpdateCurrentVel` publishes the flow vector in `/world` when the ROS publish period has elapsed. | upstream_code | `.../UnderwaterCurrentROSPlugin.cc:133-148` |
| The constructor sets `rosPublishPeriod` to 0.05 s. | upstream_code | `.../UnderwaterCurrentROSPlugin.cc:21-25` |

## Fake

The fake is an analytic ROS-free stand-in for the service and flow-topic
traffic.  It is not a recording of captured traffic and not the upstream
Gazebo world plugin.  It claims F0 only.  Its model ranges, state values and
flow mapping are placeholders for tests, never device facts or limits.

## Tags

`ros`, `ros1`, `uuv`, `underwater`, `simulation`, `current`, `flow`,
`environment`
