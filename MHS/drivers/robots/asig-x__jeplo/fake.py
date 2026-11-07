"""Fake backend for the JEPLO Unitree Go2 Gymnasium driver.

The upstream environment is an Isaac Lab ``DirectRLEnv`` that needs Isaac Sim, Isaac Lab, Python 3.11 and an NVIDIA
GPU (README.md:28-32 and :75).  It also expects ``AppLauncher`` to be running and a prebuilt ``Go2LocoEnvCfg`` passed
to ``gym.make`` (training/scripts/play.py:63-64 and :110), none of which the MHS Gymnasium bridge supplies.  This
module therefore provides a small, pure Python, single-environment stand-in for the parts the bridge uses:
``action_space``, ``observation_space``, ``reset(seed, options)``, ``step(action)`` and ``close()``.

The fake keeps the upstream interface dimensions, not the upstream physics.  The action width is 12
(go2_loco_env_cfg.py:178); the policy observation width is the sum of the four configured groups
(go2_loco_env_cfg.py:248-262); the depth array is ``num_depth_stack`` frames of 25 x 60 rays
(go2_loco_env_cfg.py:249; sensor/lidar_pattern.py:86-88); one environment step is one control step of 20 ms
(go2_loco_env_cfg.py:161-162 and :165).  The dynamics are kinematic and deliberately trivial: each action is mapped
to a joint position exactly as the upstream ``_apply_action`` forms its target (go2_loco_env.py:469-473), with the
upstream action scale and clip (go2_loco_env_cfg.py:179-180); no physics, contacts, sensors or rewards are modelled.

Every value that is not a dimension or an upstream constant is test data and is marked ``# placeholder``.  None of
those numbers is copied into a Fact, a Limit or the reference.  The fake does not import the clone and never talks to
a device.
"""

import math
import random

# go2_loco_env_cfg.py:178
ACTION_DIM = 12
# go2_loco_env_cfg.py:248-262: 10 * 45 proprioception history + 300 height scan + 50 privileged + 45 critic
POLICY_SIZE = 10 * 45 + 300 + 50 + 45
# go2_loco_env_cfg.py:249 and sensor/lidar_pattern.py:86-88
DEPTH_STACK = 2
DEPTH_HEIGHT = 25
DEPTH_WIDTH = 60
DEPTH_SIZE = DEPTH_STACK * DEPTH_HEIGHT * DEPTH_WIDTH
# go2_loco_env_cfg.py:161, :162 and :165: 25.0 s / (1/200 s * 4)
EPISODE_LENGTH_S = 25.0
CONTROL_STEP_S = (1.0 / 200.0) * 4
MAX_EPISODE_STEPS = int(round(EPISODE_LENGTH_S / CONTROL_STEP_S))
# go2_loco_env_cfg.py:179-180
ACTION_SCALE = 0.25
ACTION_TARGET_CLIP = (-100.0, 100.0)


def _shape(values):
    """The shape of a nested list of numbers (a scalar has shape ``()``)."""

    if isinstance(values, (list, tuple)):
        return (len(values),) + (_shape(values[0]) if values else ())
    return ()


def _grid(value):
    """A fresh ``DEPTH_STACK x DEPTH_HEIGHT x DEPTH_WIDTH`` grid of ``value``."""

    return [[[value for _ in range(DEPTH_WIDTH)] for _ in range(DEPTH_HEIGHT)] for _ in range(DEPTH_STACK)]


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: low/high bounds, shape and dtype for the bridge."""

    def __init__(self, low, high):
        self.low = low
        self.high = high
        self.shape = _shape(low)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeGo2LocoEnv:
    """Single-environment kinematic stand-in for ``go2_parkour.tasks.go2_loco_env:Go2LocoEnv``.

    The upstream class inherits ``reset``, ``step`` and ``close`` from Isaac Lab's ``DirectRLEnv`` outside the clone;
    gate G7 treats those Gymnasium environment members as possibly absent and reports a warning.  No other public
    method is defined here, so the fake adds no surface the upstream class does not have.
    """

    def __init__(self, **_options):
        # Unbounded Box: the action bounds come from Isaac Lab's DirectRLEnv, which is outside the clone, so no
        # finite action limit is claimed.  Only the width (12) is cited.
        self.action_space = Box([-math.inf] * ACTION_DIM, [math.inf] * ACTION_DIM)
        self.observation_space = Dict({
            "policy": Box([-math.inf] * POLICY_SIZE, [math.inf] * POLICY_SIZE),
            "depth": Box(_grid(-math.inf), _grid(math.inf)),
        })
        self._rng = random.Random()
        self._home = [0.0] * ACTION_DIM          # placeholder: reset home pose
        self._joints = list(self._home)
        self._tick = 0
        self._episode = 0

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        # placeholder: the fake's reset pose; the upstream pose comes from the Isaac Lab scene and events
        self._home = [self._rng.uniform(-0.1, 0.1) for _ in range(ACTION_DIM)]
        self._joints = list(self._home)
        self._tick = 0
        self._episode += 1
        return self._observation(), {}

    def step(self, action):
        values = list(action)
        if len(values) != ACTION_DIM:
            raise ValueError(f"expected {ACTION_DIM} action values, got {len(values)}")
        target = []
        for home, value in zip(self._home, values):
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("the action values must be finite")
            target.append(min(max(home + ACTION_SCALE * number, ACTION_TARGET_CLIP[0]), ACTION_TARGET_CLIP[1]))
        self._joints = target
        self._tick += 1
        # placeholder: reward and termination are not modelled; the upstream reward terms and cutoffs are not copied
        return self._observation(), 0.0, False, self._tick >= MAX_EPISODE_STEPS, {"tick": self._tick}

    def close(self):
        self._joints = None

    def _observation(self):
        # placeholder: policy values are derived from the fake's 12 coordinates; the rest are zeros
        policy = [0.0] * POLICY_SIZE
        policy[:ACTION_DIM] = list(self._joints or [0.0] * ACTION_DIM)
        # placeholder: constant depth values; the upstream depth comes from the Mid-360 ray caster
        return {"policy": policy, "depth": _grid(0.5)}
