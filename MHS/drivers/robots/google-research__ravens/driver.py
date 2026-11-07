"""OpenMHS driver for gh.google-research/ravens: the Ravens PyBullet manipulation environment.

Ravens is a simulated tabletop manipulation benchmark with a Gym-like API (``README.md:3-4``).  The card's role is
``sim-env``: this package is a simulated R0 driver (``GymnasiumDriver``) whose ``native`` is
``ravens.environments.environment:Environment``, the ``gym.Env`` base class at ``environment.py:42``.  The bridge
serves ``cap.world.step.v1`` (``{ticks, action}``), ``cap.world.reset.v1`` (``{seed, options}``) and
``cap.world.seed.v1`` (``{seed}``).

The action space of the base ``Environment`` is a ``Dict`` of ``pose0`` and ``pose1``, each a ``Tuple`` of a position
box and a four-value rotation box (``environment.py:89-103``); the bridge turns that into nested JSON arrays and
declares no per-element limits inside a ``Tuple`` (a simulation-only residual of the SDK bridge, listed in ``gaps``).
The observation is a ``Dict`` of RGB-D ``color``/``depth`` tuples (``environment.py:77-88``).  ``step`` returns the
legacy four-tuple ``(obs, reward, done, info)`` (``environment.py:224-255``), so the bridge treats ``done`` as
``terminated`` and never reports truncation.  ``reset`` rebuilds the PyBullet scene and returns the first observation
(``environment.py:179-222``).

The gate cannot import the clone's stack (``gym``, ``pybullet``, ``numpy`` and the asset tree), and package code never
imports or runs the clone.  The ``fake`` backend is therefore this package's own pure-Python stand-in for the
``Environment`` surface: it implements the same public methods (``reset``, ``step``, ``seed``, ``close``) and the same
space structure, and returns small placeholder RGB-D arrays instead of the RealSenseD415 images.  It was not compared
with the upstream simulator.  A backend name that ``backends`` does not list is served by ``gymnasium.make(env_id)``
in ``GymnasiumDriver.open_native``; this package leaves ``env_id`` unset because Ravens registers no Gym environment
and needs ``assets_root`` and a task object, so no upstream ``sim`` path was run.

Fidelity (spec 05-fidelity FID-002): the deployed simulator is PyBullet rigid-body dynamics (F1), stepped in lockstep
at the upstream default ``hz=240`` (``environment.py:50``, ``1./hz`` at ``environment.py:138``).  ``hz`` is a
constructor option, so the published timestep is the default and a deployment can change it.  Determinism is declared
``none``: ``Environment.seed()`` only installs a ``RandomState`` for the camera-noise generator
(``environment.py:175-177``), while the task resets draw from the global numpy RNG, so a seed does not reproduce an
upstream task layout.  The package is model-authored and unreviewed and is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVIRONMENT = "ravens/environments/environment.py"
CAMERAS = "ravens/tasks/cameras.py"


class Ravens(GymnasiumDriver):
    device_id = "ravens"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "ravens.environments.environment:Environment"
    backends = {"fake": ".fake:FakeRavensEnvironment"}
    display_name = "Ravens PyBullet manipulation environment"
    vendor, model = "Google Research", "Ravens"
    tags = ["ravens", "pybullet", "robot-manipulation", "reinforcement-learning", "simulation"]
    facts = [
        Fact("Ravens is a collection of simulated tasks in PyBullet for learning vision-based robotic manipulation, "
             "with a Gym-like API", source="vendor_doc", ref="README.md:3-4"),
        Fact("Environment subclasses gym.Env and its docstring calls it an OpenAI Gym-style environment class",
             source="upstream_code", ref=f"{ENVIRONMENT}:42-43"),
        Fact("The observation space is a Dict of color and depth Tuples, with color boxes 0 to 255 and depth boxes "
             "0.0 to 20.0 for each RealSenseD415 camera", source="upstream_code", ref=f"{ENVIRONMENT}:77-88"),
        Fact("The default camera configuration has three RealSenseD415 entries with 480 by 640 images",
             source="upstream_code", ref=f"{CAMERAS}:27-73"),
        Fact("The action space is a Dict with pose0 and pose1, each a Tuple of the position box and a four-value "
             "box in -1.0 to 1.0", source="upstream_code", ref=f"{ENVIRONMENT}:94-103"),
        Fact("The position box has low [0.25, -0.5, 0.] and high [0.75, 0.5, 0.28]",
             source="upstream_code", ref=f"{ENVIRONMENT}:89-93"),
        Fact("Environment.seed(seed) installs a numpy RandomState in _random and returns the seed",
             source="upstream_code", ref=f"{ENVIRONMENT}:175-177"),
        Fact("Environment.reset() rebuilds the PyBullet scene, resets the task and returns the observation of a "
             "first step", source="upstream_code", ref=f"{ENVIRONMENT}:179-222"),
        Fact("Environment.step(action) executes a task primitive and returns the (obs, reward, done, info) tuple; "
             "a timed-out primitive also returns done True", source="upstream_code", ref=f"{ENVIRONMENT}:224-255"),
        Fact("Environment.close() unloads the EGL plugin and disconnects the PyBullet client",
             source="upstream_code", ref=f"{ENVIRONMENT}:257-260"),
        Fact("The PyBullet physics time step is 1./hz", source="upstream_code", ref=f"{ENVIRONMENT}:138"),
        Fact("The hz parameter of the Environment constructor defaults to 240", source="upstream_code",
             ref=f"{ENVIRONMENT}:50"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime's software latch refuses step, reset "
                  "and seed until mhs.safety.reset clears it; no native stop method exists in a simulated "
                  "Environment, and the state stays readable")
    #: The complete fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is a stand-in
    #: for the upstream Environment, not a second model: the gaps say exactly where it is not the upstream simulator.
    fidelity = {
        "engine": "pybullet",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "notes": "Environment.seed() only seeds the camera-noise generator (environment.py:175-177) and the "
                     "default camera configuration has noise disabled (cameras.py:41-73); task resets draw from the "
                     "global numpy RNG, so this package makes no seed-replay claim for the upstream model.  The fake "
                     "does repeat a trajectory for a given seed, but that is test data and not a device guarantee.",
        },
        "timestep_ms": 4.166666666666667,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the timestep is the upstream constructor default hz=240 (environment.py:50, :138); hz is an option and "
            "a deployment can change it, so the published timestep is not a bound of the environment",
            "the fake backend does not run PyBullet and models no contacts, actuator dynamics, grasp physics, task "
            "rewards or terminal conditions; it returns a constant reward without a terminal condition",
            "the fake returns placeholder RGB-D arrays for the three cameras, smaller than the upstream "
            "RealSenseD415 480 by 640 color and depth images (cameras.py:27-28, :41-73); the image content is a "
            "stand-in",
            "no wall-clock pacing: realtime_factor 0, and one tick advances only the bridge's step counter, not the "
            "modelled physics timestep",
            "the bridge derives no per-element limits for the Tuple pose actions (simulation-only residual): the "
            "position and rotation boxes of environment.py:89-103 are not enforced by the step input schema",
            "the fake was not compared with the upstream environment and no upstream run was made; the clone needs "
            "the PyBullet stack and its asset tree, which the gate cannot import",
            "no physical device is modelled and no hardware backend exists for this simulator",
            "snapshot and restore are not offered: Environment exposes no get_state/set_state",
        ],
    }
