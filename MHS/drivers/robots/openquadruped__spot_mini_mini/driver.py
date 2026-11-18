"""OpenMHS driver for gh.openquadruped/spot_mini_mini: the SpotMicroEnv-v0 PyBullet quadruped environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.*`` contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values`` bounded by the twelve-motor ``Box(-1, 1)`` action space (``spotmicro/spot_gym_env.py:280-282``),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The observation is the
sixteen-value vector of ``Spot.GetObservation`` when contacts are enabled: roll, pitch, angular rate xyz, linear
acceleration xyz, four leg phases and four foot contacts (``spotmicro/spot.py:688-703``).  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The card lists three entry symbols; this package serves the first one, ``spotmicro.spot_gym_env:spotGymEnv``, which
registers ``SpotMicroEnv-v0`` (``spotmicro/spot_gym_env.py:47-51``).  The Bezier variant is a subclass that drives the
motors from its own state machine and ignores the passed action, and the Minitaur environment belongs to a separate
``mini_bullet`` package.

The ``fake`` backend is this package's pure Python stand-in (fake.py) and does not import the clone.  A backend name
that ``backends`` does not list (``sim``) is served by ``gym.make("SpotMicroEnv-v0", render=False)`` after the bridge
imports ``env_module`` (GymnasiumDriver.open_native).  ``spotmicro.spot_gym_env`` is that module: its body imports
``gym.envs.registration.register`` and calls it for ``SpotMicroEnv-v0`` (``spotmicro/spot_gym_env.py:24``,
``:47-51``).  ``render=False`` selects ``BulletClient()`` with no connection mode instead of the GUI client
(``:103``, ``:264-268``).  The clone has no setup.py; the sim run puts the pinned tree on ``PYTHONPATH`` and installs
the legacy ``gym``, PyBullet and ``pkg_resources`` that module imports.  That sim path was not run in this workspace.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002), with the fake's
limitations in ``gaps``.  Every constant and rule cites a line of the clone at the pinned commit
(c7e4905be176c63fa0e68a09c177b937e916fa60).  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "spotmicro/spot_gym_env.py"
SPOT = "spotmicro/spot.py"
RANDOMIZER = "spotmicro/spot_env_randomizer.py"
DATA = "spotmicro/util/pybullet_data/__init__.py"
CLIENT = "spotmicro/util/bullet_client.py"


class SpotMicro(GymnasiumDriver):
    device_id = "spot-micro"
    env_id = "SpotMicroEnv-v0"
    #: spotmicro/spot_gym_env.py:24 imports register and :47-51 call it at module scope.  The bridge imports this
    #: module before gym.make only when it builds the environment itself; the fake entry is built directly.
    env_module = "spotmicro.spot_gym_env"
    native = "spotmicro.spot_gym_env:spotGymEnv"
    backends = {"fake": ".fake:FakeSpotGymEnv"}
    #: render defaults to True and opens BulletClient(connection_mode=pybullet.GUI) (spot_gym_env.py:103, :264-266).
    #: False builds BulletClient() with no connection mode (:267-268).
    env_kwargs = {"render": False}
    mode, risk = "simulated", "R0"
    display_name = "openquadruped spot_mini_mini SpotMicroEnv-v0 (PyBullet quadruped)"
    vendor, model = "openquadruped", "SpotMicroEnv-v0"
    tags = ["spot", "quadruped", "robot", "locomotion", "pybullet", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("SpotMicroEnv-v0 is registered with entry point spotmicro.spot_gym_env:spotGymEnv and "
             "max_episode_steps 1000", source="upstream_code", ref=f"{ENV}:47-51"),
        Fact("The register call is at module scope, so importing spotmicro.spot_gym_env registers SpotMicroEnv-v0",
             source="upstream_code", ref=f"{ENV}:47-51"),
        Fact("spot_gym_env imports register from gym.envs.registration", source="upstream_code", ref=f"{ENV}:24"),
        Fact("spot_gym_env imports pybullet, pybullet_data and pybullet_utils.bullet_client",
             source="upstream_code", ref=f"{ENV}:17-23"),
        Fact("spot_gym_env imports parse_version from pkg_resources", source="upstream_code", ref=f"{ENV}:21"),
        Fact("The class body compares gym.__version__ with 0.9.6 and keeps the new method names at or above that "
             "version", source="upstream_code", ref=f"{ENV}:705"),
        Fact("The constructor default render is True", source="upstream_code", ref=f"{ENV}:103"),
        Fact("render True builds BulletClient with connection_mode pybullet.GUI, and render False builds "
             "BulletClient with no connection mode", source="upstream_code", ref=f"{ENV}:264-268"),
        Fact("The vendored BulletClient treats a missing connection mode as SHARED_MEMORY and then DIRECT",
             source="upstream_code", ref=f"{CLIENT}:25-31"),
        Fact("The urdf_root default is pybullet_data.getDataPath()", source="upstream_code", ref=f"{ENV}:85"),
        Fact("reset loads plane.urdf from urdf_root", source="upstream_code", ref=f"{ENV}:319-320"),
        Fact("Spot.Reset loads assets/urdf/spot.urdf from spotmicro.util.pybullet_data.getDataPath()",
             source="upstream_code", ref=f"{SPOT}:375-376"),
        Fact("The vendored getDataPath returns the directory of spotmicro.util.pybullet_data",
             source="upstream_code", ref=f"{DATA}:3-6"),
        Fact("docs/requirements.txt pins pybullet==2.6.4, numpy==1.18.4 and gym==0.17.2",
             source="vendor_doc", ref="docs/requirements.txt:1-3"),
        Fact("spotGymEnv simulates the locomotion of a quadruped robot; its docstring says the action space is the "
             "desired motor angle for each motor", source="upstream_code", ref=f"{ENV}:62-69"),
        Fact("NUM_MOTORS is 12", source="upstream_code", ref=f"{ENV}:31"),
        Fact("The action bound _action_bound is 1", source="upstream_code", ref=f"{ENV}:240"),
        Fact("The action space is spaces.Box(-action_high, action_high) with action_high made of _action_bound for "
             "action_dim = NUM_MOTORS", source="upstream_code", ref=f"{ENV}:280-282"),
        Fact("The observation bounds come from Spot.GetObservationUpperBound() plus OBSERVATION_EPS and "
             "GetObservationLowerBound() minus OBSERVATION_EPS", source="upstream_code", ref=f"{ENV}:276-279"),
        Fact("The observation upper bound is 2*pi for roll and pitch, infinity for the three angular rates and three "
             "linear accelerations, 2.0 for the four leg phases and 1.0 for the four contacts",
             source="upstream_code", ref=f"{SPOT}:590-597"),
        Fact("The observation lower bound is minus the upper bound", source="upstream_code", ref=f"{SPOT}:600-602"),
        Fact("GetObservation appends roll, pitch, the angular twist xyz, the linear acceleration xyz, the leg phases "
             "and, when contacts are enabled, the four foot contacts", source="upstream_code", ref=f"{SPOT}:688-703"),
        Fact("The contacts constructor option defaults to True", source="upstream_code", ref=f"{ENV}:118"),
        Fact("is_fallen returns true when the dot product of the world up direction and the base's local up "
             "direction is below 0.55", source="upstream_code", ref=f"{ENV}:536-551"),
        Fact("_termination returns is_fallen() or whether the base distance exceeds _distance_limit",
             source="upstream_code", ref=f"{ENV}:553-556"),
        Fact("distance_limit defaults to float('inf')", source="upstream_code", ref=f"{ENV}:87"),
        Fact("The simulation time step is 0.01 s and the control period is _time_step * _action_repeat",
             source="upstream_code", ref=f"{ENV}:198-211"),
        Fact("action_repeat defaults to 1, and pd_control_enabled and accurate_motor_model_enabled default to False",
             source="upstream_code", ref=f"{ENV}:91-105"),
        Fact("seed calls gym.utils.seeding.np_random and returns [seed]", source="upstream_code", ref=f"{ENV}:382-384"),
        Fact("step returns a numpy observation, the reward, done and an empty info dictionary",
             source="upstream_code", ref=f"{ENV}:440"),
        Fact("env_randomizer defaults to a SpotEnvRandomizer instance", source="upstream_code", ref=f"{ENV}:107"),
        Fact("SpotEnvRandomizer seeds numpy's global generator with 0 in its constructor",
             source="upstream_code", ref=f"{RANDOMIZER}:37"),
        Fact("The constructor creates a pybullet_utils BulletClient, so the environment runs on PyBullet",
             source="upstream_code", ref=f"{ENV}:264-268"),
        Fact("The environment metadata declares the human and rgb_array render modes and 50 video frames per second",
             source="upstream_code", ref=f"{ENV}:72-75"),
    ]
    safe_state = ("the simulated spot world stops advancing: after an e-stop every step and reset is refused and the "
                  "last observation stays readable until mhs.safety.reset clears the latch; there is no hardware to "
                  "stop")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine, the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:SpotMicroEnv-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 seeds the fake and its placeholder initial tilt and gait "
                     "phase; upstream seeds gym.utils.seeding.np_random and the default SpotEnvRandomizer then draws "
                     "physical properties from numpy's global generator, so one seed does not give the same "
                     "trajectory on the two implementations",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure Python kinematic stand-in with placeholder tilt, gait-phase, acceleration and reward "
            "values; it does not run PyBullet and models no rigid bodies, contacts, motor model or actuator "
            "fidelity, so trajectories differ from the clone",
            "the fake models no sensor noise, control or observation latency, observation history, height field or "
            "environment randomizer; upstream SpotEnvRandomizer randomizes mass, inertia, friction, battery voltage "
            "and motor damping at every reset",
            "the fake reset returns (observation, info) and its step returns a five-tuple with the registered "
            "1000-step limit applied by the fake; upstream reset returns the observation only and step returns a "
            "four-tuple, and gym.make adds the TimeLimit wrapper",
            "the fake seeds Python's random.Random; upstream seeds gym.utils.seeding.np_random and the randomizer "
            "uses numpy's global generator, so the same seed gives different trajectories",
            "no rendering, camera adjustment or GUI pacing is modelled; realtime_factor 0 and ticks advance "
            "simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
