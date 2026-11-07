"""OpenMHS driver for gh.farama-foundation/stable-retro: the RetroEnv Gymnasium environment.

``stable_retro.retro_env:RetroEnv`` is a ``gymnasium.Env`` (``retro_env.py:16``) that turns an emulated classic
console game into a reinforcement-learning environment.  A ``GymnasiumDriver`` is configuration only: the bridge
derives ``cap.world.step.v1`` (``{ticks, action}``), ``cap.world.reset.v1`` (``{seed, options}``) and
``cap.world.seed.v1`` (``{seed}``) from the environment's spaces, so the driver declares no parameters, writes or
limits of its own.  The device is simulated (R0): there is no hardware backend and no stop path to a machine.

Stable Retro registers no Gymnasium environment id; the documented factory is ``stable_retro.make(game)``
(``stable_retro/__init__.py:56-72``).  The acceptance run therefore serves the package's own pure Python fake
(``.fake:FakeRetroEnv``); a backend that ``backends`` does not list (``sim``) would make the bridge call
``gymnasium.make(env_id)`` with ``env_id`` unset and fail with ``MHS.DEVICE.NOT_READY`` (GymnasiumDriver.open_native).
The upstream environment cannot be opened in the gate: it needs the stable-retro extension modules, an emulator core
and a ROM (``README.md:115-132``), and package code never imports the clone, so the upstream simulator path was not run.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit (e2fdb2a6d39f942d21d5b7f4b3b9929808739eab).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "stable_retro/retro_env.py"


class StableRetro(GymnasiumDriver):
    device_id = "stable-retro"
    #: stable-retro registers no gymnasium.make id; its factory is stable_retro.make(game) (__init__.py:56-72).
    env_id = None
    native = "stable_retro.retro_env:RetroEnv"
    backends = {"fake": ".fake:FakeRetroEnv"}
    display_name = "Stable Retro (Gymnasium console emulation)"
    vendor, model = "Farama Foundation", "RetroEnv"
    tags = ["retro", "emulator", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("RetroEnv is a gymnasium.Env subclass that provides a Gym interface to classic video games",
             source="upstream_code", ref=f"{ENV}:16-21"),
        Fact("The environment metadata declares the render modes human and rgb_array and 60.0 video frames per second",
             source="upstream_code", ref=f"{ENV}:23"),
        Fact("The constructor defaults to Actions.FILTERED restricted actions, one player, Observations.IMAGE and "
             "render_mode human", source="upstream_code", ref=f"{ENV}:31-36"),
        Fact("The buttons of a game come from the emulator core metadata and their count is num_buttons",
             source="upstream_code", ref=f"{ENV}:128-130"),
        Fact("With the default restricted-actions mode the action space is MultiBinary(num_buttons * players)",
             source="upstream_code", ref=f"{ENV}:154-155"),
        Fact("The observation space is Box(low=0, high=255) with the shape of the screen or RAM buffer and dtype "
             "uint8", source="upstream_code", ref=f"{ENV}:157-167"),
        Fact("The observation is an RGB image from the emulator screen by default; obs_type RAM returns the RAM "
             "buffer instead", source="upstream_code", ref=f"{ENV}:180-188"),
        Fact("The default observations are RGB images of the game, and RAM values can be viewed instead",
             source="vendor_doc", ref="docs/python.md:35"),
        Fact("step advances one emulator frame and returns (observation, reward, bool(done), False, dict(info))",
             source="upstream_code", ref=f"{ENV}:236-257"),
        Fact("reset accepts seed and options and seeds gymnasium's RNG with super().reset(seed=seed); it restores "
             "the initial state, presses no buttons, advances the emulator once and returns (observation, {})",
             source="upstream_code", ref=f"{ENV}:259-285"),
        Fact("Reward and done come from the game data (current_reward and is_done) and info is lookup_all",
             source="upstream_code", ref=f"{ENV}:366-373"),
        Fact("The screen is cropped to the game's crop_info rectangle and optionally rotation-corrected",
             source="upstream_code", ref=f"{ENV}:333-351"),
        Fact("close deletes the emulator and closes the viewer", source="upstream_code", ref=f"{ENV}:304-309"),
        Fact("stable_retro.make() checks the ROM file path and returns RetroEnv(game, state, inttype=inttype, "
             "**kwargs)", source="upstream_code", ref="stable_retro/__init__.py:56-72"),
        Fact("The README says ROMs are not included and must be obtained and imported, and names one "
             "non-commercial Airstriker Genesis ROM included for testing",
             source="vendor_doc", ref="README.md:115-132"),
        Fact("The emulators are deterministic, so playback of a recorded button sequence gives the same output each "
             "time", source="vendor_doc", ref="docs/python.md:51"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latch refuses step and reset after an e-stop until "
                  "mhs.safety.reset clears it, and the fake keeps its state readable")
    fidelity = {
        "engine": "stable-retro:RetroEnv",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds gymnasium's RNG (retro_env.py:261) while the emulator state comes from the "
                     "game's savestate (retro_env.py:263-267), and the emulators are deterministic for the same "
                     "actions (docs/python.md:51); the fake mirrors a fixed game state and is deterministic too",
        },
        # One step advances one emulator frame, and the environment metadata declares 60.0 frames per second
        # (retro_env.py:23, :237).
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no emulator core, game data or ROM handling is modelled: the fake backend is pure Python and its "
            "rewards, termination and info are test data, not a game's scenario rules (retro_env.py:366-373)",
            "the fake returns a flat 60-element uint8 stand-in for an RGB frame; the real screen shape depends on "
            "the emulator core and the game's crop_info (retro_env.py:157-161, 333-351)",
            "no rendering is modelled: render() is not implemented by the fake; only observations are served",
            "the seed seeds gymnasium's RNG, not the emulator (retro_env.py:261-267); the fake mirrors a fixed "
            "state and does not draw a random start state",
            "snapshot and restore are not offered: RetroEnv exposes no get_state/set_state, so the bridge reports "
            "snapshot_restore false",
            "the fake was never compared with the upstream emulator; the upstream environment was not run here",
        ],
    }
