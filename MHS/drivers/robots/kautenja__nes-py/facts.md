# Facts and tags for gh.kautenja/nes-py

Every fact cites its source at commit `8d27b099f24a57afaac7339fab7ec0f1f96a59c8`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| NESEnv is a Gymnasium environment (class NESEnv(gym.Env)) | upstream_code | nes_py/nes_env.py:48 |
| The action space is Discrete(256), a bitmap of button press values for the 8 NES buttons | upstream_code | nes_py/nes_env.py:68-69 |
| The observation space is Box(low=0, high=255, shape=SCREEN_SHAPE_24_BIT, dtype=uint8) | upstream_code | nes_py/nes_env.py:61-66 |
| The default observation and the rgb_array render are the zero-copy (240, 256, 3) uint8 RGB screen view | vendor_doc | docs/ml-observation-fast-paths.md:5-6 |
| The metadata declares the render modes rgb_array and human and render_fps 60 | upstream_code | nes_py/nes_env.py:52-55 |
| reset accepts an optional seed and options, calls super().reset(seed=seed) and the native reset, and returns the screen and info | upstream_code | nes_py/nes_env.py:264-291 |
| step refuses to run in a done environment, advances the emulator by one frame, and returns the screen, reward, terminated, truncated and info | upstream_code | nes_py/nes_env.py:313-334 |
| The base hooks return reward 0, no termination and no truncation unless a subclass overrides them | upstream_code | nes_py/nes_env.py:336-351 |
| The reward range is unbounded from -inf to inf | upstream_code | nes_py/nes_env.py:57-58 |
| seed() is deprecated in favour of reset(seed=...) | upstream_code | nes_py/nes_env.py:243-260 |
| close closes the native emulator and any viewer | upstream_code | nes_py/nes_env.py:374-385 |
| render returns the screen in rgb_array mode | upstream_code | nes_py/nes_env.py:415-416 |
| dump_state and load_state carry an opaque native snapshot and restore it | upstream_code | nes_py/nes_env.py:214-225 |
| get_action_meanings returns ['NOOP'] for the base class | upstream_code | nes_py/nes_env.py:452-454 |

Limits: the driver declares none. The only bounds are derived by the bridge from the environment itself:
`cap.world.step.v1` takes `ticks` from 1 to `max_ticks` (10000 by default) and the action field `action.index` from
0 to 255 from the fake's `Discrete(256)` action space; the reset and seed inputs are non-negative integers. The
device is simulated (R0), so no limit is `operator_required` and no site-limits overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `nes-py:NESEnv`, level F0 (the fake is a kinematic
stand-in with no emulated CPU, PPU, mapper, memory or audio dynamics), determinism `seeded` with `seed_control`
`parameter`, timestep 16.67 ms (one frame at the declared `render_fps` 60, `nes_py/nes_env.py:54`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled,
that the fake returns a 24 x 32 x 3 downscale of the real 240 x 256 x 3 frame, and that no run was compared with the
upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the frame
state stays readable.

Tags: nes, emulator, reinforcement-learning, simulation, gymnasium
