"""Fake backend of the nes-py driver: a pure Python stand-in for ``nes_py.nes_env:NESEnv``.

Why a fake: the upstream class needs the built C++ extension ``nes_py._native`` and a legally obtained ``.nes``
ROM, package code never imports the clone, and the gate does not build or install the upstream package.  This module
implements the three public members the bridge uses (``reset``, ``step``, ``close``) with the same signatures as
``NESEnv`` (nes_env.py:264, :297, :374), plus duck-typed ``Discrete`` and ``Box`` spaces (the bridge reads ``n``,
``start``, ``low``, ``high`` and ``shape`` by class name).

Every number below is placeholder test data, marked ``# placeholder``: the frame is a 24 x 32 x 3 downscale of the
real 240 x 256 x 3 NES frame, and the pixels are a deterministic stand-in, not an emulated picture.  The fake does
not emulate the CPU, PPU, mappers, RAM, controllers or audio, and its reward/termination behaviour is the base
``NESEnv`` hook behaviour (nes_env.py:336-351), not a game.  It was never compared with the upstream environment.
"""

# All dimensions and colours below are placeholder test data for the fake screen.
FRAME_HEIGHT = 24                        # placeholder: downscaled from the real 240-pixel height
FRAME_WIDTH = 32                         # placeholder: downscaled from the real 256-pixel width
CHANNELS = 3                             # placeholder: RGB
ACTION_COUNT = 256                       # placeholder: mirrors the Discrete(256) button bitmap (nes_env.py:69)
RENDER_FPS = 60                          # placeholder: mirrors metadata render_fps (nes_env.py:54)
MAX_PIXEL = 255                          # placeholder: uint8 upper bound
STEP_COLOUR_SALT = 7                     # placeholder: spreads the fake's changed pixel
STEP_TICK_MODULUS = 256                  # placeholder: keeps every channel in uint8


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
    """Duck-typed ``gymnasium.spaces.Box``: a flat low/high bound and a shape, like the NES RGB frame."""

    def __init__(self, low, high, shape):
        count = 1
        for item in shape:
            count *= int(item)
        self.low = [float(low)] * count
        self.high = [float(high)] * count
        self.shape = tuple(int(item) for item in shape)
        self.dtype = "uint8"


def _blank_screen():
    """A black stand-in frame; all values are placeholder test data."""
    return [[[0, 0, 0] for _ in range(FRAME_WIDTH)] for _ in range(FRAME_HEIGHT)]


class FakeNESEnv:
    """A fresh in-memory NES environment per endpoint; no ROM is opened and no device is touched."""

    metadata = {
        "render_modes": ["rgb_array", "human"],
        "render_fps": RENDER_FPS,
    }
    reward_range = (-float("inf"), float("inf"))

    def __init__(self, rom_path=None, render_mode=None, **_options):
        if render_mode is not None and render_mode not in self.metadata["render_modes"]:
            raise NotImplementedError("valid render modes are: 'rgb_array', 'human'")
        self._rom_path = rom_path
        self.render_mode = render_mode
        self.viewer = None
        self.done = True
        self.screen = _blank_screen()
        self.action_space = Discrete(ACTION_COUNT)
        self.observation_space = Box(0, MAX_PIXEL, (FRAME_HEIGHT, FRAME_WIDTH, CHANNELS))
        self._frame = 0
        self._seed = None
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Reset the fake emulator and return the start frame, like ``NESEnv.reset`` (nes_env.py:264-291)."""
        if self._closed:
            raise ValueError("env has already been closed.")
        self._seed = seed
        self._frame = 0
        self.done = False
        self.screen = _blank_screen()
        return self.screen, {}

    def step(self, action):
        """Advance one frame and return the base-class result (nes_env.py:297-334, :336-351)."""
        if self.done:
            raise ValueError("cannot step in a done environment! call `reset`")
        if not self.action_space.contains(action):
            raise ValueError(f"{action!r} is not a valid NES button bitmap")
        self._frame += 1
        row = (self._frame - 1) % FRAME_HEIGHT
        column = ((self._frame - 1) * STEP_COLOUR_SALT + action) % FRAME_WIDTH
        self.screen[row][column] = [
            action,
            self._frame % STEP_TICK_MODULUS,
            (action * 3) % STEP_TICK_MODULUS,
        ]                                                   # placeholder pixel
        return self.screen, 0.0, False, False, {}

    def close(self):
        """Close the fake emulator; idempotent so a repeated server close is harmless."""
        if self._closed:
            return
        self._closed = True
        self.done = True
