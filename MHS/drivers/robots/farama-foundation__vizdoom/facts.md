# Facts and tags for gh.farama-foundation/vizdoom

Every fact cites its source at commit `26a9958970a3b1069325cf9e00c4119a69664128`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

`VizdoomBasic-v1` is the Gymnasium environment for the basic scenario (`scenarios/basic.cfg`). A reset seeds
DoomGame, starts an episode and returns the first observation; a step advances one frame (one tic by default) and
returns the reward, the terminated flag from the game and the truncated flag from the game's timeout. The
observation is a dictionary: the screen image plus the game variables (AMMO2), and the other buffers only when
the config enables them.

| fact | source | ref |
|---|---|---|
| VizdoomScenarioEnv is defined as a subclass of VizdoomEnv | upstream_code | gymnasium_wrapper/gymnasium_env_defns.py:32 |
| VizdoomBasic-v1 is registered with scenario_config_file basic.cfg and max_buttons_pressed 1 | upstream_code | gymnasium_wrapper/__init__.py:30-33 |
| The basic scenario declares three binary buttons: MOVE_LEFT, MOVE_RIGHT and ATTACK | upstream_code | scenarios/basic.cfg:30-35 |
| With max_buttons_pressed above zero the binary action space is Discrete(len(button_map)), where button_map holds the button combinations whose pressed count is at most max_buttons_pressed | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:448-454 |
| The wrapper forces the screen format to RGB24 when the config selects neither RGB24 nor GRAY8, and records the channel count: 3 unless the format is GRAY8 | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:173-193 |
| The screen observation space is a uint8 Box of [screen height, screen width, channels] | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:493-503 |
| The basic scenario renders at RES_320X240 | upstream_code | scenarios/basic.cfg:14 |
| The observation dictionary always carries the screen and carries depth, labels, automap, audio, notifications and gamevariables only when they are enabled | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:294-315 |
| The game variables are a float32 array with one element per available game variable | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:553-560 |
| The only game variable enabled by the basic scenario is AMMO2 | upstream_code | scenarios/basic.cfg:38 |
| step returns terminated from the game's episode-finished flag and truncated from its episode-timeout flag when treat_episode_timeout_as_truncation is true | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:231-242 |
| On a terminal step there is no game state and the wrapper returns a zero observation instead | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:316-324 |
| The basic scenario sets the living reward to -1 | upstream_code | scenarios/basic.cfg:11 |
| The basic scenario finishes an episode after an episode_timeout of 300 tics | upstream_code | scenarios/basic.cfg:26-27 |
| The basic scenario starts an episode after episode_start_time 14 tics | upstream_code | scenarios/basic.cfg:23-24 |
| A reset seeds DoomGame with an unsigned 32-bit integer drawn from Gymnasium's generator | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:280-284 |
| The default ViZDoom tic rate is 35 tics per second and the default frame time is 1/35 s | upstream_code | include/ViZDoomConsts.h:34-37 |
| The default frame_skip is 1, so one step advances one frame | upstream_code | gymnasium_wrapper/base_gymnasium_env.py:67 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the
environment (`Discrete(4)` for `VizdoomBasic-v1`: `action.index` 0 to 3, with no source and ref
`action_space of the fake backend .fake:FakeVizdoomBasicEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `vizdoom:VizdoomBasic-v1`, level F0 (analytic: a
ticking counter and an ammo counter, no Doom dynamics), determinism `seeded` with `seed_control` `parameter`,
timestep 28.57 ms (`include/ViZDoomConsts.h:34-37`: 35 tics per second, one tic per default step), `realtime_factor`
0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake
returns an 8 x 8 x 3 screen where the real one is 240 x 320 x 3, and that it was not compared with upstream.

Safety: simulated R0 game. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last observation stays readable.

Tags: vizdoom, doom, gymnasium, reinforcement-learning, visual-rl, simulation
