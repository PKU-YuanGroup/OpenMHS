"""OpenMHS driver for gh.axelbr/racecar_gym: the single-agent race environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where the action is the environment's
action space (two Box members of length one: ``steering`` and ``motor``, each bounded by -1 and 1);
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream package (pybullet, numpy and a first-use track download; see ``requirements.txt``
and ``racecar_gym/bullet/providers.py:90-96``), so the ``fake`` backend is the package's own pure Python stand-in
(``fake.py``).  A backend name that ``backends`` does not list would be served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native), which also needs ``racecar_gym.envs.gym_api`` imported for the registration; that path
was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002), with the fake's
limitations in ``gaps``.  Every constant and rule cites a line of the clone at the pinned commit
(70496767d80397010ac9b5ba722647ca67e3f85c).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "racecar_gym/envs/gym_api/single_agent_race.py"
SENSORS = "racecar_gym/bullet/sensors.py"
VEHICLE = "models/vehicles/racecar/racecar.yml"
TASK = "racecar_gym/tasks/progress_based.py"


class RacecarGym(GymnasiumDriver):
    device_id = "racecar-gym"
    env_id = "SingleAgentAustria-v0"
    native = "racecar_gym.envs.gym_api:SingleAgentRaceEnv"
    backends = {"fake": ".fake:FakeSingleAgentRaceEnv"}
    display_name = "racecar_gym single-agent race environment"
    vendor, model = "axelbr", "racecar_gym"
    tags = ["racecar", "racing", "reinforcement-learning", "pybullet", "simulation", "gymnasium"]
    facts = [
        Fact("SingleAgentRaceEnv is the single-agent Gymnasium environment of the gym API", source="upstream_code",
             ref=f"{ENV}:9"),
        Fact("A scenario that lists no actuators gets the VehicleSpec default ['steering', 'motor']",
             source="upstream_code", ref="racecar_gym/core/specs.py:23"),
        Fact("The vehicle action space is a Dict keyed by actuator name", source="upstream_code",
             ref="racecar_gym/core/vehicles.py:40-41"),
        Fact("The motor actuator's action space is Box(low=-1.0, high=1.0, shape=(1,))", source="upstream_code",
             ref="racecar_gym/bullet/actuators.py:62"),
        Fact("The steering actuator's action space is Box(low=-1.0, high=1.0, shape=(1,))", source="upstream_code",
             ref="racecar_gym/bullet/actuators.py:117"),
        Fact("The car's action space is normalized between -1 and 1", source="vendor_doc", ref="README.md:90"),
        Fact("The vehicle observation space is a Dict keyed by sensor name", source="upstream_code",
             ref="racecar_gym/core/vehicles.py:44-46"),
        Fact("The single-agent observation space adds a 'time' Box with declared bounds 0 to 1 to the agent's sensor "
             "Dict", source="upstream_code", ref=f"{ENV}:24-27"),
        Fact("The step writes the growing simulation time into observation['time'] without clipping it to the "
             "declared Box bound", source="upstream_code", ref=f"{ENV}:38"),
        Fact("The shipped austria scenario requests the lidar, pose, velocity and acceleration sensors",
             source="upstream_code", ref="scenarios/austria.yml:7"),
        Fact("The racecar lidar is configured with 1080 rays, range 15.0 and min_range 0.25", source="upstream_code",
             ref=f"{VEHICLE}:55-57"),
        Fact("The lidar space is a Box of one value per ray bounded by min_range and min_range+range",
             source="upstream_code", ref=f"{SENSORS}:109-112"),
        Fact("A world update advances pybullet by one simulation step and adds the configured time step to the state "
             "time", source="upstream_code", ref="racecar_gym/bullet/world.py:120-122"),
        Fact("The SimulationSpec time step defaults to 0.01 s", source="upstream_code",
             ref="racecar_gym/core/specs.py:8"),
        Fact("The fixed-timestep sensor scheduler is constructed with a 0.01 s time step", source="upstream_code",
             ref="racecar_gym/bullet/providers.py:67"),
        Fact("The single-agent reset passes the seed to gymnasium.Env.reset", source="upstream_code",
             ref=f"{ENV}:44"),
        Fact("Sensor noise is drawn from numpy's global generator (np.random.normal), so the seed passed to "
             "gymnasium.Env.reset does not control it", source="upstream_code", ref=f"{SENSORS}:255"),
        Fact("The reset option 'mode' selects the starting-position mode and defaults to 'grid'", source="upstream_code",
             ref=f"{ENV}:50-53"),
        Fact("The maximize_progress task's default progress_reward is 100.0", source="upstream_code",
             ref=f"{TASK}:8"),
        Fact("The maximize_progress reward is the change in lap+progress times progress_reward", source="upstream_code",
             ref=f"{TASK}:20-33"),
        Fact("The maximize_progress task ends when lap > laps or time > time_limit", source="upstream_code",
             ref=f"{TASK}:35-39"),
        Fact("The single-agent registration passes the scenario path as the scenario kwarg", source="upstream_code",
             ref="racecar_gym/envs/gym_api/__init__.py:23-29"),
        Fact("The gym_api module registers one SingleAgent<Track>-v0 environment per scenario file",
             source="upstream_code", ref="racecar_gym/envs/gym_api/__init__.py:43-47"),
        Fact("SingleAgentAustria-v0 is documented as a predefined environment id", source="vendor_doc",
             ref="README.md:132"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latch refuses every step and reset after an e-stop "
                  "until mhs.safety.reset clears it, and the last state stays readable; the simulator has no native "
                  "stop")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine, the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet",
        "fidelity_level": "F2",
        "determinism": {
            "kind": "statistical",
            "seed_control": "parameter",
            "notes": "SingleAgentRaceEnv.reset(seed) seeds gymnasium's own np_random, but the sensor models draw "
                     "their noise from numpy's global generator (racecar_gym/bullet/sensors.py:255), so one seed "
                     "does not fix a trajectory; the package fake uses its own seeded random.Random.",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in, not the pybullet model: it has no rigid-body dynamics, "
            "contacts, friction, collisions, opponents, laps, ranks or task termination; its pose, velocity, "
            "acceleration, progress and reward are placeholders",
            "the fake returns a constant placeholder lidar scan of the real 1080-ray length and does not model the "
            "pose, velocity or acceleration sensor noise, the camera or the sensor frequencies",
            "the physics time step is read from the downloaded track scene's simulation.time_step "
            "(racecar_gym/bullet/providers.py:110), which is not in the clone; the contract states the 0.01 s "
            "SimulationSpec default (racecar_gym/core/specs.py:8) and the fixed 0.01 s sensor scheduler "
            "(racecar_gym/bullet/providers.py:67), and the fake advances 0.01 s per transition as a placeholder",
            "no wall-clock pacing: realtime_factor 0 and ticks advance simulated time only",
            "snapshot and restore are not offered: SingleAgentRaceEnv exposes no get_state/set_state (only "
            "MultiAgentRaceEnv has set_state)",
            "the track scene files under models/scenes are downloaded on first use and are not in the clone; neither "
            "the fake nor this package loads them",
            "the fake's observation 'time' is a one-element array while upstream writes a 0-d float32 array, and the "
            "fake never terminates an episode while the shipped task ends at lap > laps or time > time_limit",
            "no physical device is modelled and nothing was validated against one",
        ],
    }
