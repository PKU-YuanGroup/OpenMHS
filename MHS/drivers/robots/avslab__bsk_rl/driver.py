"""OpenMHS driver for gh.avslab/bsk_rl: the SatelliteTasking-v1 Gymnasium environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by
the environment's discrete action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The upstream action space is a property of the satellite configuration, not a fixed number of the environment: a
satellite subclass names an ``action_spec`` and the discrete builder sums each action's ``n_actions``
(``src/bsk_rl/act/discrete_actions.py:34-37``).  The package therefore declares no Limit of its own; the bridge
derives ``action.index`` from the live environment that the fake backend serves (a test configuration, see ``fake.py``
and the notes of ``RESULT.json``), exactly as the Gymnasium family does for any environment.

The gate does not import bsk_rl (its Basilisk dependency and the whole upstream simulation are never imported by
package code), so the ``fake`` backend is the package's own pure Python tasking stand-in.  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id, **env_kwargs)`` (GymnasiumDriver
.open_native); that path needs an installed upstream package and, because SatelliteTasking takes a satellite
instance, a configured satellite in ``env_kwargs``.  It was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
the checked model is the analytic fake, so the level is F0 and ``timestep_ms`` is 0 (event-driven environment steps).
Every Fact cites a line of the clone at the pinned commit (e307f335a3f133ef6dc528a9bb3b2ceb06329605); the fake's
configuration numbers are test data and are not facts or limits.  This package is model-authored and unreviewed: it
is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM = "src/bsk_rl/gym.py"
ACT = "src/bsk_rl/act/discrete_actions.py"
OBS = "src/bsk_rl/obs/observations.py"
REGISTER = "src/bsk_rl/__init__.py"
SAT = "src/bsk_rl/sats/satellite.py"
SATS_DOC = "src/bsk_rl/sats/__init__.py"
DATA = "src/bsk_rl/data/unique_image_data.py"


class BskSatelliteTasking(GymnasiumDriver):
    device_id = "satellite_tasking"
    env_id = "SatelliteTasking-v1"
    native = "bsk_rl.gym:SatelliteTasking"
    backends = {"fake": ".fake:FakeSatelliteTasking"}
    display_name = "bsk_rl SatelliteTasking-v1 (satellite tasking simulation)"
    vendor, model = "AVS Lab", "SatelliteTasking-v1"
    tags = ["satellite", "tasking", "astrodynamics", "basilisk", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("SatelliteTasking-v1 is registered to bsk_rl.gym:SatelliteTasking", source="upstream_code",
             ref=f"{REGISTER}:22-25"),
        Fact("SatelliteTasking is the single-satellite special case of GeneralSatelliteTasking and exposes the "
             "satellite's action space directly", source="upstream_code", ref=f"{GYM}:582-604"),
        Fact("SatelliteTasking exposes the satellite's observation space directly", source="upstream_code",
             ref=f"{GYM}:606-610"),
        Fact("SatelliteTasking refuses to be constructed with anything but exactly one satellite",
             source="upstream_code", ref=f"{GYM}:595-599"),
        Fact("The multi-satellite base composes a Tuple of the satellites' action spaces", source="upstream_code",
             ref=f"{GYM}:480-487"),
        Fact("The multi-satellite observation space composes the satellites' observation spaces and calls reset() "
             "when no simulator exists yet", source="upstream_code", ref=f"{GYM}:489-505"),
        Fact("A satellite subclass defines observation_spec and action_spec, which determine its observation and "
             "action spaces", source="upstream_code", ref=f"{SATS_DOC}:9-12"),
        Fact("The documented construction passes a configured satellite instance to "
             "gymnasium.make('SatelliteTasking-v1', ...)", source="upstream_code", ref=f"{SATS_DOC}:32"),
        Fact("With a discrete action spec the satellite's action space is Discrete(sum of each action's n_actions)",
             source="upstream_code", ref=f"{ACT}:34-37"),
        Fact("An integer action outside the discrete action space raises ValueError('Action index ... out of "
             "range')", source="upstream_code", ref=f"{ACT}:84"),
        Fact("Downlink is a DiscreteFSWAction", source="upstream_code", ref=f"{ACT}:218"),
        Fact("DiscreteFSWAction contributes one discrete action (n_actions=1)", source="upstream_code",
             ref=f"{ACT}:139"),
        Fact("Image is a DiscreteAction and Image(n_ahead_image) contributes n_ahead_image discrete actions",
             source="upstream_code", ref=f"{ACT}:244-272"),
        Fact("A list observation becomes Box(low=-1e16, high=1e16, shape=(len,)) and a scalar observation becomes a "
             "Box of shape (1,)", source="upstream_code", ref=f"{OBS}:43-48"),
        Fact("A Time observation returns the simulation time divided by its normalization, and the normalization is "
             "the time limit when norm is not set", source="upstream_code", ref=f"{OBS}:298-311"),
        Fact("The observation builder derives its space from the first observation it builds", source="upstream_code",
             ref=f"{OBS}:150-154"),
        Fact("reset stores self.seed, calls gymnasium's Env.reset(seed) and numpy.random.seed; a missing seed is "
             "time_ns() % 2**32", source="upstream_code", ref=f"{GYM}:341-346"),
        Fact("The reset options argument is unused", source="upstream_code", ref=f"{GYM}:331-333"),
        Fact("Each reset sets latest_step_duration to 0.0 s", source="upstream_code", ref=f"{GYM}:356"),
        Fact("reset returns the observation and the info mapping", source="upstream_code", ref=f"{GYM}:408-411"),
        Fact("A step applies a non-no-action action through Satellite.set_action and then runs the simulator",
             source="upstream_code", ref=f"{GYM}:514-527"),
        Fact("Satellite.set_action forwards the action to its action builder", source="upstream_code",
             ref=f"{SAT}:320-326"),
        Fact("Each step measures latest_step_duration as the change in simulator time", source="upstream_code",
             ref=f"{GYM}:525-527"),
        Fact("The step reward is the sum of the rewarder's reward_dict plus failure_penalty for each dead satellite",
             source="upstream_code", ref=f"{GYM}:456-462"),
        Fact("The episode terminates when a satellite is not alive or its rewarder terminates",
             source="upstream_code", ref=f"{GYM}:464-472"),
        Fact("The episode truncates when simulator time reaches time_limit or a rewarder truncates",
             source="upstream_code", ref=f"{GYM}:474-478"),
        Fact("The step returns observation, reward, terminated, truncated and info", source="upstream_code",
             ref=f"{GYM}:556-570"),
        Fact("info reports each satellite's requires_retasking and the last step duration as d_ts",
             source="upstream_code", ref=f"{GYM}:443-454"),
        Fact("SatelliteTasking flattens the satellite's info entries to the top level of the step info",
             source="upstream_code", ref=f"{GYM}:624-629"),
        Fact("A single-satellite step wraps the scalar action in a one-element list", source="upstream_code",
             ref=f"{GYM}:617-619"),
        Fact("close deletes the simulator when one exists", source="upstream_code", ref=f"{GYM}:576-579"),
        Fact("UniqueImageReward rewards each newly imaged target by its priority, once per target",
             source="upstream_code", ref=f"{DATA}:192-199"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "bsk_rl:SatelliteTasking-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the checked stand-in's random generator and the tasking rules are "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; "
                     "upstream seeds numpy's global generator (src/bsk_rl/gym.py:346) while the fake uses Python's "
                     "random.Random, so a seed does not give the same trajectory on the two implementations",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked model is the package's analytic stand-in: it models the tasking state (action index, "
            "stored data and simulated time) directly and has no orbital, attitude, power, thermal, sensor or "
            "actuator dynamics, so its fidelity level is F0",
            "the upstream environment propagates a Basilisk astrodynamics and FSW simulation; that engine is not "
            "imported by this package and was not run here",
            "the fake's satellite is a test configuration (one Downlink and ten Image actions with a Time "
            "observation); every number in fake.py is test data, and the concrete action count belongs to that "
            "configuration, not to the upstream environment, whose action space is the configured satellite's",
            "timestep_ms is 0 because an environment step is event-driven: upstream steps end at FSW events or at "
            "max_step_duration, while the fake advances a fixed number of simulated seconds per step",
            "the fake uses Python's random.Random while upstream seeds numpy's global generator, so a seed does not "
            "give the same trajectory on the two implementations",
            "snapshot and restore are not offered: upstream exposes no get_state/set_state, so the bridge declares "
            "snapshot_restore false and replay is not available",
            "the sim backend (gymnasium.make) needs installed bsk_rl and Basilisk and a configured satellite "
            "instance in env_kwargs; it was not run here",
        ],
    }
