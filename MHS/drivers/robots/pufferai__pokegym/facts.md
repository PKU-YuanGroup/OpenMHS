# Facts and tags for gh.pufferai/pokegym

Every fact cites its source at commit `9050f7ae43e21b9337ac5ae407d37e6eb34ca03f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The entry class is Environment(Base), the Gymnasium environment class defined in environment.py | upstream_code | pokegym/environment.py:374 |
| The action space is Discrete(len(ACTIONS)) | upstream_code | pokegym/environment.py:149 |
| ACTIONS is the eight-button tuple (Down, Left, Right, Up, A, B, Start, Select), so the discrete action index runs from 0 to 7 | upstream_code | pokegym/pyboy_binding.py:40 |
| The observation space is Box(low=0, high=255, dtype=np.uint8, shape=obs_size), where obs_size is the screen rows//2 and columns//2 plus four channels when use_screen_memory is true | upstream_code | pokegym/environment.py:137-149 |
| The observation concatenates the downsampled screen with a fixed window of the per-map memory channel | upstream_code | pokegym/environment.py:215-222 |
| reset has the signature reset(self, seed=None, options=None, max_episode_steps=20480, reward_scale=4.0) and its docstring says seeding is NOT supported | upstream_code | pokegym/environment.py:618-619 |
| The first reset loads the first saved state; later resets do not reload it (the load happens only when reset_count == 0) | upstream_code | pokegym/environment.py:620-621 |
| The default save state is current_state/Bulbasaur.state when state_path is None | upstream_code | pokegym/environment.py:104-107 |
| step has the signature step(self, action, fast_video=True) and sends ACTIONS[action] to the emulator | upstream_code | pokegym/environment.py:698-699 |
| One step runs the emulator for frame_skip=24 frames and releases the button after 8 frames | upstream_code | pokegym/pyboy_binding.py:71-88 |
| self.time is incremented by one at every step | upstream_code | pokegym/environment.py:700 |
| done is True when self.time >= self.max_episode_steps | upstream_code | pokegym/environment.py:896 |
| step returns (observation, reward, done, done, info): the same done bool fills terminated and truncated | upstream_code | pokegym/environment.py:1010 |
| The reward is the difference between the current cumulative reward_scale-scaled reward and the previous one; the first step returns 0 | upstream_code | pokegym/environment.py:863-894 |
| make_env hardcodes the ROM path to pokemon_red.gb in the working directory | upstream_code | pokegym/pyboy_binding.py:42-43 |
| The package requires the pyboy, gymnasium and numpy packages | upstream_code | setup.py:11-15 |
| The state files are found under pokegym/current_state/ | upstream_code | pokegym/environment.py:32 |
| The README instructs the user to copy pokemon_red.gb into the training directory | vendor_doc | README.md:36 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the fake's
`Discrete(8)` (`action.index` from 0 to 7, with no source and the ref
`action_space of the fake backend .fake:FakePokeGymEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The device
is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pyboy:pokemon-red`, level F0 (the game state transitions,
no physics, contacts, actuator or sensor dynamics), determinism `none` because the upstream reset ignores the seed and
reloads the first save state only once, timestep 0 (one step runs 24 emulator frames but the clone states no frame
duration), `realtime_factor` 0, clock `lockstep`, reset `partial`, no snapshot and restore. The gaps say what is not
modelled, that the fake returns an 8x8x4 stand-in for the 72x80x4 observation and that the upstream was never run here.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: pokemon-red, game-boy, pyboy, reinforcement-learning, simulation, gymnasium
