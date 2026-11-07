"""Fake backend of the gym-super-mario-bros driver: a pure Python stand-in for ``SuperMarioBros-v0``.

Why a fake: the acceptance gate has no nes-py (the native emulator is built with CMake and the package needs
CPython 3.13 or newer; pyproject.toml:10 and :38-41), and package code never imports the clone.  This module
re-implements the Gymnasium contract of ``gym_super_mario_bros.smb_env:SuperMarioBrosEnv``: the 256-action joypad
space (README.md:50-53), the reset and step return shapes (gym_super_mario_bros/tests/test_smv_env.py:68-80), the
reward range and the reward components (smb_env.py:32-33 and :564-577), the full-game termination on game over
(smb_env.py:277-281 and :579-583) and the info dictionary keys (smb_env.py:585-616).

What this is not: the NES emulator or its ROM.  The state is a small deterministic model -- x advances on any
non-NOOP action, the in-game clock ticks every few frames, and three lives end the episode.  Every number below is
test data, not a documented value of the device, and is marked ``# placeholder``.  The real observation is the
emulator's NES screen, a 240 x 256 x 3 uint8 array (nes-py ``nes_py/_native.pyx:21-22,31`` and ``nes_env.py:61-65``
at commit 8d27b099f24a57afaac7339fab7ec0f1f96a59c8); the fake returns a 2 x 2 x 3 uint8 stand-in of the same type
and rank so receipts stay small (playbook section 8).

The public members are the ones the upstream class exposes to Gymnasium -- ``reset``, ``step`` and ``close`` (gate
G7); the state helpers are private.
"""

# placeholder: the documented 1-1 opening values (test_smv_env.py:81-90) are used as the default start state
_START_X = 40                       # placeholder
_START_Y_PIXEL = 176                # placeholder
_START_TIME = 400                   # placeholder
_START_LIVES = 2                    # placeholder
_GAME_OVER_LIFE = 0xFF              # placeholder; the upstream game-over sentinel (smb_env.py:277-281)
_TIME_EVERY = 4                     # placeholder: frames per in-game clock tick
_REWARD_MIN, _REWARD_MAX = -15, 15  # smb_env.py:33
_SCREEN_SHAPE = (2, 2, 3)           # placeholder; the real NES screen is 240 x 256 x 3
_SEED_SPREAD = 7                    # placeholder: number of distinct seeded starting positions
_DEATH_PENALTY = -25.0              # smb_env.py:415-421
_PROGRESS_CAP = 5                   # smb_env.py:399-400


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
    """Duck-typed ``gymnasium.spaces.Box`` of uint8 pixels (the bridge reads ``low``, ``high`` and ``shape``)."""

    def __init__(self, low, high, shape, dtype="uint8"):
        self.low = int(low)
        self.high = int(high)
        self.shape = tuple(int(item) for item in shape)
        self.dtype = dtype


class FakeSuperMarioBrosEnv:
    """``SuperMarioBros-v0`` without nes-py: ``reset(seed, options)`` and ``step(action)`` return the same shapes."""

    #: The reward contract of the upstream class (smb_env.py:32-33); the fake clips its step reward to it.
    reward_range = (_REWARD_MIN, _REWARD_MAX)

    def __init__(self, lost_levels=False, target=None, render_mode=None):
        if not isinstance(lost_levels, bool):
            raise TypeError("lost_levels must be of type: bool")
        if render_mode is not None:
            raise ValueError("the fake cannot render; use render_mode=None")
        self._lost_levels = lost_levels
        self._target = target
        self.action_space = Discrete(256)                       # README.md:50-53
        self.observation_space = Box(0, 255, _SCREEN_SHAPE)      # placeholder pixel range
        self._seed = 0                                          # placeholder default seed
        self._tick = 0
        self._started = False
        self._closed = False
        self._reset_state()

    def _reset_state(self):
        self._x = _START_X + self._seed % _SEED_SPREAD
        self._x_max = self._x
        self._y_pixel = _START_Y_PIXEL
        self._time = _START_TIME
        self._time_last = _START_TIME
        self._lives = _START_LIVES
        self._coins = 0
        self._score = 0
        self._score_last = 0
        self._coins_last = 0
        self._status_value = 0
        self._status_last = 0
        self._terminated = False
        self._components = {
            "progress": 0.0, "time": 0.0, "score": 0.0, "coins": 0.0,
            "powerup": 0.0, "completion": 0.0, "death": 0.0,
        }
        self._reward_unclipped = 0.0
        self._reward_clipped = 0.0

    def reset(self, *, seed=None, options=None):
        """Reset the stand-in world and return ``(observation, info)`` (gymnasium reset contract)."""
        if self._closed:
            raise ValueError("env has already been closed.")
        if seed is not None:
            self._seed = int(seed)
        self._tick = 0
        self._started = True
        self._reset_state()
        return self._observation(), self._info()

    def step(self, action):
        """Advance one frame and return ``(observation, reward, terminated, truncated, info)``."""
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        if not self._started:
            raise ValueError("cannot step in a done environment! call `reset`")
        if self._terminated:
            raise ValueError("cannot step in a done environment! call `reset`")
        self._tick += 1
        if action != 0:                                         # placeholder: any non-NOOP frame moves right
            self._x += 1
        if self._tick % _TIME_EVERY == 0:                       # placeholder: frame count per clock tick
            self._time -= 1
        if self._time <= 0:
            self._lives -= 1
            if self._lives < 0:
                self._lives = _GAME_OVER_LIFE
                self._terminated = True
            else:
                self._time = _START_TIME
        components = {
            "progress": self._progress_reward(action),
            "time": self._time_penalty(),
            "score": self._difference_reward(self._score, "_score_last", 100),
            "coins": self._coin_reward(),
            "powerup": self._powerup_reward(),
            "completion": 0.0,
            "death": _DEATH_PENALTY if self._terminated else 0.0,
        }
        self._store_reward_components(components)
        return (self._observation(), self._reward_clipped, self._terminated, False, self._info())

    def close(self):
        """Release the stand-in world (the upstream environment closes its emulator)."""
        self._closed = True
        self._started = False

    # -- private state and reward helpers -------------------------------------------------
    def _progress_reward(self, action):
        """``_progress_reward`` of the upstream class, capped the same way (smb_env.py:392-401)."""
        if action == 0 or self._x <= self._x_max:
            return 0.0
        delta = self._x - self._x_max
        self._x_max = self._x
        return float(delta) if delta <= _PROGRESS_CAP else 0.0

    def _time_penalty(self):
        """``_time_penalty`` of the upstream class (smb_env.py:403-413)."""
        delta = self._time - self._time_last
        self._time_last = self._time
        return 0.0 if delta > 0 else float(delta)

    def _difference_reward(self, value, last_name, divisor):
        """Score-like reward: a positive difference divided by ``divisor`` (smb_env.py:423-430)."""
        last = getattr(self, last_name)
        setattr(self, last_name, value)
        delta = value - last
        return float(delta) / divisor if delta > 0 else 0.0

    def _coin_reward(self):
        """``_coin_reward`` of the upstream class (smb_env.py:432-441)."""
        delta = self._coins - self._coins_last
        if delta < -50:
            delta += 100
        self._coins_last = self._coins
        return float(delta) * 5 if delta > 0 else 0.0

    def _powerup_reward(self):
        """``_powerup_reward`` of the upstream class (smb_env.py:443-448)."""
        level = min(self._status_value, 2)
        delta = level - self._status_last
        self._status_last = level
        return float(delta) * 5

    def _store_reward_components(self, components):
        """Store the step's components and both totals, as the upstream class does (smb_env.py:462-471)."""
        self._components = {key: float(value) for key, value in components.items()}
        self._reward_unclipped = float(sum(self._components.values()))
        self._reward_clipped = max(_REWARD_MIN, min(_REWARD_MAX, self._reward_unclipped))

    def _observation(self):
        """A small uint8 screen stand-in: the same value in every pixel of a 2 x 2 x 3 image."""
        pixel = (self._x + self._time + self._tick) % 256       # placeholder
        return [[[pixel for _ in range(_SCREEN_SHAPE[2])] for _ in range(_SCREEN_SHAPE[1])]
                for _ in range(_SCREEN_SHAPE[0])]

    def _info(self):
        """The info keys of the upstream class (smb_env.py:585-616), filled from the stand-in state."""
        over = self._lives == _GAME_OVER_LIFE
        return {
            "area": 1,                                          # placeholder
            "coins": self._coins,
            "enemy_types": (0, 0, 0, 0, 0),                     # placeholder
            "flag_get": False,
            "is_dead": over,
            "is_dying": False,
            "is_game_over": over,
            "is_stage_over": False,
            "is_world_over": False,
            "left_x_pos": self._x % 256,                       # placeholder
            "level": 0,                                         # placeholder
            "life": self._lives,
            "player_state": 6 if over else 8,                  # placeholder
            "powerup_level": 0,                                 # placeholder
            "score": self._score,
            "stage": 1,                                         # placeholder
            "status": "small",                                 # placeholder
            "status_value": self._status_value,
            "time": self._time,
            "world": 1,                                         # placeholder
            "x_pos": self._x,
            "x_pos_max": self._x_max,
            "y_pixel": self._y_pixel,
            "y_pos": 255 - self._y_pixel,                      # placeholder screen coordinate
            "y_viewport": 1,                                   # placeholder
            "clear": False,
            "death": over,
            "game": "smb1",                                    # placeholder
            "game_family": "smb1",                             # placeholder
            "lives": self._lives,
            "progress": self._x,
            "progress_max": self._x_max,
            "rom_mode": "vanilla",                             # placeholder
            "single_stage": False,
            "task_id": "SuperMarioBros-v0",
            "target_stage": None,
            "target_world": None,
            "timeout": False,
            "world_label": "1",                                # placeholder
            "reward_components": dict(self._components),
            "reward_total_unclipped": self._reward_unclipped,
            "reward_total_clipped": self._reward_clipped,
        }
