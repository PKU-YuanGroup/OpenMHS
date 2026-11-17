"""Fake backend of the ClickBell driver: a pure Python analytic stand-in for ``ClickBellEnv``.

Why a fake: the acceptance gate runs without EmbodiChain, dexsim, torch, a CUDA/Vulkan GPU or the CobotMagic assets
(docs/getting_started/installation.md:3-93), and package code never imports the clone.  The public members below are
the ones ``ClickBellEnv`` declares or inherits from the external ``EmbodiedEnv`` base (``__init__``, ``reset``,
``compute_task_state``, ``is_task_success``; gate G7).  ``step``, ``close``, ``action_space`` and ``observation_space``
are the Gymnasium environment interface that the external base provides; they are only warnings under G7.

What this is: a small analytic contract stand-in.  It accepts a 14-value action vector (the task's action
configuration declares 6 DoF for each arm and one value for each gripper, ``configs/click_bell/action_config.json:2-56``;
the documentation repeats the same dimensions at ``docs/tutorials/configuration.md:319``), records the values as the
next ``robot/qpos`` observation, advances one tick, and computes the ClickBell button metric with the upstream success
threshold 0.0048 m (``robosynchallenge/tasks/click_bell/click_bell.py:138``).  The button starts at its rest position
0.0 (the joint range is [-0.005, 0.0], ``click_bell.py:135``) and the fake has no robot or contact model, so the button
never moves and the task never reports success.

What this is not: the upstream environment.  Everything not stated by the clone is a placeholder and is marked
``# placeholder``: the action bounds (-1, 1), the mapping from the action to the observation, the observation values,
and the reset jitter.  The real space, its bounds, its joint order and the physics live in the external EmbodiChain
``EmbodiedEnv`` and the CobotMagic robot, which are not in the clone.  The real observation also carries camera streams
(``sensor/<camera>/color``) that this fake does not produce.  The 361-step limit is the random protocol's value
(``configs/click_bell/random/gym_config.json:4``), not the class registration default 600 (``click_bell.py:34``).
None of this talks to a device.
"""

import random

# click_bell.py:135-139: the button joint range, the success metric and its threshold.
BUTTON_REST_QPOS = 0.0
MOVEMENT_THRESHOLD = 0.0048
# configs/click_bell/random/gym_config.json:4 (the deployed random protocol; click_bell.py:34 registers 600).
MAX_EPISODE_STEPS = 361
# The 14 active CobotMagic values (configs/click_bell/action_config.json:2-56 and replay.py:158).
ACTION_SIZE = 14
# placeholder: the fake has no sourced action bounds; the real EmbodiedEnv space is outside the clone.
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# placeholder: the fake's robot/qpos start jitter, in the observation units of the fake.
RESET_JITTER = 0.01


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a name-to-space mapping (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeClickBellEnv:
    """ClickBell without EmbodiChain: ``reset(seed, options)`` and ``step(action)`` mirror the env contract."""

    def __init__(self, cfg=None, **kwargs):
        # The native __init__ forwards cfg and kwargs to EmbodiedEnv and stores action_config (click_bell.py:37-42);
        # the fake accepts the same call shape and has no simulator to configure.
        self.cfg = cfg
        self.kwargs = dict(kwargs)
        # placeholder: the real action space is derived from the external EmbodiedEnv and the CobotMagic robot.
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE)
        # placeholder: only the robot/qpos key is modelled (configs/click_bell/random/gym_config.json:225-232).
        self.observation_space = Dict({
            "robot/qpos": Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE),
        })
        self._rng = random.Random()
        self._qpos = [0.0] * ACTION_SIZE
        self._button_qpos = [BUTTON_REST_QPOS]
        self._success_flag = False
        self._tick = None
        self._closed = False

    def reset(self, seed=None, options=None):
        """Reset the fake world; a seed reseeds the placeholder start jitter and reset_ids clear the success flag."""
        if self._closed:
            raise RuntimeError("the fake ClickBell environment is closed")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        options = options or {}
        reset_ids = options.get("reset_ids", [0])
        if not isinstance(reset_ids, (list, tuple)):
            reset_ids = [reset_ids]
        # click_bell.py:154-163 clears the latched success only for the reset ids (one env here).
        if 0 in reset_ids:
            self._success_flag = False
        self._button_qpos = [BUTTON_REST_QPOS]
        # placeholder: the fake start state is a small random robot/qpos draw, not a robot reset.
        self._qpos = [self._rng.uniform(-RESET_JITTER, RESET_JITTER) for _ in range(ACTION_SIZE)]
        self._tick = 0
        return {"robot/qpos": list(self._qpos)}, {}

    def step(self, action):
        """Apply one placeholder action and return the Gymnasium five-tuple."""
        if self._closed:
            raise RuntimeError("the fake ClickBell environment is closed")
        if self._tick is None:
            raise AssertionError("Call reset before using step method.")
        values = [float(value) for value in action]
        if len(values) != ACTION_SIZE:
            raise AssertionError(f"the ClickBell action has {ACTION_SIZE} values, got {len(values)}")
        for value in values:
            if not ACTION_LOW <= value <= ACTION_HIGH:
                raise AssertionError(f"action value {value!r} is outside the placeholder action space")
        # placeholder: the action is recorded as the next robot/qpos observation; no robot motion is modelled.
        self._qpos = values
        self._tick += 1
        _success, _fail, metrics = self.compute_task_state()
        terminated = bool(self.is_task_success())
        truncated = self._tick >= MAX_EPISODE_STEPS
        info = dict(metrics)
        info["is_success"] = bool(self._success_flag)
        return {"robot/qpos": list(self._qpos)}, 0.0, terminated, truncated, info

    def compute_task_state(self, **kwargs):
        """The upstream success metric: press_depth = -button_qpos[0], latched at 0.0048 m (click_bell.py:135-150)."""
        press_depth = -self._button_qpos[0]
        current_success = press_depth >= MOVEMENT_THRESHOLD
        self._success_flag = self._success_flag or current_success
        # The upstream method returns a fail tensor and a zero success tensor; is_task_success is the latch.
        return False, False, {"press_depth": press_depth, "movement_threshold": MOVEMENT_THRESHOLD}

    def is_task_success(self, **kwargs):
        """The latched ClickBell success (click_bell.py:152-153)."""
        return self._success_flag

    def close(self):
        """Close the fake world."""
        self._closed = True
        self._tick = None
