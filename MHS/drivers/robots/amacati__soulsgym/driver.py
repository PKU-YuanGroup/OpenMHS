"""OpenMHS driver for gh.amacati/soulsgym: the Iudex Gundyr boss-fight environment (a Gymnasium family driver).

SoulsGym turns a running Dark Souls III game into Gymnasium environments by reading and writing game memory.  The
card's entry symbols are the environments themselves, so this is a ``GymnasiumDriver``: ``env_id`` names the registered
environment and the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the
environment's spaces (``Discrete`` over the game's action table, a ``Dict`` observation).

The gate cannot import the clone (it is Windows game-memory code and needs a running game), so ``backends`` names the
package's own pure Python fake.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs ``soulsgym`` imported for the registration
and a running Dark Souls III, and was not run here (README.md).

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002): every member of
``device.schema.json`` that applies to an analytic simulator without a physical counterpart.  Every constant, rule and
bound cites a line of the clone at the pinned commit (29c94d89ac8a47846c619019296d0ba55c6e80d5).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

IUDEX = "soulsgym/envs/darksouls3/iudex.py"
SOULSENV = "soulsgym/envs/soulsenv.py"
ACTIONS = "soulsgym/core/data/darksouls3/actions.yaml"


class SoulsGymIudex(GymnasiumDriver):
    device_id = "soulsgym-iudex"
    env_id = "SoulsGymIudex-v0"
    native = "soulsgym.envs.darksouls3.iudex:IudexEnv"
    backends = {"fake": ".fake:FakeIudexEnv"}
    display_name = "SoulsGym Iudex Gundyr (Dark Souls III)"
    vendor, model = "amacati", "SoulsGymIudex-v0"
    mode, risk = "simulated", "R0"
    tags = ["soulsgym", "dark-souls-iii", "boss-fight", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The Iudex environment is registered as SoulsGymIudex-v0 with max_episode_steps=3000 and "
             "nondeterministic=True", source="upstream_code", ref="soulsgym/__init__.py:51-54"),
        Fact("The Iudex observation is a Dict of 15 members: phase, player HP/SP and max HP/SP, boss HP and max HP, "
             "player/boss/camera poses, player/boss animations and durations, and lock_on", source="upstream_code",
             ref=f"{IUDEX}:97-115"),
        Fact("The Iudex action space is a Discrete space over the game's action table", source="upstream_code",
             ref=f"{IUDEX}:116"),
        Fact("The game action table maps 0-7 to walking, 8-15 to rolling, 16 and 17 to light and heavy attacks, 18 to "
             "parry and 19 to no action", source="upstream_code", ref=f"{ACTIONS}:1-25"),
        Fact("SoulsEnv.step_size is 0.1 seconds between each step", source="upstream_code", ref=f"{SOULSENV}:61"),
        Fact("SoulsEnv.step returns (observation, reward, terminated, False, info) and raises ResetNeeded when called "
             "after the episode terminated", source="upstream_code", ref=f"{SOULSENV}:141-166"),
        Fact("The episode terminates when the player HP or the boss HP reaches zero", source="upstream_code",
             ref=f"{SOULSENV}:413"),
        Fact("The Iudex reward is boss damage over boss max HP plus the player HP change over player max HP, with a "
             "+-0.1 terminal bonus and a small distance-to-centre shaping term", source="upstream_code",
             ref=f"{IUDEX}:388-400"),
        Fact("IudexEnv.reset accepts seed and options but does not use them, and it sets the player and boss to their "
             "fixed start poses", source="upstream_code", ref=f"{IUDEX}:193-224"),
        Fact("The README states that the environments are nondeterministic and cannot provide reproducible results by "
             "setting RNG seeds", source="vendor_doc", ref="README.md:37"),
        Fact("The README requires the latest Dark Souls III running, on Windows or on Linux under Proton/Wine",
             source="vendor_doc", ref="README.md:16-22"),
        Fact("SoulsEnv constructs a GameInput, a GameWindow and a game interface, and refuses to initialize when the "
             "player is not loaded into the game", source="upstream_code", ref=f"{SOULSENV}:78-84"),
        Fact("SoulsEnv.close resumes the game, restores the altered game properties and kills the player to force a "
             "reload", source="upstream_code", ref=f"{SOULSENV}:168-185"),
        Fact("SoulsEnv.render is a no-op because the game window must already be open", source="upstream_code",
             ref=f"{SOULSENV}:229-234"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the fake keeps its state and makes no native stop call")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is an analytic
    #: stand-in, not the game: it advances HP, poses and ticks directly and has no physics, rendering or game memory.
    fidelity = {
        "engine": "soulsgym:IudexEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "this package's fake lays out an episode from the reset/seed value, so one seed repeats its "
                     "trajectory; upstream SoulsGym cannot control the game's randomness (soulsenv.py:211-227) and "
                     "IudexEnv.reset ignores seed and options (iudex.py:193-224), so the claim covers the fake only",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic F0 model: HP, poses, actions and ticks advance directly; there is no physics, collision, "
            "contact, actuator, sensor or noise model, and no game memory is read or written",
            "the real environment requires a running Dark Souls III on Windows or Linux under Proton/Wine and "
            "drives the game through its memory, input and window managers; the fake was not compared with a game",
            "observations are Python lists of placeholder values; the real observation is numpy arrays built from "
            "the game's HP, poses and animation tables",
            "seeded determinism is a property of the fake only: the game's reset ignores seed and options, and the "
            "README says RNG seeds cannot make SoulsGym reproducible",
            "the real reset teleports, reloads and enters the fog gate through game input; the fake resets its "
            "internal state synchronously",
            "no rendering (SoulsEnv.render is a no-op) and close only marks the fake closed; the real close kills "
            "the player and reloads the game",
            "the episode is truncated at the registration's 3000-step limit, which gymnasium.make applies as a "
            "TimeLimit wrapper; the fake reports truncation itself",
        ],
    }
