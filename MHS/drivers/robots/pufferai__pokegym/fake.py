"""Fake backend of the PokeGym driver: a pure Python stand-in for ``pokegym.environment:Environment``.

Why a fake: the upstream environment needs the PyBoy Game Boy emulator, a Pokemon Red ROM, the save states under
``pokegym/current_state/`` and the ``skimage``, ``mediapy`` and ``matplotlib`` packages (environment.py:1-26,
pyboy_binding.py:1-5), and package code never imports the clone.  The gate runs without any of them, so this module
implements the methods the bridge uses on the upstream class (``reset``, ``step`` and ``close``; gate G7) and
duck-types the two Gymnasium spaces the bridge reads (``Discrete`` and ``Box``).

What this is not: the Pokemon Red ROM.  The fake keeps the upstream action space (eight buttons, pyboy_binding.py:40)
and the shape of the bridge contract, but its 8x8x4 uint8 observation is a synthetic stand-in for the upstream
72x80x4 screen array (environment.py:137-149), its reward is a small exploration delta modelled on
environment.py:863-894, and it does not emulate the game.  The driver's fidelity ``gaps`` disclose all of this.  Every
number below is test data, marked ``# placeholder``; none of them is a Fact or a Limit.  Nothing here talks to a
device or imports the upstream package.
"""

# pyboy_binding.py:40: the eight buttons, in the order that indexes the Discrete action space (environment.py:149)
ACTIONS = ("Down", "Left", "Right", "Up", "A", "B", "Start", "Select")

# placeholder: the fake's synthetic screen is 8x8 with 4 channels; the upstream screen is 72x80x4
# (environment.py:137-149) and is named in the driver's fidelity gaps
SCREEN_ROWS, SCREEN_COLS, SCREEN_CHANNELS = 8, 8, 4

# placeholder: the fake's grid, initial position and reward term; the real game state comes from the save file
GRID_ROWS, GRID_COLS = 10, 10
START_ROW, START_COL, START_MAP = 4, 4, 0
EXPLORATION_WEIGHT = 0.02


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape, dtype="uint8"):
        count = 1
        for size in shape:
            count *= int(size)
        self.low = [low] * count
        self.high = [high] * count
        self.shape = tuple(int(size) for size in shape)
        self.dtype = dtype


class FakePokeGymEnv:
    """The bridge surface of ``pokegym.environment:Environment`` over a small synthetic game state."""

    def __init__(
        self,
        rom_path="pokemon_red.gb",
        state_path=None,
        headless=True,
        save_video=False,
        quiet=False,
        verbose=False,
        **kwargs,
    ):
        # the upstream Base.__init__ signature (environment.py:87-94) and its two spaces (environment.py:146-149)
        self.action_space = Discrete(len(ACTIONS))
        self.observation_space = Box(0, 255, (SCREEN_ROWS, SCREEN_COLS, SCREEN_CHANNELS), dtype="uint8")
        self.headless = bool(headless)
        self.save_video = bool(save_video)
        self.quiet = bool(quiet)
        self.verbose = bool(verbose)
        self.rom_path = rom_path
        self.state_path = state_path
        self.reset_count = 0
        self.time = 0
        self.max_episode_steps = 20480
        self.reward_scale = 4.0
        self.last_reward = None
        self.seen_coords = set()
        self.seen_maps = set()
        self.closed = False
        self._row = START_ROW
        self._col = START_COL
        self._map_n = START_MAP
        self._menu = 0

    # -- upstream helpers (private here: the fake only adds what Environment has) -------------------------------
    def _load_first_state(self):
        # placeholder: the upstream loads current_state/Bulbasaur.state (environment.py:104-107,620-621)
        self._row, self._col, self._map_n = START_ROW, START_COL, START_MAP
        self._menu = 0

    def _apply(self, action):
        # placeholder movement over the fake grid; the real game is driven by the ROM (pyboy_binding.py:71-88)
        name = ACTIONS[action]
        if name == "Down":
            self._row = min(GRID_ROWS - 1, self._row + 1)
        elif name == "Up":
            self._row = max(0, self._row - 1)
        elif name == "Left":
            self._col = max(0, self._col - 1)
        elif name == "Right":
            self._col = min(GRID_COLS - 1, self._col + 1)
        elif name in ("A", "B", "Start", "Select"):
            self._menu = (self._menu + 1) % 4

    def _observation(self):
        # placeholder: a deterministic 8x8x4 image that changes with the fake state; the upstream observation is the
        # downsampled screen plus a memory window (environment.py:207-222) at 72x80x4 (environment.py:137-149)
        cells = []
        for row in range(SCREEN_ROWS):
            for col in range(SCREEN_COLS):
                cells.extend((
                    (self._map_n * 37 + col * 11 + row * 7) % 256,
                    (self._col * 13 + self._row * 17 + self.time) % 256,
                    (self._menu * 61 + self._map_n * 5) % 256,
                    255 if (row, col) == (self._row % SCREEN_ROWS, self._col % SCREEN_COLS) else 0,
                ))
        return cells

    # -- the bridge surface -------------------------------------------------------------------------------------
    def reset(self, seed=None, options=None, max_episode_steps=20480, reward_scale=4.0):
        """Reset the episode; the seed is ignored, as upstream says seeding is NOT supported (environment.py:618-619)."""
        if self.reset_count == 0:
            self._load_first_state()
        self.reset_count += 1
        self.time = 0
        self.max_episode_steps = int(max_episode_steps)
        self.reward_scale = float(reward_scale)
        self.last_reward = None
        self.seen_coords = set()
        self.seen_maps = set()
        self.seen_maps.add(self._map_n)
        return self._observation(), {}

    def step(self, action, fast_video=True):
        """One fake game step: apply the button, count the tick and return a Gymnasium 5-tuple."""
        if not self.action_space.contains(action):
            raise ValueError(f"invalid action {action!r}; the action space is Discrete({self.action_space.n})")
        self._apply(action)
        self.time += 1
        self.seen_coords.add((self._row, self._col, self._map_n))
        self.seen_maps.add(self._map_n)
        cumulative = self.reward_scale * EXPLORATION_WEIGHT * len(self.seen_coords)
        # environment.py:887-894: the first step returns 0, later steps return the cumulative delta
        if self.last_reward is None:
            reward = 0.0
            self.last_reward = 0.0
        else:
            reward = cumulative - self.last_reward
            self.last_reward = cumulative
        done = self.time >= self.max_episode_steps
        return self._observation(), reward, done, done, {}

    def close(self):
        # environment.py:367-368: close stops the emulator; the fake only records that it is closed
        self.closed = True
