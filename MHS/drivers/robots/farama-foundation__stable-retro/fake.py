"""Fake backend of the Stable Retro driver: a pure Python stand-in for ``stable_retro.retro_env:RetroEnv``.

Why a fake: the acceptance gate runs without the stable-retro extension modules, the emulator cores and the game
ROMs (``README.md:115-132``), and package code never imports the clone.  This module mirrors the public members of
``RetroEnv`` the bridge uses (``reset``, ``step``, ``close``; gate G7) and provides duck-typed
``gymnasium.spaces.MultiBinary`` and ``Box`` objects for the bridge, which reads ``n``, ``low``, ``high``, ``shape``
and ``dtype``.

What this is not: the upstream emulator.  The fake does not load a core, a ROM, a savestate or game data, and the
screen is a flat 60-element uint8 stand-in for an RGB frame.  Its starting position, button names, score, lives and
termination tick are test data (marked ``# placeholder``), not facts about any game; the driver's fidelity ``gaps``
say so.  Nothing here talks to a device.
"""

# The fake's button count, observation size and episode rules are test data, never bounds or facts.
BUTTONS = ["LEFT", "RIGHT", "FIRE"]                     # placeholder: a small action space for the bridge
SCREEN_PIXELS = 60                                      # placeholder: 4 x 5 x 3 RGB elements
SCREEN_SHAPE = (4, 5, 3)                                # placeholder: a small stand-in for an emulator frame
START_X = 2                                             # placeholder
SCREEN_WIDTH = 4                                        # placeholder
LIVES = 3                                               # placeholder
LIVES_LOST_EVERY = 12                                   # placeholder: one life lost every 12 frames
TERMINATED_AFTER = LIVES * LIVES_LOST_EVERY             # placeholder


class MultiBinary:
    """Duck-typed ``gymnasium.spaces.MultiBinary``: ``n`` binary values, each 0 or 1."""

    def __init__(self, n):
        self.n = int(n)
        self.shape = (self.n,)
        self.dtype = "int8"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.n:
            return False
        return all(isinstance(item, int) and not isinstance(item, bool) and item in (0, 1) for item in value)


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None, dtype=None):
        self.low = [float(item) for item in low]
        self.high = [float(item) for item in high]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype or "float32"


class FakeRetroEnv:
    """A deterministic stand-in with ``RetroEnv``'s public methods: ``reset(seed, options)``, ``step(a)`` and ``close``."""

    metadata = {"render_modes": ["human", "rgb_array"], "video.frames_per_second": 60.0}

    def __init__(self, game="Airstriker-Genesis-v0", state=None, render_mode="rgb_array", **_options):
        self.gamename = game
        self.statename = state
        self.players = 1
        self.buttons = list(BUTTONS)
        self.num_buttons = len(self.buttons)
        self.action_space = MultiBinary(self.num_buttons * self.players)
        self.observation_space = Box(
            [0] * SCREEN_PIXELS, [255] * SCREEN_PIXELS, shape=SCREEN_SHAPE, dtype="uint8"
        )
        self.render_mode = render_mode
        self.img = None
        self.ram = None
        self.initial_state = None
        self.viewer = None
        self.spec = None
        self.use_restricted_actions = "filtered"
        self._x = START_X
        self._tick = 0
        self._lives = LIVES
        self._score = 0

    def _frame(self):
        """A deterministic screen stand-in derived from the current fake state (test data)."""
        base = (self._x * 37 + self._tick * 11 + self._score * 7 + self._lives * 3) % 256   # placeholder
        return [(base + 5 * index) % 256 for index in range(SCREEN_PIXELS)]                 # placeholder

    def reset(self, seed=None, options=None):
        self._x = START_X
        self._tick = 0
        self._lives = LIVES
        self._score = 0
        self.img = self._frame()
        self.ram = None
        return list(self.img), {}

    def step(self, a):
        if self.img is None:
            raise RuntimeError("Please call env.reset() before env.step()")
        values = list(a)
        if len(values) != self.num_buttons:
            raise ValueError(f"expected {self.num_buttons} button values, got {len(values)}")
        if not self.action_space.contains(values):
            raise ValueError(f"{values!r} is not in the action space")
        left, right, fire = values
        step = right - left
        self._x = max(0, min(SCREEN_WIDTH, self._x + step))
        if fire:
            self._score += 1
        self._tick += 1
        if self._tick % LIVES_LOST_EVERY == 0 and self._lives > 0:
            self._lives -= 1
        self.img = self._frame()
        done = self._lives <= 0
        reward = 1.0 if fire else 0.0
        return list(self.img), reward, done, False, {
            "score": self._score,
            "lives": self._lives,
            "x": self._x,
            "tick": self._tick,
        }

    def close(self):
        self.img = None
        self.ram = None
        self.viewer = None
