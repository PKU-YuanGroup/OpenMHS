"""OpenMHS driver for gh.enac-drones/dronesim: the CtrlAviary drone simulation (Gymnasium family).

A GymnasiumDriver is configuration only: the upstream class is ``CtrlAviary`` and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where the action is a Dict of one Box per
drone (the Box bounds are the drone's PWM limits read from its URDF), ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` ``{seed}``.

The upstream package is pyBullet plus legacy ``gym`` (setup.py:5-15), it has no registered Gymnasium id, and package
code never imports the clone.  The ``fake`` backend is therefore the package's own deterministic kinematic stand-in
for ``CtrlAviary`` (``.fake:FakeCtrlAviary``); no ``sim`` or ``hardware`` backend is served.  The fake was not compared
with the upstream environment because pybullet and gym are not installed where the gate runs.

The device is a simulated world (mode ``simulated``, catalogue class ``cap.world.*`` at R0): there is no hardware
backend, no native stop path to a machine and no operator-required limit.  This package is model-authored and
unreviewed; it is checked on the fake backend only.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  It is F0 because the
fake is an analytic kinematic stand-in, not the upstream F1 PyBullet model; the gaps say what is not modelled.  Every
Fact cites a line of the clone at the pinned commit (158e40f4631e64d731f16f81641f629fa7b2a986).
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "dronesim/envs/BaseAviary.py"
CTRL = "dronesim/envs/CtrlAviary.py"
TELLO = "dronesim/assets/tello.urdf"


class CtrlAviary(GymnasiumDriver):
    device_id = "ctrl-aviary"
    # The upstream registers no gym id (the examples construct CtrlAviary directly), so a gym.make(env_id) path
    # would be an invented id.  This package serves the package fake only; env_id stays unset.
    env_id = None
    native = "dronesim.envs.CtrlAviary:CtrlAviary"
    backends = {"fake": ".fake:FakeCtrlAviary"}
    display_name = "dronesim CtrlAviary (PyBullet multi-drone simulation)"
    vendor, model = "enac-drones", "dronesim CtrlAviary"
    tags = ["dronesim", "pybullet", "gym", "quadrotor", "multi-drone", "simulation", "world-sim"]
    facts = [
        Fact("dronesim is a pyBullet and gym-pybullet-drones based heterogeneous multi vehicle control and "
             "simulation framework", source="vendor_doc", ref="README.md:3"),
        Fact("BaseAviary subclasses gym.Env", source="upstream_code", ref=f"{BASE}:122"),
        Fact("CtrlAviary subclasses BaseAviary", source="upstream_code", ref=f"{CTRL}:7"),
        Fact("CtrlAviary's action space is a Dict with one Box per drone, its low from that drone's MIN_PWM and its "
             "high from MAX_PWM", source="upstream_code", ref=f"{CTRL}:111-116"),
        Fact("The default tello drone has four actuators (actuator_nr=4)", source="upstream_code",
             ref=f"{TELLO}:30"),
        Fact("The tello URDF's PWM limit is 0 to 1 per actuator", source="upstream_code", ref=f"{TELLO}:47"),
        Fact("CtrlAviary declares a per-drone observation Dict {state: Box(16), neighbors: MultiBinary(NUM_DRONES)}",
             source="upstream_code", ref=f"{CTRL}:196-208"),
        Fact("The observation state vector stacks position (3), quaternion (4), roll-pitch-yaw (3), velocity (3), "
             "angular velocity (3) and the last motor command (4 for tello); its docstring declares it (20,)",
             source="upstream_code", ref=f"{BASE}:764-783"),
        Fact("BaseAviary.reset() takes no seed or options argument", source="upstream_code", ref=f"{BASE}:406"),
        Fact("BaseAviary.step returns the four-value tuple obs, reward, done, info", source="upstream_code",
             ref=f"{BASE}:555"),
        Fact("BaseAviary.step advances the PyBullet simulation with p.stepSimulation for each aggregate physics step",
             source="upstream_code", ref=f"{BASE}:543"),
        Fact("CtrlAviary's default physics frequency is 240 Hz", source="upstream_code", ref=f"{CTRL}:21"),
        Fact("BaseAviary sets TIMESTEP = 1.0 / SIM_FREQ", source="upstream_code", ref=f"{BASE}:185-186"),
        Fact("BaseAviary uses gravity 9.8 m/s^2", source="upstream_code", ref=f"{BASE}:182"),
        Fact("CtrlAviary returns reward -1 on every step", source="upstream_code", ref=f"{CTRL}:278"),
        Fact("CtrlAviary returns done False on every step: it declares no terminal state", source="upstream_code",
             ref=f"{CTRL}:293"),
        Fact("CtrlAviary returns info {'answer': 42} on every step", source="upstream_code", ref=f"{CTRL}:308-310"),
        Fact("When initial_xyzs is None, drone i starts at (i*4*L, i*4*L, COLLISION_H/2 - COLLISION_Z_OFFSET + 0.1)",
             source="upstream_code", ref=f"{BASE}:360-372"),
        Fact("The adjacency matrix starts as the identity and marks a pair of drones as neighbours when their "
             "distance is below NEIGHBOURHOOD_RADIUS", source="upstream_code", ref=f"{BASE}:901-921"),
        Fact("setup.py installs only the top-level dronesim package and requires numpy, scipy, Pillow, matplotlib, "
             "cycler, gym and pybullet", source="upstream_code", ref="setup.py:5-15"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "dronesim:pybullet-CtrlAviary (package fake: analytic kinematics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "BaseAviary.reset() takes no seed (dronesim/envs/BaseAviary.py:406) and the upstream model uses "
                     "no RNG, so a reset rebuilds the same initial state; the fake is deterministic too and accepts "
                     "the seed for the family's cap.world.seed.v1 bookkeeping.  Every seed therefore repeats the "
                     "same trajectory on this fake; the seed is recorded but not consumed.",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in, not the upstream F1 PyBullet model: no contacts, mass and "
            "inertia dynamics, aerodynamics, ground effect, downwash, drag, actuator, sensor or noise model; the "
            "PWM command moves the published state by fixed per-tick increments",
            "the fake models one four-motor tello drone (CtrlAviary's default drone_model ['tello'], num_drones 1); "
            "multi-drone adjacency, other drone models and initial_xyzs, initial_vels and initial_rpys are not "
            "modelled",
            "the fake publishes the single tello's four PWM commands as one Box(4) instead of upstream's Dict keyed "
            "by the numeric drone index ('0'); the bridge's limit-path grammar cannot name a key that starts with a "
            "digit (action.0), and for one drone the four commands are the same; the fake's step also accepts the "
            "upstream Dict form",
            "CtrlAviary declares a 16-element state Box but _getDroneStateVector returns 16 values plus the last "
            "motor command (20 for tello); the fake publishes a 20-element Box and returns the 20-value state",
            "the upstream reset() takes no seed or options and the fake uses no RNG; cap.world.seed.v1 is served by "
            "the family but does not change the trajectory",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the fake was never compared with the upstream environment (pybullet and gym are not importable where "
            "the gate runs) and the model was never validated against a physical drone",
        ],
    }
