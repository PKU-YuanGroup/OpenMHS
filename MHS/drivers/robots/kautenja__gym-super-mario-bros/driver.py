"""OpenMHS driver for gh.kautenja/gym-super-mario-bros: the SuperMarioBros-v0 NES environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{index}`` bounded by the NES joypad ``Discrete(256)``; ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The gate cannot import the environment: nes-py is a native extension and the package requires CPython 3.13 or newer
(pyproject.toml:10 and :38-41), while package code never imports the clone.  The ``fake`` backend is therefore this
package's pure Python stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id, **env_kwargs)`` (GymnasiumDriver.open_native); that path needs the upstream package, its
native emulator and the bundled ROM, and was not run here.

Every Fact cites a line of the clone at commit 7ba17c778e1df8240fd1cf99dbe5238d0e9b93aa.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

SMB_ENV = "gym_super_mario_bros/smb_env.py"
REGISTRATION = "gym_super_mario_bros/_registration.py"
TEST_SMV = "gym_super_mario_bros/tests/test_smv_env.py"
DECODE_TARGET = "gym_super_mario_bros/_roms/decode_target.py"


class SuperMarioBros(GymnasiumDriver):
    device_id = "super-mario-bros"
    env_id = "SuperMarioBros-v0"
    native = "gym_super_mario_bros.smb_env:SuperMarioBrosEnv"
    backends = {"fake": ".fake:FakeSuperMarioBrosEnv"}
    display_name = "Gymnasium Super Mario Bros. (NES emulator)"
    vendor, model = "Christian Kauten", "SuperMarioBros-v0"
    tags = ["super-mario-bros", "nes", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The project is a Gymnasium environment for Super Mario Bros., Super Mario Bros. 2 (Lost Levels), "
             "Super Mario Bros. 2 (USA) and Super Mario Bros. 3 on the NES, running through the nes-py emulator",
             source="vendor_doc", ref="README.md:20-24"),
        Fact("By default the environments use the full NES action space of 256 discrete actions",
             source="vendor_doc", ref="README.md:50-53"),
        Fact("The legal reward range is -15 to 15", source="upstream_code", ref=f"{SMB_ENV}:32-33"),
        Fact("A step's reward is the sum of the progress, time, score, coins, powerup, completion and death "
             "components; the info dictionary also reports the unclipped and the clipped total",
             source="upstream_code", ref=f"{SMB_ENV}:564-577"),
        Fact("The death reward component is -25 while Mario is dying or dead",
             source="upstream_code", ref=f"{SMB_ENV}:415-421"),
        Fact("The completion reward component is 50, paid once when the flag is reached",
             source="upstream_code", ref=f"{SMB_ENV}:450-456"),
        Fact("The game is over when the life counter is 0xff (255), the value it holds when no lives are left",
             source="upstream_code", ref=f"{SMB_ENV}:277-281"),
        Fact("A full-game environment terminates on game over; a single-stage environment also terminates on "
             "dying, dead or flag reached", source="upstream_code", ref=f"{SMB_ENV}:579-583"),
        Fact("The info dictionary reports area, coins, enemy types, flag_get, is_dead, is_dying, is_game_over, "
             "is_stage_over, is_world_over, left_x_pos, level, life, player_state, powerup_level, score, stage, "
             "status, status_value, time, world, x_pos, x_pos_max, y_pixel, y_pos and y_viewport",
             source="upstream_code", ref=f"{SMB_ENV}:585-616"),
        Fact("A reset returns a two-item tuple and a step returns a five-item tuple (observation, reward, "
             "terminated, truncated, info)", source="upstream_code", ref=f"{TEST_SMV}:68-80"),
        Fact("The documented 1-1 opening info has 0 coins, 2 lives, world 1, score 0, stage 1, time 400 and "
             "x_pos 40", source="upstream_code", ref=f"{TEST_SMV}:81-90"),
        Fact("The registered time limit is 9999999 steps", source="upstream_code", ref=f"{REGISTRATION}:7"),
        Fact("SuperMarioBros-v0 is registered as a Super Mario Bros. environment",
             source="upstream_code", ref=f"{REGISTRATION}:92-93"),
        Fact("The registered entry point is gym_super_mario_bros:SuperMarioBrosEnv and the environment is marked "
             "nondeterministic", source="upstream_code", ref=f"{REGISTRATION}:33-42"),
        Fact("A target world is 1 to 8 (1 to 13 for Lost Levels) and a target stage is 1 to 4",
             source="upstream_code", ref=f"{DECODE_TARGET}:31-41"),
    ]
    safe_state = ("a step or reset is refused once the runtime's e-stop latch is engaged; the world state is kept "
                  "and stays readable, and the latch is cleared only by mhs.safety.reset")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:SuperMarioBros-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's starting offset and the fake then advances "
                     "deterministically; upstream registers nondeterministic=True (_registration.py:41), so the "
                     "upstream emulator's own random number generator is not claimed to follow this seed",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics are claimed (F0): the fake assigns positions and state transitions directly and does "
            "not integrate forces or contacts",
            "the pinned clone does not state a frame duration; one step advances one NES frame, and timestep_ms "
            "is 0 because the emulator's frame rate lives outside this clone",
            "the fake is a compact stand-in for the NES/nes-py emulator, not the emulator: it models the "
            "reset/step interface, the 256-action space, a monotone horizontal position and the in-game clock, "
            "not the game rules, collisions, enemies or level geometry",
            "the real observation is the emulator's NES screen, a uint8 array of shape 240 x 256 x 3 (nes-py "
            "_native.pyx:21-22,31 and nes_env.py:61-65 at commit 8d27b099f24a57afaac7339fab7ec0f1f96a59c8); the "
            "fake returns a 2 x 2 x 3 uint8 stand-in of the same type and rank",
            "no wall-clock pacing and no rendering: realtime_factor 0 and the fake has no render()",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the bridge requires get_state/set_state, which the upstream "
            "class does not expose (the emulator's own save_state/load_state is not that interface)",
        ],
    }
