# Facts and tags for gh.farama-foundation/stable-retro

Every fact cites its source at commit `e2fdb2a6d39f942d21d5b7f4b3b9929808739eab`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RetroEnv is a gymnasium.Env subclass that provides a Gym interface to classic video games | upstream_code | stable_retro/retro_env.py:16-21 |
| The environment metadata declares the render modes human and rgb_array and 60.0 video frames per second | upstream_code | stable_retro/retro_env.py:23 |
| The constructor defaults to Actions.FILTERED restricted actions, one player, Observations.IMAGE and render_mode human | upstream_code | stable_retro/retro_env.py:31-36 |
| The buttons of a game come from the emulator core metadata and their count is num_buttons | upstream_code | stable_retro/retro_env.py:128-130 |
| With the default restricted-actions mode the action space is MultiBinary(num_buttons * players) | upstream_code | stable_retro/retro_env.py:154-155 |
| The observation space is Box(low=0, high=255) with the shape of the screen or RAM buffer and dtype uint8 | upstream_code | stable_retro/retro_env.py:157-167 |
| The observation is an RGB image from the emulator screen by default; obs_type RAM returns the RAM buffer instead | upstream_code | stable_retro/retro_env.py:180-188 |
| The default observations are RGB images of the game, and RAM values can be viewed instead | vendor_doc | docs/python.md:35 |
| step advances one emulator frame and returns (observation, reward, bool(done), False, dict(info)) | upstream_code | stable_retro/retro_env.py:236-257 |
| reset accepts seed and options and seeds gymnasium's RNG with super().reset(seed=seed); it restores the initial state, presses no buttons, advances the emulator once and returns (observation, {}) | upstream_code | stable_retro/retro_env.py:259-285 |
| Reward and done come from the game data (current_reward and is_done) and info is lookup_all | upstream_code | stable_retro/retro_env.py:366-373 |
| The screen is cropped to the game's crop_info rectangle and optionally rotation-corrected | upstream_code | stable_retro/retro_env.py:333-351 |
| close deletes the emulator and closes the viewer | upstream_code | stable_retro/retro_env.py:304-309 |
| stable_retro.make() checks the ROM file path and returns RetroEnv(game, state, inttype=inttype, **kwargs) | upstream_code | stable_retro/__init__.py:56-72 |
| The README says ROMs are not included and must be obtained and imported, and names one non-commercial Airstriker Genesis ROM included for testing | vendor_doc | README.md:115-132 |
| The emulators are deterministic, so playback of a recorded button sequence gives the same output each time | vendor_doc | docs/python.md:51 |

Limits: the driver declares none. The only action bound is the environment's own action space, which the Gymnasium
bridge derives at runtime from `MultiBinary(num_buttons * players)`; the button count comes from the emulator core
metadata of the chosen game (`retro_env.py:128-130`, `:154-155`), so no static number is a bound of this device. The
fake's three buttons and 60-element screen are test data, marked `# placeholder` in `fake.py`; its action space is not
copied into a Fact, a Limit or the reference. The gate's derived `action.values` limit is sourced from the fake's own
space for the acceptance run only.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `stable-retro:RetroEnv`, level F1 (an emulated console
environment, no physical device), determinism `seeded` with `seed_control` `parameter`, timestep 1000/60 ms from the
60.0 frames per second metadata (`retro_env.py:23`) and one frame per step (`retro_env.py:237`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake models no core, game data, ROM,
rendering or savestate, that its 60-element flat screen is a stand-in for a core- and crop-dependent frame, that the
seed seeds gymnasium's RNG rather than the emulator (`retro_env.py:261-267`), and that the fake was never compared
with the upstream emulator. The upstream environment was not run here.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears it, and the fake's state stays readable. No hardware is involved.

Tags: retro, emulator, reinforcement-learning, simulation, gymnasium
