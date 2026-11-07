# Facts and tags for gh.alexanderkeijzer/ros-gym-env-webots

Every fact cites the pinned clone at commit `6cc613bdee4bad0adb157230df51a9bacdf621e4`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The node includes the gym_env RegisterSpaces, SensorMessage, ActuatorMessage, CloseEnv, ResetEnv, StepEnv and GetReward headers together with the webots_ros get_bool, get_float, set_int, set_float and Float64Stamped headers. | upstream_code | src/gym_env_webots_node.cpp:9-21 |
| MOTOR_NUMBER is 9. | upstream_code | src/gym_env_webots_node.cpp:25 |
| The motor_names array names the seven Panda arm joints and the two finger joints in the order panda_joint1 through panda_joint7 followed by panda_finger_joint1 and panda_finger_joint2. | upstream_code | src/gym_env_webots_node.cpp:44-46 |
| sensorCallback stores each Float64Stamped value in sensor_values and publishes a SensorMessage carrying all nine values. | upstream_code | src/gym_env_webots_node.cpp:58-63 |
| initSensors calls each <model>/<joint>_sensor/enable service with value 80 and, when the call succeeds, subscribes to that sensor's Float64Stamped value topic and busy-waits until the subscription has a publisher. | upstream_code | src/gym_env_webots_node.cpp:65-79 |
| sensorSpacesCallback returns motorMin-2e-5 as low, motorMax+2e-5 as high and the topic /joint_sensors/value. | upstream_code | src/gym_env_webots_node.cpp:94-99 |
| actuatorSpacesCallback returns a nine-element action space with low -1.0 and high 1.0 and the topic /joint_actuators/value. | upstream_code | src/gym_env_webots_node.cpp:108-113 |
| actuatorCommandCallback adds motorRange[i]*actions[i]/20 to each setpoint, clamps the setpoint to [motorMin[i], motorMax[i]] and calls the joint set_position service. | upstream_code | src/gym_env_webots_node.cpp:117-125 |
| initActuators reads each joint's get_max_position and get_min_position, stores max-1e-5 and min+1e-5, and computes range as max-min. | upstream_code | src/gym_env_webots_node.cpp:127-142 |
| stepCallback calls the stepEnv client with no retry limit until a call succeeds with response.success, and then returns true. | upstream_code | src/gym_env_webots_node.cpp:144-164 |
| resetCallback returns false unless the resetEnv get_bool call succeeds with value true; it then calls stepEnv with value 8 once, ignoring the result, calls it again until one call succeeds, sleeping 0.5 s after each failure, calls initSensors and returns true. | upstream_code | src/gym_env_webots_node.cpp:171-195 |
| closeCallback logs Close and returns true without calling any device method. | upstream_code | src/gym_env_webots_node.cpp:166-169 |
| rewardCallback computes the negative sum over the nine joints of the distance from each joint position to the middle of its range and returns it in response.reward. | upstream_code | src/gym_env_webots_node.cpp:197-208 |
| main creates the reset client on <model>/supervisor/simulation_reset and the step client on <model>/robot/time_step, and sets the step request value to 80 ms. | upstream_code | src/gym_env_webots_node.cpp:241-243 |
| The node advertises /joint_sensors, /joint_actuators, /webots/step, /webots/close, /webots/reset and /reward. | upstream_code | src/gym_env_webots_node.cpp:250-256 |
| The node subscribes /joint_actuators/value and advertises /joint_sensors/value. | upstream_code | src/gym_env_webots_node.cpp:258-259 |
| main subscribes /joint_actuators/value with a queue size of 1, advertises /joint_sensors/value with a queue size of 1 and then calls ros::spin(). | upstream_code | src/gym_env_webots_node.cpp:258-265 |
| The launch file includes webots_ros webots.launch in realtime mode with the panda.wbt world and starts the gym_env_webots_node executable. | upstream_code | launch/webots_p-rob3.launch:5-13 |
| The Panda world fixes basicTimeStep to 8 ms and instantiates the Panda robot with controller "ros". | upstream_code | worlds/panda.wbt:8-64 |
| The Panda robot runs the ros controller with the --synchronize controller argument and supervisor TRUE. | upstream_code | worlds/panda.wbt:61-68 |
| The Panda PROTO declares synchronization with the default TRUE. | upstream_code | protos/Panda.proto:15 |
| motorSetPoints is a global array initialised to zero. | upstream_code | src/gym_env_webots_node.cpp:31 |
| The Panda PROTO declares panda_finger_joint1 as a LinearMotor with maxPosition 0.04. | upstream_code | protos/Panda.proto:1348-1351 |
| The Panda PROTO declares panda_finger_joint2 as a LinearMotor with maxPosition 0.04. | upstream_code | protos/Panda.proto:1413-1416 |
| package.xml declares build/exec dependencies on gym_env, roscpp, std_msgs and webots_ros. | upstream_code | package.xml:52-63 |

## Scope

The package exposes the node's own ROS 1 surface over rosbridge. The primary command is one environment step as the
node's gym_env client performs it, `x-cap.alexanderkeijzer.action_step.v1` (a RosDriver publish-then-step command,
repair 2026-11-05): it publishes the action vector on `/joint_actuators/value`, whose callback increments each motor
setpoint by `motorRange*action/20`, clamps it to the joint limits and calls the joint's `set_position`
(`src/gym_env_webots_node.cpp:117-125`); then it calls `/webots/step` once (`:144-164`, `:253`); then it reads one
fresh `gym_env/SensorMessage` sample on `/joint_sensors/value` (`:259`) on a subscription opened after the step was
acknowledged. The receipt reports `published=true`, `confirmed=false` (the publication itself is never acknowledged),
`stepped=true` and the nine positions. Every failure after the publication (a failed, refused, unanswered or
interrupted step, no sample in time, a result that cannot be mapped) is an unknown outcome: the node keeps the
incremented setpoints, so a retry is not the same command. Whether webots_ros publishes a sensor sample after the
step's reply is outside the clone; when none arrives within 2 s the receipt is unknown. The order in which the node
handles the publication and the step is not guaranteed: rosbridge forwards them over different ROS connections (its
publisher of `/joint_actuators/value` and its `/webots/step` service client), and the node serves the subscription
(queue size 1) and the step service from one `ros::spin()` (`:253`, `:258`, `:265`). The step may therefore run before
`actuatorCommandCallback`, and the first action after rosbridge advertises the topic may be lost before the node's
subscription connects; a completed receipt's observation need not reflect the action (only `confirmed=false` says
the publication is unacknowledged). The fake's `action_after_step` switch reproduces the first case. The positions are seven arm joint angles (RotationalMotor, radians)
and two finger joint positions (LinearMotor, `protos/Panda.proto:1348-1351`, `:1413-1416`), so the array declares no
single unit. A separate `/webots/step` call, the `/reward` service's `response.reward` scalar and a plain joint sample
remain available; the `/webots/step` call acknowledges that the Webots robot/time_step client returned success and
returns no observation, reward or termination flag.

The `gym_env` message and service definitions live in the external `gym_env` package, which the
pinned clone only declares as a dependency (`package.xml:52-63`) and imports in the node
(`src/gym_env_webots_node.cpp:15-21`). The response fields of `StepEnv` and `ResetEnv` are not
defined in this clone; the callbacks return a boolean and never read or write a response field
(`src/gym_env_webots_node.cpp:144-164`, `171-195`). The declared empty-response application
predicate is therefore the expected empty-values contract, not a field copied from an upstream
definition.

## Limits

The only numeric input is the nine-element action vector. `actuatorSpacesCallback` declares the
normalized action space low `-1.0` and high `1.0` (`src/gym_env_webots_node.cpp:108-113`). The
callback does not itself reject an action outside that space; it scales the value into a setpoint
and clamps the setpoint to the joint range (`117-125`). The declared envelope is therefore the
action-space contract the node advertises to its gym_env client. The action array length 9 comes
from `MOTOR_NUMBER` (`25`) and the nine motor names (`44-46`).

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free fake of the node's setpoint arithmetic (no Webots
physics)`, level F0, determinism `none`, `timestep_ms: 0` (event-driven canned replies), and `realtime_factor: 0` (not
paced). The upstream world sets `basicTimeStep 8` and the node requests an 80 ms step (`worlds/panda.wbt:8`,
`src/gym_env_webots_node.cpp:243`); those are source facts about the upstream, not fake timing. An action publication
updates the fake's copy of the node's setpoints exactly as `actuatorCommandCallback` does, with placeholder joint
limits copied from the Panda PROTO (finger minimum 0, not stated there), before the next step (the
`action_after_step` switch applies it after the step instead, the live ordering hazard of the Scope section); a fake
step moves every joint to its last target in one step (placeholder dynamics: real joints move under their motor limits over many 8 ms steps); a reset
restores placeholder start positions and keeps the node's setpoints, as `resetCallback` keeps `motorSetPoints`. The
reward is a placeholder. No Webots engine, controller, physics or pacing runs.

## Safety

The device is simulated at R2 because the action capability moves a robot arm; the card floor is
R0. `x-cap.alexanderkeijzer.reset.v1` is the declared input-free safe-state action. Its callback
asks the Webots supervisor to reset the simulation and returns false unless that call reports
success, then calls the 8 ms time_step once (ignoring the result) and again until a call succeeds,
sleeping 0.5 s after each failure, and re-enables the sensors (`src/gym_env_webots_node.cpp:171-195`).
It is not a Webots process stop, it does not cancel an already queued `/webots/step` request, and
it does not fence other ROS clients that can still publish on `/joint_actuators/value`. No
independent hardware emergency stop exists or is claimed. The runtime latches in software and runs
the safe-state action; after the e-stop, agent commands are refused while latched.

Model review (2026-11-05): the author's text said the reset "requests one 8 ms time_step" and
"restores the initial simulated world". At least two time_step calls run, and what Webots restores
on `simulation_reset` is Webots behaviour outside the clone. The reset is kept as the safe-state
action because the Panda runs the `ros` controller with `--synchronize` (`worlds/panda.wbt:61-68`;
`Panda.proto:15` defaults `synchronization` to TRUE), the configuration in which the world advances
only on time_step calls, and MHS sends none after the latch. The reset does not clear the node's
`motorSetPoints` (`src/gym_env_webots_node.cpp:31`, `:117-125`), so the first action after it
continues from the pre-reset setpoints, and its unbounded retry loops (`:171-195`, `:65-79`) can
outlast the 2 s default binding timeout, in which case the e-stop reports `SAFE_STATE_UNREACHED`.

Repair (2026-11-05), act and step: an e-stop that lands after the action was published and before the step keeps
the step from being sent (the command's receipt is unknown); the setpoints the callback already incremented and the
`set_position` targets it sent stay in place until the reset, and the synchronized world does not advance on them
while MHS sends no time_step. An e-stop that lands while a step is unanswered (in flight, or timed out and never
answered) still calls `/webots/reset`, but reports the safe state unreached until that step's reply has arrived (the
SDK keeps the safe state unachieved while an effectful call it sent is unsettled); if no reply ever arrives, every
later e-stop on that connection reports it unreached. A step that was sent and not answered in time is retained on the
rosbridge connection: because this package's stop is a safe-state Action rather than a `safety_bindings` stop, the
SDK's reset then stays refused on that connection even after the late reply and a confirmed safe state (an SDK
limitation recorded in `MHS/changes/ROS-PUBLISH-STEP-AND-MVSIM.md`; it fails safe: the latch holds).

The `/webots/close` callback is not a stop: it logs `Close` and returns true without calling any
device method (`src/gym_env_webots_node.cpp:166-169`).

## Tags

`ros`, `ros1`, `webots`, `simulation`, `gym`, `panda`, `robot-arm`, `joint-action`
