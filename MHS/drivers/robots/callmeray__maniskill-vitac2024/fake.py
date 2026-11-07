"""Fake backend of the ViTac peg-insertion Gymnasium driver.

The upstream environment is a SAPIEN + SapienIPC GPU simulation (``envs/peg_insertion.py`` imports ``sapien`` and
builds an ``IPCSystem``); it is not importable where the gate runs and package code never imports the clone.  This
module is a pure Python kinematic stand-in for the class the driver names as ``native``,
``ContinuousInsertionSimGymRandomizedPointFLowEnv``.  It reproduces the non-physics rules of the upstream step:

* the action space is ``Box(low=-1, high=1, shape=(3,), dtype=np.float32)`` (``envs/peg_insertion.py:129``);
* the action is multiplied by ``max_action`` and clipped, rotated by the current theta and added to the offset
  (``envs/peg_insertion.py:493-503``, ``:624-626``);
* the error-too-large thresholds are 12 mm on x and y and 15 on theta (``envs/peg_insertion.py:506-509``);
* the reward is the error decrease minus ``step_penalty``, with the error/truncation branches of
  ``envs/peg_insertion.py:704-715``;
* the episode truncates at ``max_steps`` and terminates on ``error_too_large`` (``envs/peg_insertion.py:717-721``).

What it is not: the upstream environment.  It does not simulate contacts, elastic sensor deformation, marker motion,
peg/hole geometry or the success test, and it never computes a marker flow.  The constants below are test data
(placeholder), not facts or limits of the device; the driver's ``fidelity.gaps`` says so.  Nothing here talks to a
device.
"""

import math
import random

#: The upstream error thresholds, envs/peg_insertion.py:506-509 (12 mm, 12 mm, 15) with the 1e-5 tolerance.
X_ERROR_LIMIT = 12.0
Y_ERROR_LIMIT = 12.0
THETA_ERROR_LIMIT = 15.0
ERROR_TOLERANCE = 1e-5

# placeholder: action scaling and episode budget of the fake, not a bound of the upstream environment.
FAKE_MAX_ACTION = (2.0, 2.0, 4.0)
# placeholder: episode budget of the fake (the upstream constructor default is 15, envs/peg_insertion.py:73).
FAKE_MAX_STEPS = 15
# placeholder: reward constants of the fake, chosen for the test; the upstream passes them in from the caller.
FAKE_STEP_PENALTY = 1.0
FAKE_FINAL_REWARD = 10.0

#: The registered class's default observation shapes, envs/peg_insertion.py:771-778.
MARKER_FLOW_SHAPE = (2, 2, 128, 2)
GT_OFFSET_SHAPE = (3,)
# placeholder: the float32 range the upstream convert_observation_to_space uses for every array element
# (utils/gym_env_utils.py:7-10).  It is the fake space's bound, not a device limit.
FLOAT32_MAX = 3.4028234663852886e38


class Box:
    """A duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Dict:
    """A duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` and its members."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _zero_marker_flow():
    """The real marker_flow shape as a zero array: the fake computes no tactile flow."""
    return [[[[0.0, 0.0] for _ in range(MARKER_FLOW_SHAPE[2])] for _ in range(MARKER_FLOW_SHAPE[1])]
            for _ in range(MARKER_FLOW_SHAPE[0])]


_ZERO_MARKER_FLOW = _zero_marker_flow()


class FakeContinuousInsertionEnv:
    """Kinematic stand-in for ``ContinuousInsertionSimGymRandomizedPointFLowEnv``.

    The public members are the ones the bridge needs and the upstream class has (``reset``, ``step``, ``close``;
    gate G7).  ``action_space`` and ``observation_space`` are instance attributes, as upstream.
    """

    def __init__(self, **_options):
        self.render_rgb = False
        # envs/peg_insertion.py:129: the action space is the only input bound the bridge derives.
        self.action_space = Box([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0], shape=(3,))
        # envs/peg_insertion.py:775-778: the registered class's default observation.
        self.observation_space = Dict({
            "gt_offset": Box([-FLOAT32_MAX] * GT_OFFSET_SHAPE[0], [FLOAT32_MAX] * GT_OFFSET_SHAPE[0],
                             shape=GT_OFFSET_SHAPE),
            "marker_flow": Box([-FLOAT32_MAX] * 1024, [FLOAT32_MAX] * 1024, shape=MARKER_FLOW_SHAPE),
        })
        # placeholder: the fake's own parameters; see the module docstring.
        self.max_action = FAKE_MAX_ACTION
        self.max_steps = FAKE_MAX_STEPS
        self.step_penalty = FAKE_STEP_PENALTY
        self.final_reward = FAKE_FINAL_REWARD
        self._rng = random.Random(0)
        self._offset = [0.0, 0.0, 0.0]
        self._elapsed_steps = 0
        self._errors = []
        self._error_too_large = False
        self._too_many_steps = False
        self._closed = False

    @staticmethod
    def _error(offset):
        """``evaluate_error``, envs/peg_insertion.py:44-47."""
        return math.sqrt(offset[0] * offset[0] + offset[1] * offset[1] + offset[2] * offset[2])

    def _observation(self):
        return {"gt_offset": list(self._offset), "marker_flow": _ZERO_MARKER_FLOW}

    def reset(self, offset=None, seed=None, peg_idx=None):
        """``reset`` of envs/peg_insertion.py:467-490, without the physics scene.

        ``peg_idx`` selects the upstream peg/hole geometry; the fake has no geometry and accepts it unchanged.
        """
        if seed is not None:
            self._rng.seed(int(seed))
        if offset is None:
            # placeholder: the fake's initial offset draw; the upstream draws a collision-checked offset from
            # peg_x_max_offset=5, peg_y_max_offset=5 and peg_theta_max_offset=10 (envs/peg_insertion.py:76-78, 467).
            self._offset = [self._rng.uniform(-5.0, 5.0), self._rng.uniform(-5.0, 5.0),
                            self._rng.uniform(-10.0, 10.0)]
        else:
            self._offset = [float(value) for value in offset]
        self._elapsed_steps = 0
        self._error_too_large = False
        self._too_many_steps = False
        self._errors = [self._error(self._offset)]
        return self._observation(), {}

    def step(self, action):
        """``step`` of envs/peg_insertion.py:618-633, with a kinematic offset instead of the IPC simulation."""
        self._elapsed_steps += 1
        raw = [float(value) for value in action]
        # envs/peg_insertion.py:625 multiplies by max_action; :493 clips the result to +-max_action.
        scaled = [max(-self.max_action[index], min(self.max_action[index], raw[index] * self.max_action[index]))
                  for index in range(3)]
        current_theta = self._offset[2] * math.pi / 180.0
        action_x = scaled[0] * math.cos(current_theta) - scaled[1] * math.sin(current_theta)
        action_y = scaled[0] * math.sin(current_theta) + scaled[1] * math.cos(current_theta)
        action_theta = scaled[2]
        self._offset[0] += action_x
        self._offset[1] += action_y
        self._offset[2] += action_theta

        # envs/peg_insertion.py:506-514
        if (abs(self._offset[0]) > X_ERROR_LIMIT + ERROR_TOLERANCE
                or abs(self._offset[1]) > Y_ERROR_LIMIT + ERROR_TOLERANCE
                or abs(self._offset[2]) > THETA_ERROR_LIMIT + ERROR_TOLERANCE):
            self._error_too_large = True
        elif self._elapsed_steps > self.max_steps:
            self._too_many_steps = True

        # envs/peg_insertion.py:704-715.  The success test needs the peg depth and the sensor surface movement, which
        # the fake does not model, so is_success is always False and final_reward is never paid.
        self._errors.append(self._error(self._offset))
        reward = self._errors[-2] - self._errors[-1] - self.step_penalty
        if self._too_many_steps:
            reward = 0.0
        elif self._error_too_large:
            reward += (-2 * self.step_penalty * (self.max_steps - self._elapsed_steps) + self.step_penalty)
        is_success = False

        info = {
            "steps": self._elapsed_steps,
            "is_success": is_success,
            "error_too_large": self._error_too_large,
            "too_many_steps": self._too_many_steps,
        }
        terminated = self._error_too_large or is_success          # envs/peg_insertion.py:720-721
        truncated = self._elapsed_steps >= self.max_steps          # envs/peg_insertion.py:717-718
        return self._observation(), reward, terminated, truncated, info

    def close(self):
        self._closed = True
