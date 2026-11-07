"""OpenMHS driver for gh.kadhyo/wheeledrobotsimulations: the kitchen-v1 wheeled-robot navigation world.

A GymnasiumDriver is configuration only: ``env_id`` names one of the ``gym_fastsim`` environments that the clone
registers (``fastsim/gym_fastsim/__init__.py:15-22``) and the bridge derives the whole contract from the environment's
spaces.  This package serves ``kitchen-v1``, whose ten range-1 lasers and two-wheel action box are declared in
``fastsim/gym_fastsim/assets/kitchen_lasers.xml:6-20`` and ``fastsim/gym_fastsim/simple_nav/nav_env.py:118-121``:
``cap.world.step.v1`` takes ``{ticks, action: {values: [left, right]}}`` with each wheel bounded by ``maxVel`` 4,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no machine to stop and no operator-required limit.

The upstream is a legacy ``gym`` environment (``import gym``, ``nav_env.py:6``) whose ``SimpleNavEnv.__init__`` calls
``pyfastsim`` (``nav_env.py:14,75``).  Neither gym nor pyfastsim is installed where the gate runs and package code never
imports the clone, so the ``fake`` backend is this package's own pure Python kinematic stand-in for ``SimpleNavEnv``
(``fake.py``).  A backend name that ``backends`` does not list (``sim``) is served by ``gym.make(env_id)`` through
``GymnasiumDriver.open_native``; that path needs gym, pyfastsim and a preceding ``import gym_fastsim`` for the
registration, and it was not run here.

``kitchen-v0`` is not served: it registers ``assets/kitchen.xml`` (``__init__.py:15-16``), whose map is ``cuisine.pbm``
(``kitchen.xml:5``), but the clone's asset directory ships ``kitchen.pbm`` and no ``cuisine.pbm``; ``kitchen-v1`` uses
``assets/kitchen_lasers.xml`` (``__init__.py:17-18``) and the existing ``kitchen.pbm`` (``kitchen_lasers.xml:5``).

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002): the checked backend is
a kinematic F0 stand-in, and the gaps name what it does not reproduce.  Every fact cites a line of the clone at the
pinned commit 821f75691403aa92d683c4fe7c080933dea72bf6.  This package is model-authored and unreviewed: it is checked
on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

NAV = "fastsim/gym_fastsim/simple_nav/nav_env.py"
INIT = "fastsim/gym_fastsim/__init__.py"
KITCHEN_LASERS = "fastsim/gym_fastsim/assets/kitchen_lasers.xml"
KITCHEN = "fastsim/gym_fastsim/assets/kitchen.xml"
README = "README.md"


class FastsimNav(GymnasiumDriver):
    device_id = "fastsim-nav"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "kitchen-v1"
    native = "gym_fastsim.simple_nav:SimpleNavEnv"
    backends = {"fake": ".fake:FakeSimpleNavEnv"}
    display_name = "gym_fastsim kitchen-v1 (wheeled robot navigation)"
    vendor, model = "kadhyo", "gym_fastsim kitchen-v1"
    tags = ["wheeled-robot", "navigation", "laser", "reinforcement-learning", "simulation", "gym", "libfastsim"]
    facts = [
        Fact("SimpleNavEnv subclasses gym.Env", source="upstream_code", ref=f"{NAV}:66"),
        Fact("step unpacks its action into v1 and v2, the left and right wheel velocities", source="upstream_code",
             ref=f"{NAV}:186-188"),
        Fact("maxVel is 4, the value used in the C++ sferes2 experiment", source="upstream_code", ref=f"{NAV}:86"),
        Fact("step clips both motor orders to -maxVel through +maxVel before moving the robot", source="upstream_code",
             ref=f"{NAV}:190-191"),
        Fact("The action space is Box(low=-maxVel, high=maxVel, shape=(2,), dtype=float32)", source="upstream_code",
             ref=f"{NAV}:120-121"),
        Fact("The observation-space high array is maxSensorRange repeated n_lasers, then 1.0 repeated twice, then "
             "1.0 repeated n_lightsensors; low is 0.0 repeated n_lasers, 0.0 repeated twice and -1 (or 0 in realistic "
             "mode) repeated n_lightsensors", source="upstream_code", ref=f"{NAV}:118-119"),
        Fact("get_all_sensors returns only the laser ranges: the bumper and light-sensor terms are commented out",
             source="upstream_code", ref=f"{NAV}:182-184"),
        Fact("get_laserranges maps a negative laser distance to maxSensorRange and clips the rest to "
             "0..maxSensorRange", source="upstream_code", ref=f"{NAV}:143-156"),
        Fact("maxSensorRange is the first laser's range, or 0 when the robot has no laser", source="upstream_code",
             ref=f"{NAV}:89-95"),
        Fact("step calls robot.move(left, right, map, sticky_walls) once with the clipped motor orders",
             source="upstream_code", ref=f"{NAV}:193-194"),
        Fact("step sets episode_over to dist_obj <= goal.get_diam(), the goal's full diameter", source="upstream_code",
             ref=f"{NAV}:209-210"),
        Fact("step returns the legacy 4-tuple (sensors, reward, episode_over, info) with info dist_obj and robot_pos",
             source="upstream_code", ref=f"{NAV}:212"),
        Fact("The default reward_func is binary_goalbased", source="upstream_code", ref=f"{NAV}:67"),
        Fact("binary_goalbased returns 1.0 when the goal distance is at most goalRadius and 0.0 otherwise",
             source="upstream_code", ref=f"{NAV}:33-39"),
        Fact("goalRadius is half the goal diameter", source="upstream_code", ref=f"{NAV}:114-116"),
        Fact("The other reward functions are minimize_energy (minus the sum of the absolute motor orders), "
             "displacement (distance from the previous position) and none (0)", source="upstream_code",
             ref=f"{NAV}:42-63"),
        Fact("reset restores the initial pose, zeroes both motor orders and returns get_all_sensors(); it draws no "
             "random number and takes no seed", source="upstream_code", ref=f"{NAV}:217-223"),
        Fact("kitchen_env is assets/kitchen.xml", source="upstream_code", ref=f"{INIT}:9"),
        Fact("kitchen_lasers_env is assets/kitchen_lasers.xml", source="upstream_code", ref=f"{INIT}:10"),
        Fact("kitchen-v0 is registered with entry_point gym_fastsim.simple_nav:SimpleNavEnv and kwargs "
             "xml_env=join(dirname(__file__), kitchen_env)", source="upstream_code", ref=f"{INIT}:15-16"),
        Fact("kitchen-v1 is registered with entry_point gym_fastsim.simple_nav:SimpleNavEnv and kwargs "
             "xml_env=join(dirname(__file__), kitchen_lasers_env)", source="upstream_code", ref=f"{INIT}:17-18"),
        Fact("kitchen_lasers.xml places the robot at x=2, y=4, theta=0, the goal at x=0.5, y=0.5 with diameter 0.2, "
             "and ten lasers of range 1", source="upstream_code", ref=f"{KITCHEN_LASERS}:6-20"),
        Fact("kitchen_lasers.xml names the map kitchen.pbm", source="upstream_code", ref=f"{KITCHEN_LASERS}:5"),
        Fact("assets/kitchen.xml names the map cuisine.pbm", source="upstream_code", ref=f"{KITCHEN}:5"),
        Fact("The first simulation environment is based on the fast simulation library libfastsim",
             source="vendor_doc", ref=f"{README}:5"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The contract of the model as deployed.  The bridge derives the engine, determinism and lockstep clock; the
    #: members below state the kinematic stand-in this package actually serves and what it does not reproduce.
    fidelity = {
        "engine": "libfastsim:kitchen-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream reset restores a fixed initial pose and draws no random number (nav_env.py:217-223), "
                     "so a trajectory is a function of the action sequence; the bridge still exposes and echoes a seed, "
                     "and this package's fake uses no random number either",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic F0 stand-in: the fake integrates a differential-drive placeholder and synthesizes "
            "laser values; it does not call libfastsim's robot.move, model rigid-body dynamics, wall contacts, "
            "sensor geometry, wheel slip or noise",
            "timestep_ms is 0 because the clone states no integration interval for robot.move; one tick is one "
            "robot.move call and the fake advances one discrete transition per tick",
            "the observation space declares n_lasers+2+n_lightsensors bounds (nav_env.py:118-119) while "
            "get_all_sensors returns only the n_lasers laser readings (nav_env.py:182-184); the fake mirrors the "
            "mismatch: 12 bounds in the space and 10 values returned for kitchen-v1",
            "the upstream reset ignores a seed and restores the fixed initial pose; a seed does not change a "
            "trajectory, and the fake mirrors that",
            "the reward and terminal rule follow the clone: goalRadius is half the goal diameter (nav_env.py:114-116) "
            "while episode_over compares the distance to the full goal diameter (nav_env.py:209-210)",
            "no rendering is served (cap.world.render.v1 stays unbound); the info fields pose, acceleration, "
            "velocity and time listed in README.md:136-143 are not returned by step, which returns only dist_obj and "
            "robot_pos (nav_env.py:212)",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
