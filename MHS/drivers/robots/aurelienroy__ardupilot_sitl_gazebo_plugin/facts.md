OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic.

# Facts and tags for gh.aurelienroy/ardupilot_sitl_gazebo_plugin

Every fact cites the pinned clone at commit `75430fbc77967cd0a2e3c429a76b5787a9bff2d1`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The plugin is a Gazebo WorldPlugin registered with GZ_REGISTER_WORLD_PLUGIN. | upstream_code | ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:57 |
| ROS_NAMESPACE is defined as /fdmUDP. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:93 |
| The plugin opens its ROS NodeHandle with ROS_NAMESPACE. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp:45 |
| The plugin advertises the relative take_apm_lapseLock service on its /fdmUDP node handle. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp:77 |
| The plugin advertises the relative release_apm_lapseLock service on its /fdmUDP node handle. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp:78 |
| The TakeApmLapseLock service request has a process_id string and a float32 max_duration; the response has an int32 nb_holders. | upstream_code | ardupilot_sitl_gazebo_plugin/srv/TakeApmLapseLock.srv:1-4 |
| The ReleaseApmLapseLock service request has a process_id string; the response has an int32 nb_holders. | upstream_code | ardupilot_sitl_gazebo_plugin/srv/ReleaseApmLapseLock.srv:1-3 |
| The take service calls take_lapseLock(req.max_duration) and returns _nbHolders_lapseLock. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp:89-95 |
| The release service calls release_lapseLock() and returns _nbHolders_lapseLock. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp:99-105 |
| take_lapseLock sets the lock to the requested duration when it is longer than the current one and increments the holder counter. | upstream_code | ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:283-293 |
| release_lapseLock decrements the holder counter and clears the lock when no holders remain. | upstream_code | ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:300-316 |
| check_lapseLock subtracts loop_elapsed_dt from a held lock and, when the lock falls below zero, sets the lock and the holder count to zero and logs that the simulation resumes. | upstream_code | ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:326-345 |
| The loop passes check_lapseLock the loop duration measured with ros::WallTime. | upstream_code | ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:218-242 |
| While check_lapseLock returns false the loop continues to its next iteration; otherwise it calls receive_apm_input and, when a servo packet arrived, steps Gazebo unless _isSimPaused is set and sends the FDM state. | upstream_code | ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:241-262 |
| init_gazebo_side pauses the Gazebo world. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_gazebo_side.cpp:44-66 |
| step_gazebo_sim advances the world with Step(1); its comment says the simulation must be in pause mode for Step to work. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_gazebo_side.cpp:101-109 |
| on_gazebo_control toggles _isSimPaused on every world_control pause message and calls SetPaused(true) only when the toggle pauses. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_gazebo_side.cpp:136-157 |
| The Cessna spawn launch file includes gazebo_ros empty_world.launch with paused set to true. | upstream_code | ardupilot_sitl_gazebo_plugin/launch/cessna_spawn.launch:53-54 |
| MAX_LAPSE_LOCK_ON_MODEL_INSERT is defined as 5 s. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:112 |
| load_parachute_model inserts the parachute model and takes the lapse lock with MAX_LAPSE_LOCK_ON_MODEL_INSERT. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_parachute.cpp:50-55 |
| on_parachute_model_loaded sets _loop_lapseLock to 0 without touching the holder count when the parachute model is not found. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_parachute.cpp:70-75 |
| on_parachute_model_loaded calls release_lapseLock after attaching the parachute. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_parachute.cpp:106-109 |
| receive_apm_input passes the parachute servo value to check_parachute_cmd. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_apm_side.cpp:141-142 |
| check_parachute_cmd returns for a servo value below 0.5 and otherwise loads the parachute model once. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_parachute.cpp:22-33 |
| The recorder camera plugin's lapse-lock service clients target /fdmUDP/take_apm_lapseLock and /fdmUDP/release_apm_lapseLock. | upstream_code | recorder_camera_plugin/src/recorder_camera_plugin.cpp:134-136 |
| The recorder camera plugin's OnNewFrame, when it saves frames or video, calls its TakeApmLapseLock client with max_duration 5 before and its ReleaseApmLapseLock client after handling the frame. | upstream_code | recorder_camera_plugin/src/recorder_camera_plugin.cpp:181-240 |
| cessna.xacro leaves its recorder_camera instance inside a comment. | upstream_code | ardupilot_sitl_gazebo_plugin/urdf/cessna.xacro:10-24 |
| The header states the lapse lock has no memory or identification of holding processes, can resume before a holder has finished, and is a bounded wall-time pause. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:285-310 |
| The model name defaults to iris. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:85 |
| The plugin reads the SDF UAV_MODEL element into _modelName. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_gazebo_side.cpp:52-53 |
| The LFLY Cessna world sets UAV_MODEL to cessna. | upstream_code | ardupilot_sitl_gazebo_plugin/worlds/LFLY_world_cessna/empty.world:88 |
| LFLY_world_cessna.launch includes cessna_spawn.launch with the LFLY Cessna world. | upstream_code | ardupilot_sitl_gazebo_plugin/launch/LFLY_world_cessna.launch:2-12 |
| empty_world_cessna.launch includes cessna_spawn.launch with the empty_world_cessna world. | upstream_code | ardupilot_sitl_gazebo_plugin/launch/empty_world_cessna.launch:2-12 |
| The empty_world_cessna world loads the plugin without a UAV_MODEL element. | upstream_code | ardupilot_sitl_gazebo_plugin/worlds/empty_world_cessna/empty.world:182 |
| NB_SERVOS_MOTOR_SPEED is defined as 4, commented '4(iris) or 5(cessna)'. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:104 |
| _cmd_motor_speed is declared with NB_SERVOS_MOTOR_SPEED entries and commented as the local copy of the motor speed command in rad/s; _modelName is the next member. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:261-264 |
| The plugin reads the SDF NB_SERVOS_MOTOR_SPEED element into _nbMotorSpeed. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_gazebo_side.cpp:54-55 |
| The LFLY Cessna world sets NB_SERVOS_MOTOR_SPEED to 5. | upstream_code | ardupilot_sitl_gazebo_plugin/worlds/LFLY_world_cessna/empty.world:89 |
| The aircraft plugin stores motor_speed entries 0 to 4 as the aileron, elevator, propeller (divided by 10), rudder and flap commands. | upstream_code | aircraft_plugin/src/aircraft_plugin.cpp:186-193 |
| The aircraft plugin's command indices are Aileron 0, Elevators 1, Propeller 2, Rudder 3 and Flap 4. | upstream_code | aircraft_plugin/include/aircraft_plugin/aircraft_plugin.h:89-93 |
| UpdatePIDs turns the stored aileron, elevator and rudder commands into angles about the value 500, the flap command into an angle from 0 and the propeller command into a throttle of command / 1000. | upstream_code | aircraft_plugin/src/aircraft_plugin.cpp:140-148 |
| The aircraft plugin connects OnUpdate to the world-update-begin event, and OnUpdate calls UpdatePIDs whenever simulation time has advanced. | upstream_code | aircraft_plugin/src/aircraft_plugin.cpp:110-138 |
| The plugin advertises mav_msgs/CommandMotorSpeed on /<modelName>/command/motor_speed with queue size 10. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp:73-74 |
| The Cessna aircraft plugin subscribes to the resolved /cessna/command/motor_speed topic. | upstream_code | ardupilot_sitl_gazebo_plugin/urdf/aircraft_base.xacro:419 |
| The plugin includes the generated mav_msgs/CommandMotorSpeed header. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:52 |
| The published CommandMotorSpeed sets frame_id to quad, stamps the current ROS time and fills motor_speed with the configured number of _cmd_motor_speed entries. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_ros_side.cpp:267-275 |
| receive_apm_input writes each of the first _nbMotorSpeed servo values times 1000 into _cmd_motor_speed and sets every entry to 5, commented as rad/s, when none exceeds 1. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_apm_side.cpp:126-138 |
| The servo packet comment states each servo value ranges from 0 (no rotation) to 1 (full throttle). | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:175-177 |
| The loop calls receive_apm_input only after check_lapseLock returns true. | upstream_code | ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:241-247 |
| receive_apm_input calls publish_commandMotorSpeed only after a complete servo packet is received. | upstream_code | ardupilot_sitl_gazebo_plugin/src/apm_plugin_apm_side.cpp:116-144 |
| MAX_LAPSE_LOCK_DEFAULT is defined as 1 s. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:113 |
| take_lapseLock's default argument is MAX_LAPSE_LOCK_DEFAULT. | upstream_code | ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:146 |
| The repository LICENSE.md says the plugin is licensed under Apache v2.0 terms. | upstream_code | LICENSE.md:1-6 |
| The plugin package.xml gives its licence as TODO. | upstream_code | ardupilot_sitl_gazebo_plugin/package.xml:16 |
| SocketAPM.cpp carries a GNU GPL version 3 or later notice and names Socket.cpp of the ArduPilot project as its source. | upstream_code | ardupilot_sitl_gazebo_plugin/src/SocketAPM.cpp:1-18 |
| The plugin library is built from the plugin sources including src/SocketAPM.cpp. | upstream_code | ardupilot_sitl_gazebo_plugin/CMakeLists.txt:74-83 |

## Scope

This is a configuration-only ROS 1 `RosDriver` over rosbridge. The upstream is a
Gazebo WorldPlugin library; it has no standalone ROS node executable, no Python
native class and no action server. The operator loads the plugin in a Gazebo
world and runs ArduPilot SITL and rosbridge separately.

The package serves only the ROS surface the plugin itself declares:

* `x-cap.aurelienroy.motor_speed.v1`: a fresh subscription to
  `/cessna/command/motor_speed` (`mav_msgs/CommandMotorSpeed`). The endpoint is
  the resolved name of the publisher's `/<modelName>/command/motor_speed` when
  the deployment sets `UAV_MODEL` to `cessna`, as the shipped LFLY Cessna world
  does. Only the LFLY Cessna world (`LFLY_world_cessna.launch`) sets it; the
  iris launch files and `empty_world_cessna.launch` load worlds without
  `UAV_MODEL`, where the plugin publishes `/iris/command/motor_speed`. The
  entries are the SITL servo values times 1000; the upstream comments call
  them rad/s, but the Cessna aircraft plugin reads entries 0 to 4 as aileron,
  elevator, propeller (divided by 10), rudder and flap commands, so the output
  declares no unit.
* `x-cap.aurelienroy.take_lapse_lock.v1` and
  `x-cap.aurelienroy.release_lapse_lock.v1`: the acknowledged
  `/fdmUDP/take_apm_lapseLock` and `/fdmUDP/release_apm_lapseLock` services.
  Both actions are input-free. The take request uses the upstream
  `take_lapseLock` method default horizon of 1 s
  (`MAX_LAPSE_LOCK_DEFAULT`), because the service itself takes the caller's
  `max_duration`; the driver does not invent a new horizon. The actions report
  the returned `nb_holders` and require the exact count this driver expects:
  take succeeds only at 1 and release only at 0. A higher count means another
  holder remains; it is reported as an application failure, not mistaken for
  this driver's own pause or release.

The SITL UDP bridge, FDM state, servo packets, sensor subscriptions, parachute
path, Gazebo stepping, rotor dynamics, the `aircraft_plugin` consumers and the
`recorder_camera_plugin` are NOT COVERED. A read while the lapse lock is held
gets no fresh motor-speed sample and fails at its deadline; the fake models
that observation but never claims a stopped device.

## Safety

The device is simulated at R0. The only native pause is the wall-time lapse
lock. The upstream header states it has no memory or identification of the
holding processes and can resume the simulation before a holder has finished
(`ardupilot_sitl_gazebo_plugin/include/ardupilot_sitl_gazebo_plugin/ardupilot_sitl_gazebo_plugin.h:285-310`);
`check_lapseLock` clears it automatically when the timer expires
(`ardupilot_sitl_gazebo_plugin/src/ardupilot_sitl_gazebo_plugin.cpp:326-345`).

The e-stop binding is the take service with a fixed `max_duration` equal to
the maximum finite value of the declared `float32` field
(`ardupilot_sitl_gazebo_plugin/srv/TakeApmLapseLock.srv:2`), so the upstream
wall-time timer does not expire in a realistic deployment. The ordinary take
action keeps the upstream method default horizon of 1 s. The maximum-float32
request is a driver request choice, not a device safety limit.

The plugin runs Gazebo in lock-step: it pauses the world when it loads
(`apm_plugin_gazebo_side.cpp:66`) and advances it only with `Step(1)` from its
loop after a servo packet (`apm_plugin_gazebo_side.cpp:101-109`,
`ardupilot_sitl_gazebo_plugin.cpp:241-262`). While the lock is held the loop
receives no servo packets, publishes no motor speeds, sends no FDM state and
does not step the world, so the simulated aircraft is frozen as long as no
other client unpauses Gazebo; in an unpaused world the aircraft plugin keeps
applying the last stored command at every world update. The e-stop does not
stop the ArduPilot SITL process. It is not an independent stop: the holder
counter has no process identity, and any release that brings it to zero
resumes the loop, including the release of a holder whose own lock expired
(expiry zeroes the count), the plugin's parachute path (a 5 s take released
after the model loads; a failed load zeroes the lock directly) and the recorder
camera plugin when it saves frames (not instantiated by `cessna.xacro`).

The take is not idempotent: every call adds a holder, and the bindings accept
only `nb_holders` exactly 1 (the binding grammar has no lower-bound test). A
reviewer probe showed one take for an idle e-stop and none on reset (reset does
not resume the loop; `release_lapse_lock` is the separate, explicit resume). A
second e-stop while latched, an e-stop within 1 s of an ordinary take, another
holder or a lost take response make the e-stop report `SAFE_STATE_UNREACHED`
with the latch held although the loop is paused, and every background retry
then takes the lock again until a reset, so resuming needs one release per
take. The MHS software latch refuses this driver's own take/release commands
after the e-stop. No physical e-stop, hardware run, torque-off or independent
stopped-state proof is claimed.

The package is model-authored and unreviewed (`reviewed_by` stays null); the
loader refuses the hardware backend of an unreviewed model-written package at
R2 and R3, and RosDriver refuses every hardware backend without a human
hardware review, so no hardware path is claimed here.

## Fidelity contract

`driver.py` describes the deployed fake: engine
`analytic:ROS-free recording fake for the ArduPilot SITL Gazebo ROS surface (no physics)`,
level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, no snapshot/restore. The fake is event-driven and has no
Gazebo step, ArduPilot SITL process, UDP socket or wall-clock pacing. It keeps
its placeholder lapse lock held until release or a test reset; it does not run
the upstream elapsed-wall-time expiry. The plugin's 2.5 ms SITL step and loop
rates remain source facts, not fake timing. The gaps list these limits and the
placeholder state.

## Limits

No `Limit` is declared: the exposed actions have no numeric caller input and
the observation has no sourced bound. The e-stop's fixed maximum-float32
horizon is a request value derived from the declared field type, not a `Limit`
or a device bound. `site-limits.example.json` is therefore
not needed. The 1 s pause horizon is the upstream method default used to fill
the service's required `max_duration`, not a device safety limit.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `ardupilot`, `sitl`, `motor-speed`,
`lapse-lock`

## Model review (wave C)

A model review (not a human review; `reviewed_by` stays null) corrected three
facts that said more than their lines, removed the rad/s unit from the
observation, rewrote `safe_state`, and added source facts and gaps for the
lock-step world, the lock-clearing paths, the non-idempotent take, the
deployment that matches the bound topic, two upstream defects at the pin and
the licence conflict. Upstream defects at the pin: the LFLY Cessna world sets
`NB_SERVOS_MOTOR_SPEED` to 5 while `_cmd_motor_speed` has 4 entries, so the
plugin writes and reads a fifth entry past the array (the next member is
`_modelName`); `empty_world_cessna` loads the plugin without `UAV_MODEL`, so
the Cessna there listens on a topic the plugin does not publish. Licence:
`LICENSE.md` says Apache v2.0, the plugin `package.xml` says TODO, and
`SocketAPM.cpp`, compiled into the plugin library, carries a GPL-3.0-or-later
notice from ArduPilot; the owner decides publication.
