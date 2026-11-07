"""Fake backend for the TAVIS Gymnasium driver.

The gate cannot import the upstream environment: TAVIS needs Isaac Sim, Isaac Lab, IsaacLab-Arena, a Linux NVIDIA RTX
machine and USD assets downloaded from Hugging Face (README.md:38-49), and the upstream stack was not started here.
This module is a small, pure Python stand-in for the single-environment part of what ``make_tavis_env`` returns: an
Isaac Lab ``ManagerBasedRLEnv`` inside ``CanonicalFrameWrapper`` (make_env.py:90-100).  The public methods the
Gymnasium bridge calls are the two methods of that environment class (``reset``, ``step``); the space objects
duck-type ``gymnasium.spaces.Box`` and ``Dict`` (the bridge reads ``low``, ``high``, ``shape`` and ``spaces``).
The driver names the card's GR1T2 embodiment class as ``native`` because the card's factory is a function and G7
resolves a class; the fake therefore has the Gymnasium interface of the environment while G7 compares it with the
embodiment class, whose base lies outside the clone, and reports those names as ``MAYBE_ABSENT`` warnings by design.

The fake keeps a 19-number kinematic coordinate, matching the GR1T2 unified action layout
[7 left-arm IK, 7 right-arm IK, 1 head roll, 2 head pitch/yaw, 2 grippers] (gr1t2.py:8-10).  The action Box has no
finite bound: the clone states a 19-D layout but no numeric per-element bound, so no bound is claimed.  The
observation stands in for the environment's policy observation group; it is not the camera or joint-state arrays of
an Isaac Lab run.  Every number below is test data only (each marked ``# placeholder``); none is copied into a Fact,
a Limit or the reference.
"""

import random

# No finite bound is claimed: the fake's action Box is unbounded, so the bridge publishes no action limit.
INF = float("inf")
# placeholder: the GR1T2 unified action width; the real batched Box is chosen by the composed action config.
ACTION_WIDTH = 19
# placeholder: the fake's per-tick gain and initial joint range; the upstream applies IK and physics.
GAIN = 0.1
RESET_LOW, RESET_HIGH = -0.1, 0.1


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a low and a high bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeTavisEnv:
    """A one-environment stand-in for the environment ``make_tavis_env`` returns.

    ``reset(seed, options)`` and ``step(action)`` are the two public methods of the upstream environment class that
    the Gymnasium bridge calls, so gate G7 resolves them in the clone.  The upstream reset is called with
    ``seed``/``options`` by the bridge (the wrapper forwards them to Isaac Lab), and step receives one batched action.
    """

    def __init__(self, **_options):
        # placeholder: one unbounded 19-element action Box; the real width and bounds come from the action terms.
        self.action_space = Box([-INF] * ACTION_WIDTH, [INF] * ACTION_WIDTH)
        # placeholder: one policy group of 19 numbers; the real observation is a Dict of groups with camera images.
        self.observation_space = Dict({"policy": Box([-INF] * ACTION_WIDTH, [INF] * ACTION_WIDTH)})
        self._rng = random.Random()
        self._joints = [0.0] * ACTION_WIDTH                # placeholder: initial coordinate
        self._tick = 0
        self._episode = 0

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        # placeholder: the fake's start range; the upstream start state comes from the composed scene and task.
        self._joints = [self._rng.uniform(RESET_LOW, RESET_HIGH) for _ in range(ACTION_WIDTH)]
        self._tick = 0
        self._episode += 1
        return {"policy": list(self._joints)}, {}

    def step(self, action):
        # placeholder: one scalar action moves each joint by a fixed gain; the upstream applies the composed action
        # terms, canonical-frame conversion and Isaac Lab physics through the environment step.
        values = list(action) if isinstance(action, (list, tuple)) else []
        for index in range(ACTION_WIDTH):
            value = float(values[index]) if index < len(values) else 0.0
            self._joints[index] += value * GAIN
        self._tick += 1
        return ({"policy": list(self._joints)}, 0.0, False, False, {"tick": self._tick})
