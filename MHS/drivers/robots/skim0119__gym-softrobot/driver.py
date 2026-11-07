"""OpenMHS driver for gh.skim0119/gym-softrobot: the OctoMuscleCrawl-v0 environment (Gymnasium family).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the action and observation spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where ``action`` is
``{"values": [...]}`` with ``n_arms * n_channels`` entries in ``[-1, 1]``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): no hardware backend
exists, no e-stop reaches a machine and no operator-required limit is declared.

The gate runs without the upstream stack (gymnasium, numpy, PyElastica, COOMM and the other dependencies in
pyproject.toml:20-29), so the ``fake`` backend is the package's own pure-Python point-mass surrogate in fake.py.  A
backend name that ``backends`` does not list (``sim``) would be served by ``gymnasium.make(env_id)`` through
``GymnasiumDriver.open_native``; that upstream path was not run here.  The fidelity contract therefore describes the
fake as deployed (F0, kinematic/analytic) and its gaps say what it does not model.

This package is model-authored and unreviewed; it is checked on the fake backend only.  Every Fact cites a text file
of the clone at the pinned commit e4a73ed86191747f4d0af56e612a6e339e952448.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_softrobot/envs/octopus/muscle_crawl_env.py"
CONFIG = "gym_softrobot/envs/octopus/crawling_simulation/config.py"
PHASE = "gym_softrobot/envs/octopus/crawling_simulation/phase_simulation.py"
DOC = "docs/envs/octopus_muscle.md"
REGISTER = "gym_softrobot/__init__.py"


class OctoMuscleCrawl(GymnasiumDriver):
    device_id = "octo-muscle-crawl"
    env_id = "OctoMuscleCrawl-v0"
    native = "gym_softrobot.envs.octopus:OctoMuscleCrawlEnv"
    backends = {"fake": ".fake:FakeOctoMuscleCrawlEnv"}
    display_name = "gym-softrobot OctoMuscleCrawl-v0 (eight-arm soft crawler)"
    vendor, model = "skim0119", "gym-softrobot"
    tags = ["octopus", "soft-robot", "cosserat", "crawling", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("OctoMuscleCrawl-v0 registers the environment gym_softrobot.envs.octopus:OctoMuscleCrawlEnv",
             source="upstream_code", ref=f"{REGISTER}:27-30"),
        Fact("The default configuration has 8 arms", source="upstream_code", ref=f"{CONFIG}:23"),
        Fact("OctopusMuscleConfig sets n_channels to 9", source="upstream_code", ref=f"{CONFIG}:163-164"),
        Fact("The action space is a Box from -1.0 to 1.0 with shape (n_arms, n_channels)",
             source="upstream_code", ref=f"{ENV}:52-57"),
        Fact("The observation space is a Box with shape (6,)", source="upstream_code", ref=f"{ENV}:58-63"),
        Fact("The observation is the central body's displacement from its reset pose (3 values) followed by its "
             "translational velocity (3 values)", source="vendor_doc", ref=f"{DOC}:123-130"),
        Fact("One step advances the simulation by one control interval, control_dt", source="upstream_code",
             ref=f"{ENV}:103"),
        Fact("The default control interval control_dt is 1/60 s", source="upstream_code", ref=f"{CONFIG}:95"),
        Fact("The default horizon is the number of control intervals in episode_duration_s",
             source="upstream_code", ref=f"{ENV}:47-49"),
        Fact("The default episode duration is five cycles of T_L = 2.4 s, 12 s", source="upstream_code",
             ref=f"{CONFIG}:93-101"),
        Fact("The default episode is 720 steps at 60 Hz", source="vendor_doc", ref=f"{DOC}:151-153"),
        Fact("The per-step reward is forward progress along -z divided by base_length minus lateral_penalty times "
             "the absolute lateral deviation divided by base_length", source="upstream_code", ref=f"{ENV}:107-110"),
        Fact("base_length is 0.45 m", source="upstream_code", ref=f"{CONFIG}:29"),
        Fact("lateral_penalty is 0.5", source="upstream_code", ref=f"{CONFIG}:106"),
        Fact("A non-finite simulation sets terminated and reaching the horizon sets truncated",
             source="upstream_code", ref=f"{ENV}:111-112"),
        Fact("reset(seed) seeds the environment random generator and returns the observation with an info dict that "
             "reports time", source="upstream_code", ref=f"{ENV}:87-95"),
        Fact("The simulation uses the Position Verlet integrator", source="upstream_code", ref=f"{PHASE}:123"),
        Fact("The default physics timestep is 3.0e-4 s", source="upstream_code", ref=f"{CONFIG}:94"),
        Fact("The robot is a rigid central sphere of radius 0.09 m with arms of length 0.45 m, base radius 0.02 m "
             "and 15 elements", source="upstream_code", ref=f"{CONFIG}:28-33"),
        Fact("Gravity acts in the negative y direction with -9.80665 m/s^2", source="upstream_code",
             ref=f"{CONFIG}:53"),
        Fact("Rod-rod contact is disabled by default", source="upstream_code", ref=f"{CONFIG}:87"),
        Fact("The environment supports an rgb_array render mode", source="upstream_code", ref=f"{ENV}:33"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step, reset or seed is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    #: Fidelity of the model as deployed: the fake is a kinematic point-mass surrogate, not the upstream elastica
    #: simulation.  The constants that remain are the upstream control interval and the lockstep clock.
    fidelity = {
        "engine": "gymnasium:OctoMuscleCrawl-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 reseeds the fake's Python random.Random; the fake then "
                     "integrates deterministically.  The upstream environment uses numpy's generator, so the same "
                     "seed does not reproduce the same trajectory across the two implementations",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0 kinematic/analytic surrogate: the fake integrates a point-mass central body with a hand-written "
            "force map; there are no Cosserat rods, no PyElastica or COOMM, and no contact, friction, suction or "
            "muscle dynamics, so forces and contacts are not modelled",
            "the action-to-force map is test data: the nine channels are not the TM/LM/OM muscle groups and the "
            "two suction bands of the upstream model",
            "the six-value observation is the surrogate body's displacement and velocity, not the elastica sphere "
            "pose; arm shape, muscle activation and suction state are not modelled",
            "the fake was not compared with the upstream environment: gym_softrobot needs gymnasium, numpy, "
            "PyElastica and COOMM (pyproject.toml:20-29) and was not importable where the gate ran; the sim "
            "backend was not run",
            "the fake does not render: render() returns None, while the upstream rgb_array renderer needs "
            "matplotlib",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
            "no wall-clock pacing: realtime_factor 0, only steps advance simulated time by timestep_ms",
        ],
    }
