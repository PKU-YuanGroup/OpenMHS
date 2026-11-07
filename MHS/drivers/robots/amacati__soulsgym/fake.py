"""Fake backend of the SoulsGym Iudex driver: a pure Python analytic stand-in for the Iudex environment.

Why a fake: the upstream package reads and writes the memory of a running Dark Souls III game on Windows (or Linux
under Proton/Wine) and needs ``soulsgym`` imported for the gymnasium registration, so the acceptance gate cannot open
the real environment.  This module mimics the public surface of ``soulsgym.envs.darksouls3.iudex:IudexEnv`` that the
Gymnasium bridge uses (``reset``, ``step``, ``close``; gate G7) and the action/observation spaces the bridge reads.

Every numeric value below is a stand-in for a game or episode value and is marked ``# placeholder``.  None of them is
a Fact, a Limit or a reference; the facts of this package cite the clone, not this file.  The rules that matter (the
shape of the observation, the action table, the step contract and the seed behaviour) are described in ``facts.md``
with their upstream lines.

What this is not: the game.  It has no physics, collision, animation, rendering or game memory; it moves a pose and
subtracts HP from an analytic action table.  The driver's fidelity ``gaps`` disclose that.
"""

from __future__ import annotations

import math
import random

# placeholder: the length of soulsgym/core/data/darksouls3/actions.yaml (0..19)
ACTION_COUNT = 20
# placeholder: player and boss HP/SP values the game reads from memory
PLAYER_MAX_HP = 1000.0
PLAYER_MAX_SP = 100.0
BOSS_MAX_HP = 1037.0
# placeholder: a stand-in arena and start layout inside the clone's ARENA_LIM_* ranges
ARENA_LOW = [110.0, 540.0, -73.0, -3.1416]
ARENA_HIGH = [190.0, 640.0, -55.0, 3.1416]
PLAYER_START = [120.0, 545.0, -73.0, 0.0]
BOSS_START = [150.0, 596.0, -73.0, 0.0]
CAMERA_START = [0.378, 0.926, 0.0, 0.0, 0.0, -1.0]
# placeholder: the registered max_episode_steps and the fake's damage/counter values
EPISODE_LIMIT = 3000
LIGHT_ATTACK_DAMAGE = 60.0
HEAVY_ATTACK_DAMAGE = 110.0
COUNTER_DAMAGE = 25.0
COUNTER_EVERY = 5
STEP_MOVE = 0.05
ROLL_MOVE = 0.10
# placeholder: the observation's animation members are a two-value stand-in for the game's animation tables
PLAYER_ANIMATIONS = 2
BOSS_ANIMATIONS = 2


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of member names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


def _walk_vector(action):
    """A unit direction for the eight walking actions; placeholder test data."""
    directions = ((1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (-1.0, 1.0),
                  (-1.0, 0.0), (-1.0, -1.0), (0.0, -1.0), (1.0, -1.0))
    return directions[action % 8]


class FakeIudexEnv:
    """The Iudex environment without the game: ``reset(seed, options)`` and ``step(action)`` return what it returns."""

    def __init__(self, game_speed=1.0, phase=1, random_player_pose=False, skip_steps=False):
        self.observation_space = Dict({
            "phase": Discrete(2, start=1),
            "player_hp": Box([0.0], [PLAYER_MAX_HP]),
            "player_max_hp": Discrete(1, start=int(PLAYER_MAX_HP)),
            "player_sp": Box([0.0], [PLAYER_MAX_SP]),
            "player_max_sp": Discrete(1, start=int(PLAYER_MAX_SP)),
            "boss_hp": Box([0.0], [BOSS_MAX_HP]),
            "boss_max_hp": Discrete(1, start=int(BOSS_MAX_HP)),
            "player_pose": Box(ARENA_LOW, ARENA_HIGH),
            "boss_pose": Box(ARENA_LOW, ARENA_HIGH),
            "camera_pose": Box(ARENA_LOW[:3] + [-1.0, -1.0, -1.0], ARENA_HIGH[:3] + [1.0, 1.0, 1.0]),
            "player_animation": Discrete(PLAYER_ANIMATIONS, start=-1),
            "player_animation_duration": Box([0.0], [10.0]),
            "boss_animation": Discrete(BOSS_ANIMATIONS, start=-1),
            "boss_animation_duration": Box([0.0], [10.0]),
            "lock_on": Discrete(2),
        })
        self.action_space = Discrete(ACTION_COUNT)
        self._game_speed = game_speed  # placeholder: kept so the constructor matches IudexEnv
        self._phase = int(phase)       # placeholder: phase 1 unless the caller asks for 2
        self._random_player_pose = bool(random_player_pose)
        self._skip_steps = bool(skip_steps)
        self._closed = False
        self._reset_state(None)

    def reset(self, seed=None, options=None):
        """Reset the episode; ``seed`` gives the fake its reproducible layout, ``options`` is ignored."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is None:
            seed = self._seed
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        self._reset_state(seed)
        return self._observation(), self._info()

    def step(self, action):
        """Apply one action and return ``(observation, reward, terminated, truncated, info)``."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if isinstance(action, bool) or not isinstance(action, int) or not 0 <= action < ACTION_COUNT:
            raise ValueError(f"invalid action {action!r}")
        if self._terminated:
            raise RuntimeError("the episode terminated; reset the environment first")
        previous_boss_hp = self._boss_hp
        previous_player_hp = self._player_hp
        previous_pose = list(self._player_pose)
        self._tick += 1
        self._player_animation = 0
        self._boss_animation = 0
        self._player_animation_duration = 0.1  # placeholder: one step's animation time
        self._boss_animation_duration = 0.1    # placeholder: one step's animation time
        if 0 <= action < 8:
            direction = _walk_vector(action)
            self._player_pose[0] += STEP_MOVE * direction[0]
            self._player_pose[1] += STEP_MOVE * direction[1]
        elif 8 <= action < 16:
            direction = _walk_vector(action - 8)
            self._player_pose[0] += ROLL_MOVE * direction[0]
            self._player_pose[1] += ROLL_MOVE * direction[1]
            self._player_animation = 1
        elif action in (16, 17):
            self._player_animation = 1
            damage = LIGHT_ATTACK_DAMAGE if action == 16 else HEAVY_ATTACK_DAMAGE
            self._boss_hp = max(0.0, self._boss_hp - damage)
            if self._tick % COUNTER_EVERY == 0:
                self._boss_animation = 1
                self._player_hp = max(0.0, self._player_hp - COUNTER_DAMAGE)
        elif action == 18:
            self._player_animation = 1
        # action 19 is the no-op
        self._terminated = self._player_hp == 0.0 or self._boss_hp == 0.0
        truncated = (not self._terminated) and self._tick >= EPISODE_LIMIT
        reward = self._reward(previous_boss_hp, previous_player_hp, previous_pose)
        return self._observation(), reward, bool(self._terminated), bool(truncated), self._info()

    def close(self):
        """Mark the fake closed; the real close kills the player and reloads the game."""
        self._closed = True

    # -- private state helpers -------------------------------------------------
    def _reset_state(self, seed):
        if seed is None:
            seed = 0
        self._seed = int(seed)
        self._rng = random.Random(self._seed)
        jitter = self._rng.uniform(-0.5, 0.5)  # placeholder: a small reproducible pose offset
        self._player_hp = PLAYER_MAX_HP
        self._player_max_hp = PLAYER_MAX_HP
        self._player_sp = PLAYER_MAX_SP
        self._player_max_sp = PLAYER_MAX_SP
        self._boss_hp = BOSS_MAX_HP
        self._boss_max_hp = BOSS_MAX_HP
        self._player_pose = list(PLAYER_START)
        self._player_pose[0] += jitter
        self._boss_pose = list(BOSS_START)
        self._boss_pose[0] -= jitter
        self._camera_pose = list(CAMERA_START)
        self._phase = 1
        self._player_animation = -1
        self._boss_animation = -1
        self._player_animation_duration = 0.0
        self._boss_animation_duration = 0.0
        self._lock_on = 0
        self._tick = 0
        self._terminated = False
        self._closed = False

    def _observation(self):
        return {
            "phase": self._phase,
            "player_hp": [self._player_hp],
            "player_max_hp": int(self._player_max_hp),
            "player_sp": [self._player_sp],
            "player_max_sp": int(self._player_max_sp),
            "boss_hp": [self._boss_hp],
            "boss_max_hp": int(self._boss_max_hp),
            "player_pose": list(self._player_pose),
            "boss_pose": list(self._boss_pose),
            "camera_pose": list(self._camera_pose),
            "player_animation": self._player_animation,
            "player_animation_duration": [self._player_animation_duration],
            "boss_animation": self._boss_animation,
            "boss_animation_duration": [self._boss_animation_duration],
            "lock_on": self._lock_on,
        }

    def _info(self):
        return {"action_mask": [True] * ACTION_COUNT}

    def _reward(self, previous_boss_hp, previous_player_hp, previous_pose):
        boss_reward = (previous_boss_hp - self._boss_hp) / self._boss_max_hp
        player_reward = (self._player_hp - previous_player_hp) / self._player_max_hp
        if self._boss_hp == 0.0 or self._player_hp == 0.0:
            base_reward = 0.1 if self._boss_hp == 0.0 else -0.1
        else:
            d_center_now = math.hypot(self._player_pose[0] - 139.0, self._player_pose[1] - 596.0)
            d_center_prev = math.hypot(previous_pose[0] - 139.0, previous_pose[1] - 596.0)
            base_reward = 0.01 * (d_center_prev - d_center_now) * (1.0 if d_center_now > 4.0 else 0.0)
        return float(boss_reward + player_reward + base_reward)
