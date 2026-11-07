"""OpenMHS driver for gh.pufferai/pokegym: the Pokemon Red Gymnasium environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: the bridge derives its contract from the environment's spaces.  The upstream
class is ``pokegym.environment:Environment``, a Gymnasium environment that drives a Pokemon Red ROM through the PyBoy
Game Boy emulator.  It is a simulated device (R0): no physical hardware, no e-stop path to a machine and no
operator-required limit.

The environment is not registered with ``gymnasium.make`` and its constructor needs the PyBoy emulator, a Pokemon Red
ROM, the ``skimage``/``mediapy``/``matplotlib`` packages and the save states under ``pokegym/current_state/`` (setup.py
``install_requires`` names only pyboy, gymnasium and numpy; the ROM is not in the clone).  This package therefore has
one backend, the pure Python stand-in in ``fake.py``; it does not offer the ``sim`` backend, which would call
``gymnasium.make(env_id)``.  The fake is not the ROM: it keeps the 8-button action space and returns a small synthetic
observation, and the fidelity ``gaps`` say so.  Both the upstream and this package are model-authored and unreviewed;
this package is checked on the fake backend only.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  Every fact cites a
line of the clone at the pinned commit 9050f7ae43e21b9337ac5ae407d37e6eb34ca03f.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVIRONMENT = "pokegym/environment.py"
BINDING = "pokegym/pyboy_binding.py"


class PokeGym(GymnasiumDriver):
    device_id = "pokegym"
    native = "pokegym.environment:Environment"
    backends = {"fake": ".fake:FakePokeGymEnv"}
    display_name = "PokeGym Pokemon Red (Gymnasium environment)"
    vendor, model = "PufferAI", "PokeGym Pokemon Red"
    tags = ["pokemon-red", "game-boy", "pyboy", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The entry class is Environment(Base), the Gymnasium environment class defined in environment.py",
             source="upstream_code", ref=f"{ENVIRONMENT}:374"),
        Fact("The action space is Discrete(len(ACTIONS))", source="upstream_code", ref=f"{ENVIRONMENT}:149"),
        Fact("ACTIONS is the eight-button tuple (Down, Left, Right, Up, A, B, Start, Select), so the discrete action "
             "index runs from 0 to 7", source="upstream_code", ref=f"{BINDING}:40"),
        Fact("The observation space is Box(low=0, high=255, dtype=np.uint8, shape=obs_size), where obs_size is the "
             "screen rows//2 and columns//2 plus four channels when use_screen_memory is true",
             source="upstream_code", ref=f"{ENVIRONMENT}:137-149"),
        Fact("The observation concatenates the downsampled screen with a fixed window of the per-map memory channel",
             source="upstream_code", ref=f"{ENVIRONMENT}:215-222"),
        Fact("reset has the signature reset(self, seed=None, options=None, max_episode_steps=20480, "
             "reward_scale=4.0) and its docstring says seeding is NOT supported", source="upstream_code",
             ref=f"{ENVIRONMENT}:618-619"),
        Fact("The first reset loads the first saved state; later resets do not reload it (the load happens only when "
             "reset_count == 0)", source="upstream_code", ref=f"{ENVIRONMENT}:620-621"),
        Fact("The default save state is current_state/Bulbasaur.state when state_path is None",
             source="upstream_code", ref=f"{ENVIRONMENT}:104-107"),
        Fact("step has the signature step(self, action, fast_video=True) and sends ACTIONS[action] to the emulator",
             source="upstream_code", ref=f"{ENVIRONMENT}:698-699"),
        Fact("One step runs the emulator for frame_skip=24 frames and releases the button after 8 frames",
             source="upstream_code", ref=f"{BINDING}:71-88"),
        Fact("self.time is incremented by one at every step", source="upstream_code", ref=f"{ENVIRONMENT}:700"),
        Fact("done is True when self.time >= self.max_episode_steps", source="upstream_code",
             ref=f"{ENVIRONMENT}:896"),
        Fact("step returns (observation, reward, done, done, info): the same done bool fills terminated and truncated",
             source="upstream_code", ref=f"{ENVIRONMENT}:1010"),
        Fact("The reward is the difference between the current cumulative reward_scale-scaled reward and the previous "
             "one; the first step returns 0", source="upstream_code", ref=f"{ENVIRONMENT}:863-894"),
        Fact("make_env hardcodes the ROM path to pokemon_red.gb in the working directory", source="upstream_code",
             ref=f"{BINDING}:42-43"),
        Fact("The package requires the pyboy, gymnasium and numpy packages", source="upstream_code",
             ref="setup.py:11-15"),
        Fact("The state files are found under pokegym/current_state/", source="upstream_code",
             ref=f"{ENVIRONMENT}:32"),
        Fact("The README instructs the user to copy pokemon_red.gb into the training directory", source="vendor_doc",
             ref="README.md:36"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pyboy:pokemon-red",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "the upstream reset ignores its seed (environment.py:618-619) and reloads the first save state "
                     "only on the first reset (environment.py:620-621), so a seed does not make a trajectory "
                     "repeatable; no determinism is claimed",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "the model is the Pokemon Red game running on the PyBoy Game Boy emulator: no physical device, forces, "
            "contacts, actuators or sensors are modelled (fidelity F0, no dynamics)",
            "the package's fake backend is a pure Python stand-in with the real 8-button action space but a synthetic "
            "8x8x4 uint8 observation; it does not emulate the ROM, the game's reward or the upstream 72x80x4 uint8 "
            "screen array (environment.py:137-149), and it was never compared with the upstream environment",
            "no wall-clock pacing: realtime_factor 0; one step advances the emulator 24 frames (pyboy_binding.py:71-88) "
            "but the clone states no frame duration, so timestep_ms is 0 and ticks are not converted to seconds",
            "reset is partial: the first reset loads the first save state, later resets keep the emulator's current "
            "game state (environment.py:620-621)",
            "snapshot and restore are not offered: the environment has save_state/load_first_state helpers but no "
            "get_state/set_state pair the bridge could use",
            "the ROM (pokemon_red.gb) and the emulator are not in the clone, so the upstream environment was never "
            "run here",
        ],
    }
