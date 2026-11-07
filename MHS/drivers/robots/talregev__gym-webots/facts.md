OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.talregev/gym-webots

Every fact cites its source at commit `023ae0bebd8067ea8c7fbb4b84b31ae29a9fb9f3`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written into
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; `reference.json` and `REFERENCE.md` are generated
from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| WebotsCircuit2cPionner3atCameraNnEnv is defined in the pioneer package and extends webots_env.WebotsEnv | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:28 |
| The package registers the environment id WebotsCircuit2cPioneerCameraNnEnv-v0 | upstream_code | gym_webots/__init__.py:10 |
| The registered entry point is gym_webots.envs.pioneer:WebotsCircuit2cPionner3atCameraNnEnv | upstream_code | gym_webots/__init__.py:11 |
| WebotsEnv subclasses gym.Env | upstream_code | gym_webots/envs/webots_env.py:13 |
| WebotsEnv.__init__ starts roscore and Webots with subprocess.Popen and initializes a ROS node named gym | upstream_code | gym_webots/envs/webots_env.py:58-70 |
| A relative world file is resolved under gym_webots/envs/assets/worlds | upstream_code | gym_webots/envs/webots_env.py:50-56 |
| The pioneer environment passes pioneer3at-circle.wbt to WebotsEnv | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:32 |
| The environment holds the wheel motor names front_left_wheel, front_right_wheel, back_left_wheel and back_right_wheel | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:34 |
| The environment creates ROS service proxies for simulation_reset, robot/time_step, simulation_set_mode, camera/enable and Sick_LMS_291/enable | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:36-41 |
| For every wheel the environment creates set_velocity and set_position service proxies of type set_float | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:45-56 |
| The environment switches Webots to run mode by calling the simulation_set_mode proxy with 1 | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:59 |
| The basic time step is read from the robot/get_basic_time_step service and stored in TIME_STEP | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:62-65 |
| The camera observation parameters are img_rows 32, img_cols 32 and img_channels 1 | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:73-75 |
| calculate_observation marks done when a LaserScan range is greater than 0 and less than 0.21 | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:77-83 |
| enable_sensors calls the camera and lidar enable proxies with TIME_STEP | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:89-97 |
| enable_motors calls every set_position proxy with float infinity | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:99-103 |
| stop_robot calls every set_velocity proxy with 0 | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:105-109 |
| step implements three actions: 0 forward, 1 right and 2 left; forward calls all four velocity proxies with 6, a right turn calls the left wheels with 6 and the right wheels with 0.3, and a left turn calls the left wheels with 0.3 and the right wheels with 6 | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:123-139 |
| step does not advance the simulation itself: the step_sim call is commented out and step waits for a LaserScan on /pioneer3at/Sick_LMS_291/laser_scan/layer0 and a camera Image on /pioneer3at/camera/image with a timeout of 5 seconds | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:141-169 |
| step updates a 50-entry last50actions history with 0 for forward and 1 otherwise | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:172-178 |
| The reward is computed from left and right sums of the LaserScan ranges and a center-detour term, and is -1 when the observation marks done | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:196-212 |
| step converts the camera frame to grayscale, resizes it to img_rows by img_cols, reshapes it to (1, 1, rows, cols) and returns (state, reward, done, {}) | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:220-227 |
| reset calls the simulation_reset proxy with 1, sleeps 1 second, then enables the sensors, stops the robot and enables the motors | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:239-247 |
| reset returns the resized camera state alone, not an observation/info pair | upstream_code | gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py:273-279 |

## Scope and shape

The served device is the Gymnasium environment `WebotsCircuit2cPioneerCameraNnEnv-v0`: `cap.world.step.v1`
(ticks plus the discrete action), `cap.world.reset.v1` and `cap.world.seed.v1`. The card listed `RosDriver`, but
the entry symbol is a legacy `gym.Env`; its public interface is `reset()` and `step(action)`, and ROS is the
environment's internal transport to Webots. The family driver is therefore `GymnasiumDriver` (a recorded
deviation from the card), and the class keeps the card's entry symbol as `native`.

The upstream class defines no `action_space` or `observation_space`; the three actions are equality checks in
`step` (0 forward, 1 right, 2 left) and the observation is the 1 x 1 x 32 x 32 grayscale frame. The fake declares
`Discrete(3)` and a matching `Box` as placeholders and sets no `action_space_ref`, because no upstream line
defines a space. The derived step limits are therefore the fake's, not upstream facts.

## Fidelity contract

The deployed backend is the package's analytic fake, level F0: no Webots engine, no ROS graph, no camera or
LaserScan, synthetic pixels and reward, `timestep_ms: 0`, `realtime_factor: 0`, seeded determinism with the seed
a parameter, full reset from the fake's own state, and no snapshot/restore. The upstream `TIME_STEP` is read at
run time from the `robot/get_basic_time_step` service, so no fixed upstream timestep is claimed.

## Safety

The device is simulated at R0. There is no hardware stop to cite; an e-stop is the runtime's software latch.
After it the runtime refuses `cap.world.step.v1`, `cap.world.reset.v1` and `cap.world.seed.v1` until
`mhs.safety.reset` clears the latch, while `mhs.resource.read` stays available. The fake has no physical stop
and makes no hardware or live-simulation claim; `driver.lock.json` keeps `reviewed_by: null`.

Tags: webots, ros, pioneer3at, camera, reinforcement-learning, simulation, gym
