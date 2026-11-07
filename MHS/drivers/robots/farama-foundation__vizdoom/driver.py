"""OpenMHS driver for gh.farama-foundation/vizdoom: the ``VizdoomBasic-v1`` Gymnasium environment.

ViZDoom ships Gymnasium environments registered under the ``vizdoom.gymnasium_wrapper`` package; this package
serves the basic scenario.  A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered
environment, and the bridge derives the contract from the environment's spaces.  For ``VizdoomBasic-v1`` the
action space is a ``Discrete`` over the combinations of the scenario's three binary buttons with at most one
button pressed, and the observation is a ``Dict`` with the screen image and the game variables (AMMO2).

The device is a simulated game (R0).  There is no hardware backend, no native stop and no operator-required
bound: the only bound is the action space, which the bridge derives from the environment.

``native`` is the card's second confirmed entry symbol, ``VizdoomEnv``: it defines ``reset``, ``step``, ``close``
and the spaces, while the registered entry point ``VizdoomScenarioEnv`` only resolves the scenario config path and
inherits that class.

The gate cannot import ViZDoom (it needs the compiled engine extension and gymnasium), so the ``fake`` backend is
the package's own analytic stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served
by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs the upstream package installed and
was not run here.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  Every
fact cites a line of the clone at the pinned commit 26a9958970a3b1069325cf9e00c4119a69664128.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "gymnasium_wrapper/base_gymnasium_env.py"
REGISTRY = "gymnasium_wrapper/__init__.py"
SCENARIO = "scenarios/basic.cfg"
CONSTS = "include/ViZDoomConsts.h"
TIMESTEP_MS = 1000.0 / 35.0


class VizdoomBasic(GymnasiumDriver):
    device_id = "vizdoom-basic"
    device_kind = "world.sim"
    env_id = "VizdoomBasic-v1"
    native = "vizdoom.gymnasium_wrapper.base_gymnasium_env:VizdoomEnv"
    backends = {"fake": ".fake:FakeVizdoomBasicEnv"}
    display_name = "ViZDoom Basic (Gymnasium)"
    vendor, model = "Farama Foundation", "ViZDoom Basic"
    tags = ["vizdoom", "doom", "gymnasium", "reinforcement-learning", "visual-rl", "simulation"]
    facts = [
        Fact("VizdoomScenarioEnv is defined as a subclass of VizdoomEnv", source="upstream_code",
             ref="gymnasium_wrapper/gymnasium_env_defns.py:32"),
        Fact("VizdoomBasic-v1 is registered with scenario_config_file basic.cfg and max_buttons_pressed 1",
             source="upstream_code", ref=f"{REGISTRY}:30-33"),
        Fact("The basic scenario declares three binary buttons: MOVE_LEFT, MOVE_RIGHT and ATTACK",
             source="upstream_code", ref=f"{SCENARIO}:30-35"),
        Fact("With max_buttons_pressed above zero the binary action space is Discrete(len(button_map)), where "
             "button_map holds the button combinations whose pressed count is at most max_buttons_pressed",
             source="upstream_code", ref=f"{BASE}:448-454"),
        Fact("The wrapper forces the screen format to RGB24 when the config selects neither RGB24 nor GRAY8, and "
             "records the channel count: 3 unless the format is GRAY8", source="upstream_code",
             ref=f"{BASE}:173-193"),
        Fact("The screen observation space is a uint8 Box of [screen height, screen width, channels]",
             source="upstream_code", ref=f"{BASE}:493-503"),
        Fact("The basic scenario renders at RES_320X240", source="upstream_code", ref=f"{SCENARIO}:14"),
        Fact("The observation dictionary always carries the screen and carries depth, labels, automap, audio, "
             "notifications and gamevariables only when they are enabled", source="upstream_code",
             ref=f"{BASE}:294-315"),
        Fact("The game variables are a float32 array with one element per available game variable",
             source="upstream_code", ref=f"{BASE}:553-560"),
        Fact("The only game variable enabled by the basic scenario is AMMO2", source="upstream_code",
             ref=f"{SCENARIO}:38"),
        Fact("step returns terminated from the game's episode-finished flag and truncated from its episode-timeout "
             "flag when treat_episode_timeout_as_truncation is true", source="upstream_code",
             ref=f"{BASE}:231-242"),
        Fact("On a terminal step there is no game state and the wrapper returns a zero observation instead",
             source="upstream_code", ref=f"{BASE}:316-324"),
        Fact("The basic scenario sets the living reward to -1", source="upstream_code", ref=f"{SCENARIO}:11"),
        Fact("The basic scenario finishes an episode after an episode_timeout of 300 tics", source="upstream_code",
             ref=f"{SCENARIO}:26-27"),
        Fact("The basic scenario starts an episode after episode_start_time 14 tics", source="upstream_code",
             ref=f"{SCENARIO}:23-24"),
        Fact("A reset seeds DoomGame with an unsigned 32-bit integer drawn from Gymnasium's generator",
             source="upstream_code", ref=f"{BASE}:280-284"),
        Fact("The default ViZDoom tic rate is 35 tics per second and the default frame time is 1/35 s",
             source="upstream_code", ref=f"{CONSTS}:34-37"),
        Fact("The default frame_skip is 1, so one step advances one frame", source="upstream_code",
             ref=f"{BASE}:67"),
    ]
    safe_state = ("the simulation is frozen: after an e-stop the runtime latch rejects every step and reset "
                  "until mhs.safety.reset clears it, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The model is analytic: it
    #: repeats the contract around the game (spaces, reward, timeout), not the game itself.
    fidelity = {
        "engine": "vizdoom:VizdoomBasic-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the fake's start state and the dynamics are a fixed counter, so one seed "
                     "and one action sequence repeat the fake's trajectory; upstream seeds DoomGame from "
                     "Gymnasium's generator and this fake uses Python's random.Random, so a seed does not give "
                     "the same trajectory on the two",
        },
        "timestep_ms": TIMESTEP_MS,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no Doom dynamics: no map, monster, hit detection, damage, weapon, movement physics or death model. "
            "The fake is an analytic stand-in (F0) whose actions only move a marker and decrement ammo, and "
            "terminated is always false",
            "the fake observation is smaller than the device's: an 8 x 8 x 3 screen and a one-element "
            "gamevariables array, where the real screen is 240 x 320 x 3 (basic.cfg:14) and AMMO2 is one "
            "game variable (basic.cfg:38)",
            "the 14-tic episode_start_time (basic.cfg:24) and ViZDoom's per-tic living-reward accounting are "
            "simplified: the fake pays one living reward per step and truncates after 300 steps (basic.cfg:27)",
            "no rendering is implemented and no snapshot or restore is offered; the upstream environment exposes "
            "no get_state/set_state either",
            "the fake was never compared with upstream ViZDoom: the compiled engine extension and gymnasium were "
            "not importable where the gate ran, and the sim backend (gymnasium.make) was not run",
        ],
    }
