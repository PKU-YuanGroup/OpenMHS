# Facts and tags for gh.field-robotics-lab/dave

Every fact cites the pinned clone at commit `e54ea16bdaf7d6dbb466cf141846a03f284a44dd` as
`upstream_code` with a `path/in/clone:LINE` reference. The same facts are written in
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the
driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| CMakeLists builds the shared library dave_ocean_current_plugin from src/ocean_current_plugin.cpp. | upstream_code | gazebo/dave_gazebo_ros_plugins/CMakeLists.txt:81-84 |
| A shipped world loads libdave_ocean_current_plugin.so with namespace hydrodynamics and current topic current_velocity. | upstream_code | models/dave_worlds/worlds/dave_ocean_waves_dvl_current_profiling.world:85-88 |
| The ROS plugin returns without loading when ROS is not initialized, reads the namespace from the SDF (empty when absent) and builds ros::NodeHandle(ns). | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:63-77 |
| The ROS plugin advertises geometry_msgs::TwistStamped on currentVelocityTopic with queue size 10. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:79-81 |
| The world plugin reads constant_current/topic from the SDF and defaults it to the literal current_velocity. | upstream_code | gazebo/dave_gazebo_world_plugins/src/ocean_current_world_plugin.cc:167-175 |
| The constructor sets rosPublishPeriod to 0.05 s. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:27-31 |
| ConnectWorldUpdateBegin calls OnUpdateCurrentVel, which publishes only after rosPublishPeriod, stamps frame_id /world and copies the current vector into twist.linear x, y and z. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:165-184 |
| The world plugin's Update sets the current vector to magnitude * cos(h) * cos(v), magnitude * sin(h) * cos(v) and magnitude * sin(v) from the velocity, horizontal-angle and vertical-angle processes, under a comment that names the NED frame. | upstream_code | gazebo/dave_gazebo_world_plugins/src/ocean_current_world_plugin.cc:114-129 |
| The world plugin's Load logs 'WARNING: Current velocity calculated in the ENU frame'. | upstream_code | gazebo/dave_gazebo_world_plugins/src/ocean_current_world_plugin.cc:94-96 |
| The world plugin advertises the Gazebo msgs::Vector3d topic ns/currentVelocityTopic. | upstream_code | gazebo/dave_gazebo_world_plugins/src/ocean_current_world_plugin.cc:291-296 |
| The ROS plugin advertises the relative get_current_velocity_model service with the GetCurrentVelocityModel callback. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:99-103 |
| GetCurrentVelocityModel takes dave_gazebo_ros_plugins::GetCurrentModel and replies with the velocity model mean, min, max, noise and mu. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:384-394 |
| The ROS plugin advertises the relative get_current_horz_angle_model service with the GetCurrentHorzAngleModel callback. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:112-115 |
| GetCurrentHorzAngleModel takes GetCurrentModel and replies with the horizontal-angle model mean, min, max, noise and mu. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:397-407 |
| The get_current_vert_angle_model service is advertised with the GetCurrentHorzAngleModel callback. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:123-127 |
| The ROS plugin advertises the relative set_current_velocity service with the UpdateCurrentVelocity callback. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:129-133 |
| UpdateCurrentVelocity calls SetMean on the velocity, horizontal-angle and vertical-angle models in a short-circuit && chain and sets success true only when all three calls return true. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:319-341 |
| SetMean returns false when the requested mean is outside the configured min and max; on success it stores the mean and resets the process variable to it. | upstream_code | gazebo/dave_gazebo_world_plugins/src/gauss_markov_process.cc:36-50 |
| GaussMarkovProcess::Update multiplies the process variable by (1 - step * mu), adds noiseAmp times a uniform draw in [-0.5, 0.5] and clamps the result to [min, max]. | upstream_code | gazebo/dave_gazebo_world_plugins/src/gauss_markov_process.cc:75-87 |
| The ROS plugin also advertises set_current_velocity_model, set_current_horz_angle_model, set_current_vert_angle_model, set_stratified_current_velocity, set_current_horz_angle, set_stratified_current_horz_angle, set_current_vert_angle and set_stratified_current_vert_angle. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:93-163 |
| For each stratified-database row the world plugin creates magnitude, horizontal-angle and vertical-angle Gauss-Markov models whose means come from the row (vertical 0). | upstream_code | gazebo/dave_gazebo_world_plugins/src/ocean_current_world_plugin.cc:376-411 |
| Each publish period the ROS plugin also publishes the stratified-database rows with the tidal harmonic or tidal-table data and the ebb and flood directions. | upstream_code | gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp:170-254 |
| The transient-current model plugin subscribes to the stratified-current database topic. | upstream_code | gazebo/dave_gazebo_model_plugins/src/ocean_current_model_plugin.cc:209-213 |
| The transient-current model plugin picks the database row for the vehicle's depth from the model's world pose. | upstream_code | gazebo/dave_gazebo_model_plugins/src/ocean_current_model_plugin.cc:309-336 |
| rexrov_oberon7_transient_current.xacro loads libdave_ocean_current_model_plugin.so with flow_velocity_topic hydrodynamics/current_velocity/$(arg namespace) and tide_oscillation true, and gives libuuv_underwater_object_ros_plugin.so the same flow_velocity_topic. | upstream_code | urdf/robots/rexrov_description/urdf/rexrov_oberon7_transient_current.xacro:82-104 |
| rexrov_oberon7.xacro gives libuuv_underwater_object_ros_plugin.so the flow_velocity_topic hydrodynamics/current_velocity. | upstream_code | urdf/robots/rexrov_description/urdf/rexrov_oberon7.xacro:82-84 |
| For the constant-current velocity model the world plugin reads mean, min, max, mu and noiseAmp from the SDF and asserts min < max, mean within min and max, mu in [0, 1) and noiseAmp in [0, 1). | upstream_code | gazebo/dave_gazebo_world_plugins/src/ocean_current_world_plugin.cc:180-204 |
| The shipped current-profiling world configures the velocity model with mean 0, min 0 and max 5.0 and both angle models with mean 0, min -3.141592653589793 and max 3.141592653589793, each with mu 0.0 and noiseAmp 0.0. | upstream_code | models/dave_worlds/worlds/dave_ocean_waves_dvl_current_profiling.world:89-111 |
| SetCurrentVelocity.srv declares float64 velocity, horizontal_angle and vertical_angle requests and a bool success response. | upstream_code | gazebo/dave_gazebo_ros_plugins/srv/SetCurrentVelocity.srv:16-20 |
| GetCurrentModel.srv declares float64 mean, min, max, noise and mu response fields. | upstream_code | gazebo/dave_gazebo_ros_plugins/srv/GetCurrentModel.srv:17-21 |
| The shipped integrated demo includes gazebo_ros empty_world.launch with use_sim_time true. | upstream_code | examples/dave_demo_launch/launch/dave_integrated_demo.launch:17-26 |

## Scope

The package covers DAVE's ocean-current environment as defined by
`dave_gazebo_ros_plugins`: the `geometry_msgs/TwistStamped` current vector on
`/hydrodynamics/current_velocity`, the velocity and horizontal-angle model reads, and the
set-current service that sets velocity, horizontal angle and vertical angle means. The
resolved endpoints come from a shipped world that loads `libdave_ocean_current_plugin.so`
and sets `<namespace>hydrodynamics</namespace>`; a deployment with another namespace or
remapping must expose the same resolved endpoints. Namespace and remapping assumptions are
not upstream facts.

The set-current callback sets model means, not a measured current. Each successful
`SetMean` calls `Reset`, which sets the process variable to the new mean
(`gauss_markov_process.cc:36-50`), and the next world update recomputes the published
vector (`ocean_current_world_plugin.cc:114-129`). `Update` then multiplies the process variable
by `(1 - step * mu)`, adds `noiseAmp` times a uniform draw in [-0.5, 0.5] and clamps it to the
configured range (`gauss_markov_process.cc:75-87`), so with non-zero noise a set mean is only the
starting point. A rejection is partial because the callback uses a short-circuit `&&` chain: for
example, a rejected horizontal angle leaves an accepted velocity mean changed and returns
`success=false`.

These services set only the global constant current. The world plugin also keeps one
Gauss-Markov model set per stratified-database row (`ocean_current_world_plugin.cc:376-411`),
and the ROS plugin republishes the database rows with the tidal data every publish period
(`ocean_current_plugin.cpp:170-254`). Vehicle models that carry DAVE's transient-current model
plugin (for example `rexrov_oberon7_transient_current.xacro:82-104`, with `tide_oscillation`
true) subscribe to that database and compute their own per-vehicle flow topic from the row at
their depth (`ocean_current_model_plugin.cc:209-213`, `309-336`); standard models such as
`rexrov_oberon7.xacro:82-84` read the global `hydrodynamics/current_velocity` topic instead.
The clone is inconsistent about the frame of the vector: `Update`'s comment names NED, while
`Load` and the set services log ENU (`ocean_current_world_plugin.cc:94-96`); the driver passes
`twist.linear` through unchanged.

The vertical get service is advertised with the horizontal-angle callback
(`ocean_current_plugin.cpp:123-127`), so the driver does not expose it. The vertical angle
is visible through the current vector only. The stratified-current topics and services,
the spherical-coordinate interface, robot dynamics, Gazebo stepping, pause and reset are
NOT COVERED.

## Safety

The zero-current action and the e-stop binding send a fixed
`/hydrodynamics/set_current_velocity` request with all three means zero. When the
deployment's configured ranges contain zero, the service returns `success=true` after
resetting the three global process variables; the next world update then computes a zero
global current vector, which stays zero while the velocity `noiseAmp` is zero (the shipped
current-profiling world sets 0). A deployment whose configured model range excludes zero
receives `success=false`; the service predicate then fails, no safe state is claimed and the
latch stays engaged, and the velocity mean may already be zero because of the `&&` chain.

Model review of 2026-11-04: this is a simulated current-forcing stop for the global constant
current only. Vehicles with the transient-current model plugin keep their stratified-database
and tidal current. It does not pause Gazebo, stop a robot or prove that a later world update
ran, and any ROS client can set a new current or model afterwards through the same plugin's
other services (`ocean_current_plugin.cpp:93-163`); the MHS latch refuses only this driver's
commands.

The three set-current inputs are `Limit.operator_required`: the clone reads the model
min/max from the world SDF and states no fixed device bound. `site-limits.example.json`
shows an example-only envelope; it is not a device fact and is not supplied as live
configuration.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS canned-response fake (no
Gazebo physics or current model)`, level F0, determinism `none`, `timestep_ms: 0`,
`realtime_factor: 0`, reset `none`, and no snapshot or restore. The fake answers the
declared topic and services with placeholder vectors and model values. It mirrors the
native short-circuit partial application but runs no Gazebo world, DAVE plugin,
Gauss-Markov process, physics, sensor or wall clock.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `dave`, `underwater`, `ocean-current`
