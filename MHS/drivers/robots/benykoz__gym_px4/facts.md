# Facts and tags for gh.benykoz/gym_px4

Every fact cites the pinned clone at commit `d53a9d47030d7ca3132747527d66f9a097fd0986`.
`upstream_code` refs name `path/in/clone:LINE`; `vendor_doc` refs name a text
file of the clone. The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| README describes gym-px4 as an openai/gym environment for PX4 Gazebo SITL using MAVROS. | vendor_doc | README.md:2 |
| The package registers the Gym environment id px4-v0 with entry point gym_px4.envs:gymPX4. | upstream_code | gym_px4/__init__.py:3-6 |
| gymPX4 subclasses gym.Env. | upstream_code | gym_px4/envs/gymPX4_env.py:52 |
| The action space is a one-value Box whose low is 0.0 and high is 1.0. | upstream_code | gym_px4/envs/gymPX4_env.py:57-69 |
| The observation space is a two-value Box from [0.1, -3] to [25, 3]. | upstream_code | gym_px4/envs/gymPX4_env.py:60-71 |
| The constructor creates publishers on /mavros/setpoint_position/local, /mavros/mocap/pose, /mavros/actuator_control, /mavros/setpoint_raw/attitude and /mavros/setpoint_attitude/thrust. | upstream_code | gym_px4/envs/gymPX4_env.py:105-109 |
| The constructor calls init_env, which initializes the anonymous ROS node gym_px4_mavros; it waits for the mavros/cmd/arming, mavros/set_mode and mavros/set_stream_rate services with no timeout argument, calls set_stream_rate for STREAM_POSITION and STREAM_ALL with the arguments 50 and 1, and calls offb_arm. | upstream_code | gym_px4/envs/gymPX4_env.py:114-139 |
| offb_arm calls set_mode with custom mode OFFBOARD and then the arming service with True, and checks neither response. | upstream_code | gym_px4/envs/gymPX4_env.py:294-311 |
| reset sets success_steps and steps to 0. | upstream_code | gym_px4/envs/gymPX4_env.py:143-146 |
| reset fixes desired and initial at 2 and then loops with no bound: it calls offb_arm whenever the stored state reports the vehicle disarmed, publishes the reset position with local_pos_pub and sleeps 0.5 s until the altitude error and the speed are below 0.2; it returns [desired - z, vz]. | upstream_code | gym_px4/envs/gymPX4_env.py:152-198 |
| Before publishing, step loops with no bound and no sleep until the local-position z differs from the last stored z. | upstream_code | gym_px4/envs/gymPX4_env.py:215-222 |
| step sets a type mask that ignores the three body rates and the attitude, assigns the action to the attitude target's thrust, publishes it with setpoint_raw_pub, computes reward -(desired - z)^2, and returns the two-value observation, reward, done and info. | upstream_code | gym_px4/envs/gymPX4_env.py:239-292 |
| step sets done on \|x\| > 2, \|y\| > 2, z > 3 or z < 1 (reward -1000), on a step count above 5000, or when success_steps, incremented on every step with \|desired - z\| < 0.1, exceeds 50 (reward + 10000). | upstream_code | gym_px4/envs/gymPX4_env.py:257-274 |
| step creates rospy.Rate(20) when it starts. | upstream_code | gym_px4/envs/gymPX4_env.py:202-203 |
| step sleeps until 0.03 s have passed since it started and then calls rate.sleep(). | upstream_code | gym_px4/envs/gymPX4_env.py:280-287 |
| render and close do nothing. | upstream_code | gym_px4/envs/gymPX4_env.py:313-317 |
| README says to run Gazebo with the PX4 ROS wrappers and then roslaunch mavros px4.launch with fcu_url udp://:14540@127.0.0.1:14557. | vendor_doc | README.md:30-31 |
| README documents a four-value action space: thrust[0..1], roll[-1..1], pitch[-1..1], yaw[-1..1]. | vendor_doc | README.md:57 |
| README documents gym.make('gym_px4:px4-v0'), env.reset() and env.step(action). | vendor_doc | README.md:38-42 |

## Scope and deviation from the card

The card names family `ros` and helper `RosDriver`, but the confirmed entry
symbol is a `gym.Env` subclass and its primary interface is `reset()` /
`step(action)`. The package therefore uses `GymnasiumDriver` (DEVIATION FROM
THE CARD) and serves `cap.world.step.v1`, `cap.world.reset.v1` and
`cap.world.seed.v1`. The ROS topics, MAVROS services, arming sequence and
setpoint publishers in the constructor are evidence of the upstream
simulator wiring; they are not exposed as a ROS transport by this package.

The upstream action space in code is a single thrust value
(`gym_px4/envs/gymPX4_env.py:57-69`), while README.md:57 documents four
action values. The driver and fake follow the code, because that is the
`spaces.Box` the environment actually constructs.

## Limits and provenance

`GymnasiumDriver` declares no `Limit` for the world step; the bridge derives
`action.values` from the environment's action space. The fake copies the
upstream one-value Box, so `action_space_ref` cites
`gym_px4/envs/gymPX4_env.py:57-69`, the span that defines `min_action = 0.0`,
`max_action = 1.0` and the `Box(low=self.min_action, high=self.max_action,
shape=(1,))`. Ticks are bounded by the catalogue class and bridge (1..10000).
The environment uses fixed desired/initial values and has no operator-tunable
numeric input, so the package declares no operator-required limit and writes
no site-limits example.

## Fidelity contract

`driver.py` describes the deployed fake: F0, an analytic vertical-altitude
stand-in with `timestep_ms: 0` (one step is one environment transition, not a
physics tick), `realtime_factor: 0` (not paced), lockstep clock, full reset
and no snapshot/restore. Its gaps disclose that no PX4, Gazebo, MAVROS, ROS
graph, physics, contacts, sensors or wall-clock loop is loaded; that x and y
stay at zero; that the upstream reset loop is unbounded and the constructor
arms the vehicle, while the fake returns immediately and arms nothing; and
that the seed endpoint is accepted but does not change the deterministic
fake or the fixed upstream reset.

## Safety

The device risk is R2 (REVIEW.md item 12), a vehicle in flight. `step` publishes
an `AttitudeTarget` thrust on `/mavros/setpoint_raw/attitude` (`gymPX4_env.py:239-248`),
the constructor also publishes the other MAVROS setpoint topics (`gymPX4_env.py:105-109`),
and `offb_arm` sets OFFBOARD and arms (`gymPX4_env.py:294-311`). `README.md:30-31` points
`fcu_url` at SITL; the environment does not, and no fact cites that only a simulator
consumes those setpoints. There is no hardware backend. The bridge latches a software
e-stop and refuses further step, reset and seed commands; the last observation and tick
stay readable. The latch calls nothing upstream, so it does not land or disarm a vehicle
on those topics, including a physical PX4. A normal safe-state invocation does not
engage the latch. The fake is not a physical emergency stop and makes no
hardware-safety claim.

Model review (2026-11-05): the e-stop calls nothing upstream, and the upstream
`close()` does nothing. A live PX4 SITL keeps running: nothing lands or
disarms the quadcopter that the upstream constructor and `reset` armed and
switched to OFFBOARD, and what PX4 does when the thrust setpoints stop is PX4
configuration outside the clone. The upstream environment cannot tell SITL
from a real vehicle: it arms whatever flight controller MAVROS is connected to
and re-arms a disarmed vehicle on every `reset`; only the README points MAVROS
at the SITL port. Constructing it in the server process would also call
`rospy.init_node`, wait for MAVROS services without a timeout, busy-wait in
`step` until the altitude changes, and print to standard output.

## Tags

`gym`, `gymnasium`, `px4`, `mavros`, `sitl`, `gazebo`, `simulation`,
`quadcopter`
