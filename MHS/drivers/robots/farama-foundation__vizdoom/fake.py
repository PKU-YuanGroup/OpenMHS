"""Fake backend of the ViZDoom Gymnasium driver: a pure Python stand-in for ``VizdoomBasic-v1``.

The upstream class named by ``native`` is
``vizdoom.gymnasium_wrapper.base_gymnasium_env:VizdoomEnv``: the base Gymnasium environment over an in-process Doom
game (the registered ``VizdoomBasic-v1`` entry point, ``VizdoomScenarioEnv``, only resolves the scenario config path
and inherits this class).  The acceptance gate cannot import it (it needs the compiled ``vizdoom`` extension and
``gymnasium``), so this module provides the environment object that the bridge drives.  Its public surface is the
part of the upstream environment the bridge uses (``reset``, ``step`` and ``close``; gate G7); the spaces are small
duck-typed stand-ins for ``gymnasium.spaces.Discrete``, ``Box`` and ``Dict``.

The model is analytic (fidelity level F0): a ticking counter, a deterministic screen pattern and an ammo counter.
It is not Doom.  It does not model the map, the monster, hits, damage, the weapon or any physics; it only mirrors
the contract around them: a ``Dict`` observation with ``screen`` and ``gamevariables``, a living reward of -1 from
the scenario config, a truncation at the config's episode timeout, and the discrete action space built from the
scenario's three binary buttons with ``max_buttons_pressed=1``.  Every numeric constant of the fake is test data
and is marked ``# placeholder``; it is not a fact about ViZDoom and is never copied into a Fact or a Limit.

The observation arrays are deliberately tiny (an 8 x 8 x 3 screen and one game variable) so receipts stay small.
The real screen is 240 x 320 x 3 and the real ``gamevariables`` array has one element (AMMO2); both sizes are named
in the driver's fidelity ``gaps`` and in RESULT.json.
"""

import random


# The fake observation is smaller than the device's: the real screen is 240 x 320 x 3 (basic.cfg:14) and the
# real gamevariables array has one element (basic.cfg:38).  These sizes are test data.
SCREEN_HEIGHT = 8                                                                                  # placeholder
SCREEN_WIDTH = 8                                                                                   # placeholder
SCREEN_CHANNELS = 3                                                                                # placeholder
ACTION_COUNT = 4                                                                                   # placeholder
BUTTON_COUNT = 3                                                                                   # placeholder
MAX_BUTTONS_PRESSED = 1                                                                            # placeholder
EPISODE_TIMEOUT = 300                                                                              # placeholder
LIVING_REWARD = -1.0                                                                               # placeholder
START_AMMO = 50.0                                                                                  # placeholder
MAX_AMMO = 200.0                                                                                   # placeholder
MIN_AMMO = 0.0                                                                                     # placeholder
START_X = 3                                                                                        # placeholder
X_LIMIT = SCREEN_WIDTH - 1                                                                         # placeholder

# Action indices follow the order of ``itertools.product((0, 1), repeat=3)`` filtered by
# ``max_buttons_pressed >= sum(action)`` (gymnasium_wrapper/base_gymnasium_env.py:449-454):
# 0 = no button, 1 = ATTACK, 2 = MOVE_RIGHT, 3 = MOVE_LEFT.
NO_BUTTON = 0                                                                                      # placeholder
ATTACK = 1                                                                                         # placeholder
MOVE_RIGHT = 2                                                                                     # placeholder
MOVE_LEFT = 3                                                                                      # placeholder


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
    """Duck-typed ``gymnasium.spaces.Box``: a bound and a fixed shape.

    ``low``/``high`` are kept as given (a scalar for a uniform bound).  The bridge reads ``shape`` and ``dtype``
    of an observation space only when it describes the observation; the fake never bounds an observation through
    this class.
    """

    def __init__(self, low, high, shape, dtype):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of key to space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _zero_screen():
    """The zero observation the wrapper returns on a terminal step (base_gymnasium_env.py:316-324)."""
    return [[[0 for _ in range(SCREEN_CHANNELS)] for _ in range(SCREEN_WIDTH)]
            for _ in range(SCREEN_HEIGHT)]


class FakeVizdoomBasicEnv:
    """``VizdoomBasic-v1`` without the engine: ``reset``, ``step`` and ``close`` as the bridge calls them."""

    # VizdoomEnv.metadata (gymnasium_wrapper/base_gymnasium_env.py:59-62); used by the real renderer, not the fake.
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 35}                          # placeholder

    def __init__(self, render_mode=None):
        self.render_mode = render_mode
        self.frame_skip = 1                                                                        # placeholder
        self.channels = SCREEN_CHANNELS
        self.num_delta_buttons = 0                                                                 # placeholder
        self.num_binary_buttons = BUTTON_COUNT
        self.max_buttons_pressed = MAX_BUTTONS_PRESSED
        self.action_space = Discrete(ACTION_COUNT)
        self.observation_space = Dict({
            "screen": Box(0, 255, (SCREEN_HEIGHT, SCREEN_WIDTH, SCREEN_CHANNELS), "uint8"),
            "gamevariables": Box(-3.4028234663852886e38, 3.4028234663852886e38, (1,), "float32"),
        })
        self._rng = random.Random()
        self._seed = None
        self._offset = 0                                                                           # placeholder
        self._tick = None
        self._x = START_X
        self._ammo = START_AMMO
        self._ended = False

    def reset(self, *, seed=None, options=None):
        """Start an episode: the wrapper seeds DoomGame from the reset seed (base_gymnasium_env.py:273-292)."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._offset = self._rng.randrange(256)                                                    # placeholder
        self._x = self._rng.randrange(SCREEN_WIDTH)                                                # placeholder
        self._ammo = float(self._rng.randrange(10, int(MAX_AMMO)))                                 # placeholder
        self._tick = 0
        self._ended = False
        return self._observations(), {}

    def step(self, action):
        """Advance one tic: one action index is mapped to a binary button vector, as the wrapper does."""
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        if self._tick is None or self._ended:
            raise AssertionError("Call `reset` before using `step` method.")

        if action == ATTACK:
            self._ammo = max(MIN_AMMO, self._ammo - 1.0)                                          # placeholder
        elif action == MOVE_RIGHT:
            self._x = min(X_LIMIT, self._x + 1)                                                   # placeholder
        elif action == MOVE_LEFT:
            self._x = max(0, self._x - 1)                                                         # placeholder

        self._tick += 1
        self._ended = self._tick >= EPISODE_TIMEOUT
        reward = LIVING_REWARD
        # The wrapper truncates on the game's episode timeout and terminates on the game's episode flag
        # (base_gymnasium_env.py:231-242).  This fake has no death model, so terminated is always false.
        return self._observations(), reward, False, self._ended, {}

    def close(self):
        self._tick = None
        self._ended = True
        self._seed = None

    def _observations(self):
        if self._ended:
            return {"screen": _zero_screen(), "gamevariables": [0.0]}
        screen = []
        for row in range(SCREEN_HEIGHT):
            pixels = []
            for col in range(SCREEN_WIDTH):
                base = (self._offset + 17 * self._tick + 11 * row + 5 * col + 3 * self._x) % 256
                pixels.append([(base + 7 * channel) % 256 for channel in range(SCREEN_CHANNELS)])
            screen.append(pixels)
        screen[0][self._x] = [255 for _ in range(SCREEN_CHANNELS)]
        return {"screen": screen, "gamevariables": [float(self._ammo)]}
