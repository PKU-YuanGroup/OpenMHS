"""OpenMHS driver for gh.benykoz/gym_px4, a legacy Gym PX4 SITL environment.

The card names the ROS family and ``RosDriver``, but the confirmed entry
symbol is ``gym_px4.envs.gymPX4_env:gymPX4`` (``gymPX4_env.py:52``), a
``gym.Env`` subclass registered as ``px4-v0`` (``gym_px4/__init__.py:3-6``).
Its primary interface is ``reset()`` / ``step(action)``, not a ROS topic or
service surface, so this package is a configuration-only
:class:`GymnasiumDriver` (DEVIATION FROM THE CARD: GymnasiumDriver instead of
RosDriver).  The environment's ROS topics, services and MAVROS arm sequence
are evidence of how the upstream simulator is wired, not a transport this
package drives.

The package serves the three simulator capabilities the family derives:
``cap.world.step.v1`` (``{ticks, action}`` with the one-value thrust action
space), ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  It declares only the
fake backend, a pure-Python stand-in for the legacy Gym methods (a fake-only
contract).  Constructing the upstream environment needs a live ROS 1 MAVROS
graph and was not done: it initializes a ROS node in the host process, arms
whatever PX4 flight controller MAVROS is connected to and requests OFFBOARD,
and its reset re-arms a disarmed vehicle; nothing in it tells PX4 SITL from a
real vehicle.  An MHS e-stop is a software latch only and calls nothing
upstream.  Every source reference is from the pinned clone at
d53a9d47030d7ca3132747527d66f9a097fd0986.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_px4/envs/gymPX4_env.py"


class GymPx4(GymnasiumDriver):
    device_id = "gym-px4"
    device_kind = "world.sim"
    mode = "simulated"
    # R2, not R0 (grok-4.7, 2026-11-05; REVIEW.md item 12): the constructor
    # publishes on /mavros/setpoint_raw/attitude and the other MAVROS setpoint topics
    # (gymPX4_env.py:105-109), step assigns the action to AttitudeTarget.thrust and
    # publishes it (gymPX4_env.py:239-248), and offb_arm sets OFFBOARD and arms
    # (gymPX4_env.py:294-311). README.md:30-31 points fcu_url at SITL; the environment
    # does not. No fact cites that only a simulator consumes those setpoints. A vehicle
    # in flight is R2 however simulated the deployment. The latch calls nothing upstream.
    risk = "R2"
    env_id = "px4-v0"
    native = "gym_px4.envs.gymPX4_env:gymPX4"
    backends = {"fake": ".fake:FakeGymPx4"}
    #: The fake copies the one-value thrust Box from the upstream constructor.
    action_space_ref = f"{ENV}:57-69"
    display_name = "gym_px4 PX4 Gazebo SITL environment"
    vendor = "benykoz"
    model = "px4-v0"
    tags = ["gym", "gymnasium", "px4", "mavros", "sitl", "gazebo", "simulation", "quadcopter"]
    facts = [
        Fact("README describes gym-px4 as an openai/gym environment for PX4 Gazebo SITL using MAVROS.",
             source="vendor_doc", ref="README.md:2"),
        Fact("The package registers the Gym environment id px4-v0 with entry point gym_px4.envs:gymPX4.",
             source="upstream_code", ref="gym_px4/__init__.py:3-6"),
        Fact("gymPX4 subclasses gym.Env.", source="upstream_code", ref=f"{ENV}:52"),
        Fact("The action space is a one-value Box whose low is 0.0 and high is 1.0.",
             source="upstream_code", ref=f"{ENV}:57-69"),
        Fact("The observation space is a two-value Box from [0.1, -3] to [25, 3].",
             source="upstream_code", ref=f"{ENV}:60-71"),
        Fact("The constructor creates publishers on /mavros/setpoint_position/local, /mavros/mocap/pose, "
             "/mavros/actuator_control, /mavros/setpoint_raw/attitude and /mavros/setpoint_attitude/thrust.",
             source="upstream_code", ref=f"{ENV}:105-109"),
        Fact("The constructor calls init_env, which initializes the anonymous ROS node gym_px4_mavros; it waits "
             "for the mavros/cmd/arming, mavros/set_mode and mavros/set_stream_rate services with no timeout "
             "argument, calls set_stream_rate for STREAM_POSITION and STREAM_ALL with the arguments 50 and 1, "
             "and calls offb_arm.", source="upstream_code", ref=f"{ENV}:114-139"),
        Fact("offb_arm calls set_mode with custom mode OFFBOARD and then the arming service with True, and "
             "checks neither response.", source="upstream_code", ref=f"{ENV}:294-311"),
        Fact("reset sets success_steps and steps to 0.", source="upstream_code", ref=f"{ENV}:143-146"),
        Fact("reset fixes desired and initial at 2 and then loops with no bound: it calls offb_arm whenever "
             "the stored state reports the vehicle disarmed, publishes the reset position with local_pos_pub "
             "and sleeps 0.5 s until the altitude error and the speed are below 0.2; it returns "
             "[desired - z, vz].", source="upstream_code", ref=f"{ENV}:152-198"),
        Fact("Before publishing, step loops with no bound and no sleep until the local-position z differs from "
             "the last stored z.", source="upstream_code", ref=f"{ENV}:215-222"),
        Fact("step sets a type mask that ignores the three body rates and the attitude, assigns the action to "
             "the attitude target's thrust, publishes it with setpoint_raw_pub, computes reward "
             "-(desired - z)^2, and returns the two-value observation, reward, done and info.",
             source="upstream_code", ref=f"{ENV}:239-292"),
        Fact("step sets done on |x| > 2, |y| > 2, z > 3 or z < 1 (reward -1000), on a step count above 5000, "
             "or when success_steps, incremented on every step with |desired - z| < 0.1, exceeds 50 "
             "(reward + 10000).", source="upstream_code", ref=f"{ENV}:257-274"),
        Fact("step creates rospy.Rate(20) when it starts.", source="upstream_code", ref=f"{ENV}:202-203"),
        Fact("step sleeps until 0.03 s have passed since it started and then calls rate.sleep().",
             source="upstream_code", ref=f"{ENV}:280-287"),
        Fact("render and close do nothing.", source="upstream_code", ref=f"{ENV}:313-317"),
        Fact("README says to run Gazebo with the PX4 ROS wrappers and then roslaunch mavros px4.launch with "
             "fcu_url udp://:14540@127.0.0.1:14557.", source="vendor_doc", ref="README.md:30-31"),
        Fact("README documents a four-value action space: thrust[0..1], roll[-1..1], pitch[-1..1], "
             "yaw[-1..1].", source="vendor_doc", ref="README.md:57"),
        Fact("README documents gym.make('gym_px4:px4-v0'), env.reset() and env.step(action).",
             source="vendor_doc", ref="README.md:38-42"),
    ]
    safe_state = ("Software latch only: the runtime refuses every step, reset and seed until mhs.safety.reset and "
                  "the fake stops advancing with its last observation readable; nothing upstream is called "
                  "(gymPX4.close() does nothing), so nothing lands or disarms the quadcopter the constructor and "
                  "reset armed in OFFBOARD, including a physical PX4 on the same MAVROS setpoints, and what "
                  "PX4 does after those setpoints stop is outside this clone")
    #: The fake is an F0 analytic stand-in: one step is one environment transition, with no PX4, Gazebo, MAVROS,
    #: physics, sensors or wall-clock pacing.  The upstream simulator itself needs a live ROS 1 SITL stack.
    fidelity = {
        "engine": "analytic:legacy-gym px4 altitude stand-in (no PX4, Gazebo or MAVROS)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "notes": "The fake's transition is a fixed Python calculation with no random source. The bridge's seed "
                     "endpoint records a seed for the next reset, but upstream reset uses fixed desired/initial "
                     "values, so the seed has no effect and the same reset/step sequence is reproducible.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python stand-in: it loads no PX4 firmware, Gazebo, MAVROS, ROS, gym_px4 module or "
            "quadcopter model, and runs no physics, contacts, sensors, ROS graph or wall-clock loop",
            "the fake keeps x and y at zero and models only vertical altitude and vertical velocity; the upstream "
            "observation is [desired - z, vz] and the README's wider observation description does not match the "
            "code's two-value Box (gym_px4/envs/gymPX4_env.py:64-71)",
            "the upstream action space defined by the code is a single thrust value (gym_px4/envs/gymPX4_env.py:"
            "57-69), while README.md:57 documents thrust plus roll, pitch and yaw; the fake follows the code",
            "the fake reset returns immediately, while the upstream reset publishes setpoints in an unbounded "
            "while-loop until the vehicle reaches the reset altitude (gym_px4/envs/gymPX4_env.py:162-190); the "
            "upstream constructor also waits for MAVROS services and arms the vehicle "
            "(gym_px4/envs/gymPX4_env.py:119-139)",
            "the fake has no ROS publishers or services and cannot arm, switch to OFFBOARD, or command a real "
            "setpoint; it is evidence of the Gym contract only",
            "the fake's thrust-to-velocity gain and step size are placeholders; its initial altitude mirrors the "
            "upstream fixed reset value only as test data, not as a fact or a limit",
            "the seed capability is accepted by the bridge but does not change the deterministic fake or the "
            "upstream environment, whose reset uses fixed desired/initial values",
            "the real backend path (gym.make(env_id)) was not run: it requires ROS 1 melodic, Gazebo 9, MAVROS, "
            "the legacy gym package and a running PX4 SITL, and the package is not installed in the gate",
            "no upstream simulator, ROS graph or hardware was contacted, so this package is contract-checked on "
            "the fake only and makes no live-run or hardware claim",
            "the upstream environment cannot tell PX4 SITL from a real vehicle: it arms and requests OFFBOARD on "
            "whatever flight controller MAVROS is connected to, without checking either response "
            "(gym_px4/envs/gymPX4_env.py:294-311), and reset re-arms the vehicle whenever /mavros/state reports "
            "it disarmed, for example after a crash-landing disarm (gym_px4/envs/gymPX4_env.py:164-165); only "
            "the README points MAVROS at the SITL port (README.md:30-31)",
            "live construction in the server process would call the global rospy.init_node and wait for three "
            "MAVROS services with no timeout argument; the upstream step busy-waits with no bound or sleep until "
            "the local-position altitude changes (gym_px4/envs/gymPX4_env.py:215-222), so a silent "
            "/mavros/local_position/pose blocks it forever; reset and step print progress lines and ANSI "
            "cursor-up sequences to standard output (gym_px4/envs/gymPX4_env.py:155-192, 261-273), which would "
            "corrupt an MHS server speaking over stdio",
            "the upstream observation [desired - z, vz] leaves its own observation Box, whose first lower bound "
            "is 0.1, whenever z > 2 (gym_px4/envs/gymPX4_env.py:60-71, 252)",
            "the upstream reset() takes no seed or options (gym_px4/envs/gymPX4_env.py:143) and the fake's reset "
            "has the same signature, so the bridge falls back to a plain reset() for both",
        ],
    }
