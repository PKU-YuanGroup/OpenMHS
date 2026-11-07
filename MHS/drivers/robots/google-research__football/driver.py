"""OpenMHS driver for gh.google-research/football: a Google Research Football environment (Gymnasium family).

The card's entry symbol is ``gfootball.env:create_environment`` (registered as ``GFootball-{env_name}-*-v0`` in
``gfootball/__init__.py:23-58``).  That symbol is a factory function, not a class, and gate G7 checks the fake
against the class named by ``native``; this driver therefore names the class the factory builds,
``gfootball.env.football_env:FootballEnv``, and records the resulting ``G7.NOT_AN_ENTRY_SYMBOL`` warning in
``RESULT.json``.  The registered environment served here is
``GFootball-11_vs_11_stochastic-simple115-v0``: a single agent-controlled player and the simple115 observation.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.index`` bounded 0..18 by
the environment's Discrete action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): no hardware backend, no e-stop path to a machine
and no operator-required bound.

The upstream environment needs the C++ ``gfootball_engine``, OpenCV, gym and numpy (see ``requirements.txt``), so the
gate's ``fake`` backend is the package's own kinematic stand-in in ``fake.py``.  A backend name that ``backends``
does not list (``sim``) would be served by ``gym.make(env_id)`` (GymnasiumDriver.open_native); that path needs the
upstream package and was not run here.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002): the fake's kinematic
simple115 model, not the C++ engine.  The gaps say what is missing and that nothing was compared with an upstream
run.  Every constant and rule cites a line of the clone at the pinned commit
3d9e754720a95621bba6475c4d3b0d56fe919014.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver


class Football(GymnasiumDriver):
    device_id = "gfootball"
    env_id = "GFootball-11_vs_11_stochastic-simple115-v0"
    native = "gfootball.env.football_env:FootballEnv"
    backends = {"fake": ".fake:FakeFootballEnv"}
    display_name = "Google Research Football (GFootball simple115)"
    vendor, model = "Google Research", "Google Research Football (GFootball)"
    tags = ["football", "gfootball", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The registered environment ids are built for every scenario name as GFootball-{env_name}-SMM-v0, "
             "GFootball-{env_name}-Pixels-v0, GFootball-{env_name}-simple115-v0 and "
             "GFootball-{env_name}-simple115v2-v0, with entry point gfootball.env:create_environment",
             source="upstream_code", ref="gfootball/__init__.py:23-58"),
        Fact("create_environment constructs football_env.FootballEnv(c) and calls _apply_output_wrappers before "
             "returning it", source="upstream_code", ref="gfootball/env/__init__.py:212-225"),
        Fact("The output wrapper chain applies the reward, representation, single-agent and GetState wrappers",
             source="upstream_code", ref="gfootball/env/__init__.py:76-86"),
        Fact("FootballEnv.action_space is Discrete(action-set length) when one player is agent-controlled",
             source="upstream_code", ref="gfootball/env/football_env.py:49-57"),
        Fact("The default action set is action_set_v1: 19 actions from idle through release_dribble",
             source="upstream_code", ref="gfootball/env/football_action_set.py:129-135"),
        Fact("The default config action_set is 'default'", source="upstream_code",
             ref="gfootball/env/config.py:87"),
        Fact("The simple115 observation is a Box with 115 values per controlled player, float32, bounds -inf to "
             "inf", source="upstream_code", ref="gfootball/env/wrappers.py:108-111"),
        Fact("The simple115 layout is 88 player values (backfilled with -1 when fewer than 11 players), then the "
             "ball position array, the ball direction array, a 3-value possession one-hot, 11 active-player flags "
             "and 7 game-mode flags", source="upstream_code", ref="gfootball/env/wrappers.py:161-188"),
        Fact("The raw observation's ball position and ball direction are each arrays of three values",
             source="upstream_code", ref="gfootball/env/football_env_core.py:296-304"),
        Fact("The 11_vs_11_stochastic scenario sets game_duration 3000 and deterministic False",
             source="upstream_code", ref="gfootball/scenarios/11_vs_11_stochastic.py:23-25"),
        Fact("The episode is done when the step count reaches game_duration", source="upstream_code",
             ref="gfootball/env/football_env_core.py:238-242"),
        Fact("FootballEnv.step returns observation, reward, done and info; reset returns the observation",
             source="upstream_code", ref="gfootball/env/football_env.py:183-190"),
        Fact("The engine runs 100 physics steps per second", source="upstream_code",
             ref="gfootball/env/constants.py:20-21"),
        Fact("The default config advances 10 physics steps per frame", source="upstream_code",
             ref="gfootball/env/config.py:94"),
        Fact("The default config is not real-time paced (real_time False)", source="upstream_code",
             ref="gfootball/env/config.py:96"),
        Fact("The default config's player list is agent:left_players=1", source="upstream_code",
             ref="gfootball/env/config.py:92"),
        Fact("FootballEnvCore.reset starts a new episode and resets the action set and step counter",
             source="upstream_code", ref="gfootball/env/football_env_core.py:109-120"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gfootball:fake-simple115",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "the 11_vs_11_stochastic scenario sets deterministic False and the engine seed is drawn with "
                     "random.randint (scenario_builder.py:80-88); the package's fake is a repeatable stand-in but "
                     "the upstream reset() takes no seed or options, so no determinism claim is made",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no game engine: the fake is a kinematic stand-in that moves a placeholder ball; it models no players, "
            "contacts, goals, physics, rendering or the C++ engine and was never compared with an upstream run",
            "players are not modelled: the 88 player values keep the upstream backfill value -1 and the "
            "active-player one-hot is all zeros",
            "no reward is modelled: every step returns 0.0, so goals and score changes are absent",
            "one tick is one frame: 100 ms at the default 10 physics steps per frame and 100 physics steps per "
            "second; no wall-clock pacing (realtime_factor 0)",
            "the upstream reset() takes no seed or options and the fake matches that signature: the bridge's "
            "cap.world.seed.v1 and reset seed are recorded but cannot change the episode",
            "snapshot and restore are not offered: the fake does not implement the upstream get_state/set_state, "
            "so fidelity snapshot_restore is false",
        ],
    }
