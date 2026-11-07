"""OpenMHS driver for gh.jacopopan/aerial-autonomy-stack: the AASEnv-v0 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from its spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with a one-element ``action.values``
bounded by the Box action space ``[-1.0, 1.0]``, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The observation space is the Gazebo /clock ``[sim_sec, sim_nanosec]``.  The
device is simulated (R0): it has no hardware backend, no e-stop path to a machine and no operator-required limit.

The upstream environment is a Dockerized Gazebo/PX4 stack: ``AASEnv.__init__`` creates the simulation and aircraft
containers, and ``reset``/``step`` exchange a double with a ZeroMQ bridge that pauses and multi-steps Gazebo
(``aas-gym/src/aas_gym/aas_env.py:165-166``, ``:227-228``, ``:290-400``;
``simulation/simulation_ws/src/zmq_bridge_cpp/src/zeromq_bridge.cpp:165-207``).  The gate cannot import or run that
stack (it needs Docker, Gazebo, numpy, gymnasium and pyzmq; ``aas-gym/pyproject.toml:11-18``), so the declared
``fake`` backend is the package's own pure Python clock recording fake (fake.py).  A backend name that ``backends``
does not list (``sim``) is served by ``gymnasium.make("AASEnv-v0")`` (GymnasiumDriver.open_native), but registration
lives in ``tools_and_docs/gym_run.py:17-20`` rather than in the installed package, so that path also needs the
registration and the full Docker/Gazebo stack; it was not run here.

The ``fidelity`` attribute describes the model as checked on the fake backend (spec 05-fidelity FID-002): an
analytic clock model at level F0, not the unrun Gazebo/PX4 simulation.  Every Fact cites a line of the clone at the
pinned commit bf1ca32ac8b13339da4b9bce742f46fcb9b5567c.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

AAS = "aas-gym/src/aas_gym/aas_env.py"
PYPROJECT = "aas-gym/pyproject.toml"
GYM_RUN = "tools_and_docs/gym_run.py"
SIM_YML = "simulation/simulation.yml.erb"
ZMQ_BRIDGE = "simulation/simulation_ws/src/zmq_bridge_cpp/src/zeromq_bridge.cpp"


class AASGymEnv(GymnasiumDriver):
    device_id = "aas-env"
    env_id = "AASEnv-v0"
    native = "aas_gym.aas_env:AASEnv"
    backends = {"fake": ".fake:FakeAASEnv"}
    display_name = "Aerial Autonomy Stack AASEnv-v0 (Gymnasium)"
    vendor, model = "Jacopo Panerati", "AASEnv-v0"
    tags = ["aerial", "drone", "gazebo", "px4", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The README lists a steppable Gymnasium environment and faster-than-real-time, multi-instance "
             "simulation", source="vendor_doc", ref="README.md:20"),
        Fact("The installation requires nvidia-driver, docker and nvidia-container-toolkit and builds the images "
             "with sim_build.sh", source="vendor_doc", ref="README.md:46-47"),
        Fact("Installing aas-gym is pip3 install -e . from the aas-gym directory after the Installation steps",
             source="vendor_doc", ref="README.md:321-325"),
        Fact("aas-gym describes itself as a Gymnasium wrapper for the aerial-autonomy-stack", source="upstream_code",
             ref=f"{PYPROJECT}:4"),
        Fact("aas-gym requires Python ^3.12 and depends on numpy ^2.4, gymnasium ^1.2, docker ^7.1 and pyzmq ^27.1",
             source="upstream_code", ref=f"{PYPROJECT}:11-18"),
        Fact("AASEnv is a Gymnasium environment class with render modes human and ansi", source="upstream_code",
             ref=f"{AAS}:15-16"),
        Fact("The action space is a one-element Box of floats from -1.0 to 1.0 with dtype float32",
             source="upstream_code", ref=f"{AAS}:35-40"),
        Fact("The observation space is a Box of the Gazebo /clock [seconds, nanoseconds] with low [0.0, 0.0] and "
             "high [inf, 1e9]", source="upstream_code", ref=f"{AAS}:41-46"),
        Fact("The constructor defaults are gym_freq_hz 50, an init duration of 80.0 s and a maximum episode "
             "length of 300.0 s", source="upstream_code", ref=f"{AAS}:20-33"),
        Fact("max_steps is int(MAX_EPISODE_LENGTH_SEC * GYM_FREQ_HZ), 15000 at the default 50 Hz",
             source="upstream_code", ref=f"{AAS}:33-51"),
        Fact("AASEnv creates the simulation container from the simulation-image:latest image", source="upstream_code",
             ref=f"{AAS}:165-166"),
        Fact("AASEnv creates one aircraft container from aircraft-image:latest per drone", source="upstream_code",
             ref=f"{AAS}:227-228"),
        Fact("reset restarts the simulation and aircraft containers, opens the ZeroMQ socket and sends the special "
             "action 9999.0 to reset the world", source="upstream_code", ref=f"{AAS}:290-352"),
        Fact("step reads force = action[0], sends it to the simulator and receives the clock in reply",
             source="upstream_code", ref=f"{AAS}:359-373"),
        Fact("Every step returns reward -1.0, terminated False, and truncated when step_count >= max_steps",
             source="upstream_code", ref=f"{AAS}:385-391"),
        Fact("The observation is np.array([sim_sec, sim_nanosec]) and info repeats them as sim_time_sec and "
             "sim_time_nanosec", source="upstream_code", ref=f"{AAS}:284-288"),
        Fact("reset passes seed only to gym.Env.reset, while the ZeroMQ reset payload is the constant 9999.0 and "
             "carries no seed", source="upstream_code", ref=f"{AAS}:290-328"),
        Fact("AASEnv-v0 is registered in gym_run.py with entry_point=AASEnv", source="upstream_code",
             ref=f"{GYM_RUN}:17-20"),
        Fact("The ZeroMQ bridge runs the world unpaused for init_duration seconds on reset and pauses it afterwards",
             source="upstream_code", ref=f"{ZMQ_BRIDGE}:165-186"),
        Fact("The ZeroMQ bridge publishes the double action on /action and advances the paused world by step_size "
             "physics steps", source="upstream_code", ref=f"{ZMQ_BRIDGE}:188-201"),
        Fact("The step target time is current_sim_time + step_size * physics_dt - 0.0001 s", source="upstream_code",
             ref=f"{ZMQ_BRIDGE}:197"),
        Fact("The bridge computes step_size = physics_freq_hz / gym_freq_hz and physics_dt is 0.004 s for PX4, "
             "so with the default gym_freq_hz 50 one control step is nominally 20 ms", source="upstream_code",
             ref=f"{SIM_YML}:23-42"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the checked model (spec 05-fidelity section 2).  It describes the analytic fake;
    #: the real Gazebo/PX4 backend is not claimed or covered by this package's check.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "reset(seed) forwards the seed to gym.Env's generator (aas_env.py:291), but the simulator reset "
                     "is the constant 9999.0 payload (aas_env.py:327-328) and the fake ignores the seed, so no seed "
                     "reproduces a trajectory",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake models only the simulated clock and the constant -1 step reward: there is no "
            "Gazebo/PX4 rigid-body dynamics, contact, actuator, sensor, wind, camera or LiDAR model, and the real "
            "Dockerized simulation was not run",
            "the clock start, the 80 s reset run and the control period in the fake are test data that mirror the "
            "constructor defaults, not a calibrated model of a Gazebo world",
            "no wall-clock pacing: realtime_factor 0 and only cap.world.step.v1 advances simulated time",
            "the seed reaches only gym.Env's random generator and not the simulator, so determinism is none",
            "snapshot and restore are not offered: AASEnv exposes no get_state/set_state",
            "the observation is only the Gazebo /clock [seconds, nanoseconds]; the camera and LiDAR streams are "
            "not part of the observation space",
            "the fake returns Python floats and lists; upstream returns float64 numpy arrays",
            "the control period is nominal 1/gym_freq_hz; the ZeroMQ bridge targets step_size * physics_dt minus "
            "0.1 ms, so the real clock increments can differ",
        ],
    }
