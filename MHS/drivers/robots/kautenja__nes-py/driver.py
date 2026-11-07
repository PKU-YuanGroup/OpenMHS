"""OpenMHS driver for gh.kautenja/nes-py: the NESEnv environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: the bridge derives the contract from the environment's spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by the environment's
``Discrete(256)`` button bitmap, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The environment is simulated (R0): there is no hardware backend, no path to a machine and no
operator-required limit.

The upstream ``NESEnv`` needs its native C++ extension and a legally obtained ROM, and package code never imports
the clone.  The ``fake`` backend is therefore the package's own pure Python stand-in (see fake.py).  A backend name
that ``backends`` does not list (``sim``) would be served by ``gymnasium.make(env_id)`` (GymnasiumDriver
.open_native), but this class is not registered with Gymnasium and that path was not run.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
fact cites a line of the clone at the pinned commit (8d27b099f24a57afaac7339fab7ec0f1f96a59c8).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

NES_ENV = "nes_py/nes_env.py"
OBS_DOC = "docs/ml-observation-fast-paths.md"


class NESPy(GymnasiumDriver):
    device_id = "nes-py"
    native = "nes_py.nes_env:NESEnv"
    backends = {"fake": ".fake:FakeNESEnv"}
    display_name = "nes-py NES environment"
    vendor, model = "Kautenja", "nes-py"
    tags = ["nes", "emulator", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("NESEnv is a Gymnasium environment (class NESEnv(gym.Env))", source="upstream_code",
             ref=f"{NES_ENV}:48"),
        Fact("The action space is Discrete(256), a bitmap of button press values for the 8 NES buttons",
             source="upstream_code", ref=f"{NES_ENV}:68-69"),
        Fact("The observation space is Box(low=0, high=255, shape=SCREEN_SHAPE_24_BIT, dtype=uint8)",
             source="upstream_code", ref=f"{NES_ENV}:61-66"),
        Fact("The default observation and the rgb_array render are the zero-copy (240, 256, 3) uint8 RGB "
             "screen view", source="vendor_doc", ref=f"{OBS_DOC}:5-6"),
        Fact("The metadata declares the render modes rgb_array and human and render_fps 60", source="upstream_code",
             ref=f"{NES_ENV}:52-55"),
        Fact("reset accepts an optional seed and options, calls super().reset(seed=seed) and the native reset, "
             "and returns the screen and info", source="upstream_code", ref=f"{NES_ENV}:264-291"),
        Fact("step refuses to run in a done environment, advances the emulator by one frame, and returns the "
             "screen, reward, terminated, truncated and info", source="upstream_code", ref=f"{NES_ENV}:313-334"),
        Fact("The base hooks return reward 0, no termination and no truncation unless a subclass overrides them",
             source="upstream_code", ref=f"{NES_ENV}:336-351"),
        Fact("The reward range is unbounded from -inf to inf", source="upstream_code", ref=f"{NES_ENV}:57-58"),
        Fact("seed() is deprecated in favour of reset(seed=...)", source="upstream_code", ref=f"{NES_ENV}:243-260"),
        Fact("close closes the native emulator and any viewer", source="upstream_code", ref=f"{NES_ENV}:374-385"),
        Fact("render returns the screen in rgb_array mode", source="upstream_code", ref=f"{NES_ENV}:415-416"),
        Fact("dump_state and load_state carry an opaque native snapshot and restore it", source="upstream_code",
             ref=f"{NES_ENV}:214-225"),
        Fact("get_action_meanings returns ['NOOP'] for the base class", source="upstream_code",
             ref=f"{NES_ENV}:452-454"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the frame state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "nes-py:NESEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) seeds the Gymnasium random generator (nes_env.py:278); the base NESEnv does "
                     "not use that seed to reset the native emulator (nes_env.py:285), so every reset of the base "
                     "class starts from the same reset frame and a seed repeats a trajectory. The fake backend "
                     "also resets to the same start frame.",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure Python stand-in for the native C++ emulator core: it does not emulate the CPU, "
            "PPU, mappers, RAM, controllers or audio, and it returns reward 0 with terminated and truncated false "
            "like the base NESEnv hooks; it was not compared with the upstream environment",
            "the fake returns a 24 x 32 x 3 uint8 stand-in for the real 240 x 256 x 3 NES frame "
            "(docs/ml-observation-fast-paths.md:5-6); the resolution is scaled down to keep receipts small",
            "one tick advances one emulator frame; the declared render_fps is 60 (nes_env.py:54), so timestep_ms "
            "is 1000/60; no wall-clock pacing is applied (realtime_factor 0)",
            "snapshot and restore are not offered: NESEnv has dump_state/load_state (nes_env.py:214-225), but the "
            "gymnasium bridge publishes a snapshot only for get_state/set_state, which NESEnv does not have",
            "a .nes ROM is required by the upstream constructor and is not supplied; the fake accepts an optional "
            "ROM path and does not read it",
            "no physical device is modelled and nothing was validated against one",
        ],
    }
