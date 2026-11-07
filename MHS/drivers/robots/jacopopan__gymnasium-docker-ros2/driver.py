"""OpenMHS driver for gh.jacopopan/gymnasium-docker-ros2: the GDR2 point-mass environment.

The card names a RosDriver, but the upstream entry symbol is a Gymnasium environment
(``gymnasium_docker_ros2.env:GDR2Env`` derives from ``gym.Env``), not a ROS transport
client.  The repository also contains the ROS 2 ``dynamics`` node and a ZeroMQ/Gazebo
bridge, but the primary interface is ``reset``/``step`` over ``cap.world.*``; a
Gymnasium environment does not become a ROS transport driver because its repository
also contains ROS nodes.  This package therefore uses :class:`GymnasiumDriver`
(DEVIATION FROM THE CARD, recorded in RESULT.json).  The bridge derives the step action
schema and its per-element limits from the environment's action space.

The device is simulated (R0).  There is no hardware backend, no physical e-stop and no
operator-required limit.  The upstream environment itself starts a Docker network and
two containers (``src/gymnasium_docker_ros2/env.py:44-116``), so the gate cannot open it:
the ``fake`` backend is this package's pure Python model of the upstream dynamics node
(``resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py:39-52``).  That fake copies
the upstream action space (``env.py:34``), which ``action_space_ref`` cites so gate G4
checks the bounds against the clone.

Every fact cites the pinned clone at b3a00f77da38b7f074bed00d3569c56dbfe114df.  This
package is model-authored and unreviewed; it is checked on the fake backend only, and no
Docker, ROS 2, Gazebo, live simulator or hardware run has happened.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "src/gymnasium_docker_ros2/env.py"
DYNAMICS = "resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py"
ZMQ_BRIDGE = "resources/zeromq_bridge.py"
SDF = "resources/gdr2-world.sdf"
TMUX = "resources/tmux_session.yml.erb"
TEST = "test.py"
PYPROJECT = "pyproject.toml"
README = "README.md"


class GymnasiumDockerRos2(GymnasiumDriver):
    device_id = "gdr2-point-mass"
    # The package never registers the environment id on import; test.py registers
    # GDR2Env-v0 inside main().  The fake backend is constructed directly, so env_id
    # stays unset and the bridge does not call gymnasium.make.
    env_id = None
    native = "gymnasium_docker_ros2.env:GDR2Env"
    backends = {"fake": ".fake:FakeGDR2Env"}
    # env.py:34 defines the Box the fake copies: low=-1.0, high=1.0, shape=(1,).
    action_space_ref = f"{ENV}:34"
    display_name = "GDR2 Docker/ROS 2 point-mass environment"
    vendor, model = "Jacopo Panerati", "GDR2Env-v0"
    tags = ["gymnasium", "docker", "ros2", "gazebo", "zeromq", "point-mass",
            "reinforcement-learning", "simulation"]
    facts = [
        Fact("GDR2Env derives from gym.Env and models a simple 1D point-mass system whose state is position and "
             "velocity and whose action is one force value", source="upstream_code", ref=f"{ENV}:11-18"),
        Fact("The environment advertises the human render mode with render_fps 20",
             source="upstream_code", ref=f"{ENV}:19"),
        Fact("The constructor sets max_steps to 1000 and dt to 0.05",
             source="upstream_code", ref=f"{ENV}:24-25"),
        Fact("The observation space is Box([-1.0, -5.0], [1.0, 5.0], dtype=float32) over position and velocity",
             source="upstream_code", ref=f"{ENV}:27-31"),
        Fact("The action space is Box(low=-1.0, high=1.0, shape=(1,), dtype=float32), one force value",
             source="upstream_code", ref=f"{ENV}:33-34"),
        Fact("The constructor creates a Docker network named gdr2-network, the simulation-container and "
             "dynamics-container from gdr2-image:latest, and a ZeroMQ REQ socket to 10.42.0.20:5555",
             source="upstream_code", ref=f"{ENV}:44-116"),
        Fact("reset sends the special control value 9999.0 over ZeroMQ, unpacks a ddii position/velocity/time "
             "reply, stores position and velocity and resets step_count",
             source="upstream_code", ref=f"{ENV}:124-160"),
        Fact("step sends the force over ZeroMQ, unpacks the same ddii position/velocity/time reply and stores "
             "position and velocity", source="upstream_code", ref=f"{ENV}:162-179"),
        Fact("A step returns reward -abs(position), terminated false, truncated when step_count reaches "
             "max_steps, and (observation, reward, terminated, truncated, info)",
             source="upstream_code", ref=f"{ENV}:198-214"),
        Fact("close stops the simulation and dynamics containers, removes the network and closes the ZeroMQ "
             "socket and context", source="upstream_code", ref=f"{ENV}:231-256"),
        Fact("_get_obs returns the float32 array [position, velocity] and _get_info returns position and velocity",
             source="upstream_code", ref=f"{ENV}:118-122"),
        Fact("test.py registers GDR2Env-v0 with entry_point GDR2Env and creates the environment with "
             "render_mode human", source="upstream_code", ref=f"{TEST}:18-23"),
        Fact("The declared runtime requires Python ^3.13 with numpy, gymnasium, docker and pyzmq",
             source="upstream_code", ref=f"{PYPROJECT}:10-19"),
        Fact("The README describes GDR2 as a multi-container Docker/Gazebo/ROS2 app wrapped in gymnasium, "
             "installed with pip install -e . and exercised with test.py --mode step, speed or learn",
             source="vendor_doc", ref=f"{README}:3-24"),
        Fact("DynamicsNode computes dt as 1.0 / rate and seeds NumPy to 42 once at construction",
             source="upstream_code", ref=f"{DYNAMICS}:14-21"),
        Fact("The DynamicsNode command line defaults rate to 50 Hz",
             source="upstream_code", ref=f"{DYNAMICS}:64-66"),
        Fact("The simulation launch runs the dynamics node with --rate 20",
             source="upstream_code", ref=f"{TMUX}:18"),
        Fact("The world SDF fixes max_step_size to 0.050 s and real_time_factor to 0.0",
             source="upstream_code", ref=f"{SDF}:4-6"),
        Fact("The dynamics reset branch triggers within 0.1 of control input 9999.0, draws position uniformly "
             "from -0.8 to 0.8 and sets velocity to 0",
             source="upstream_code", ref=f"{DYNAMICS}:39-43"),
        Fact("The dynamics update integrates velocity += control_input * dt, multiplies velocity by 0.99, "
             "integrates position += velocity * dt, clips position to [-1, 1] and multiplies velocity by -0.5 "
             "at a wall", source="upstream_code", ref=f"{DYNAMICS}:44-52"),
        Fact("The Python ZeroMQ bridge requests one Gazebo multi-step per request with a 1 s service timeout, "
             "then waits up to 2.0 s for a new /state and packs the reply as ddii",
             source="upstream_code", ref=f"{ZMQ_BRIDGE}:78-96"),
    ]
    safe_state = ("An e-stop freezes the simulated world in software: no step is accepted until mhs.safety.reset "
                  "clears the latch, and the last observation and tick stay readable; this is a simulation latch, "
                  "not a physical stop.")
    #: The deployed fake (spec 05-fidelity FID-002): the upstream dynamics node's Euler point-mass
    #: update in plain Python, one update per step, with no Docker/ROS/Gazebo path.
    fidelity = {
        "engine": "analytic:gdr2-point-mass",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds a Python random.Random from reset(seed), and cap.world.seed.v1 selects the "
                     "seed of the next reset, so one seed repeats the fake's trajectory; the live dynamics node "
                     "seeds NumPy to 42 once at construction and its reset branch ignores the Gymnasium seed, so a "
                     "container run repeats only while that node process keeps its RNG sequence",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake reproduces only the dynamics node's one-dimensional Euler update; there is no Docker, "
            "ZeroMQ, ROS 2, Gazebo, C++/Python bridge, /state round trip or rendering, and no rigid-body, contact, "
            "actuator, sensor or noise dynamics",
            "the live dynamics node seeds NumPy to 42 once at startup and ignores the Gymnasium reset seed, while "
            "the fake reseeds from reset(seed); one seed therefore repeats in the fake and is not guaranteed to "
            "repeat against a live container",
            "no wall-clock pacing: real_time_factor is 0 and the fake advances only when called; timestep_ms 50 is "
            "the declared physics/control interval (env dt 0.05, SDF max_step_size 0.050, dynamics --rate 20), not "
            "a measured wall-clock latency",
            "the upstream environment exposes no get_state/set_state, so the package offers no snapshot or restore",
            "the package declares only the fake backend; a live run needs Docker Engine, the gdr2-image, ROS 2 "
            "Humble and Gazebo Harmonic as the README describes, none of which the gate contacts",
            "observations are Python floats and lists; upstream returns float32 numpy arrays with the same "
            "position and velocity values",
            "the fake's start state and reset draws are test data, not calibrated against a live dynamics node",
        ],
    }
