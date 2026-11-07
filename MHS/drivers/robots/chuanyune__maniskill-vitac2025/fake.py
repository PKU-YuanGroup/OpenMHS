"""Fake backend of the ManiSkill-ViTac 2025 Track 1 peg-insertion driver.

Why a fake: the upstream environment builds a SAPIEN scene and an IPC tactile sensor and expects CUDA (the class
the driver names as ``native``), so it cannot be imported where the acceptance gate runs.  This module is a pure
Python kinematic stand-in for ``envs.peg_insertion:PegInsertionSimMarkerFLowEnv``: it exposes the public members of
that class (``reset``, ``step``, ``close``; gate G7), the same action space (a three-value ``Box`` in -1..1) and the
same observation space (``relative_motion`` 4, ``gt_offset`` 3 and ``marker_flow`` 2 x 2 x 128 x 2).  The two space
classes duck-type ``gymnasium.spaces.Box`` and ``gymnasium.spaces.Dict``: the bridge reads ``low``, ``high``,
``shape``, ``dtype`` and ``spaces``.

What this is not: the upstream simulator.  It has no rigid-body contact, no IPC/FEM tactile deformation, no marker
flow and no rendering; the observation's marker flow is all zeros and the insertion depth is advanced by a fixed
step per tick.  Those differences are listed in the driver's fidelity ``gaps``.

Every number below except the action bounds is placeholder test data, not a fact about the device: the comments
name the upstream line the stand-in mirrors, but a Fact, a Limit or the reference never takes such a value from
this file.  The action bounds copy the upstream space, and the driver's ``action_space_ref`` cites its line.
"""

import random

# The upstream action space is Box(low=-1, high=1, shape=(3,)) (Track_1/envs/peg_insertion.py:294-296; its shape
# is that of max_action_mm_deg, which :292 asserts to be (3,)).  These two lists copy it.
ACTION_LOW = [-1.0, -1.0, -1.0]
ACTION_HIGH = [1.0, 1.0, 1.0]
# placeholder: mirrors the constructor default max_action_mm_deg = [2.0, 2.0, 4.0] (peg_insertion.py:120-124)
MAX_ACTION_MM_DEG = [2.0, 2.0, 4.0]
# placeholder: mirrors the constructor default z_step_size_mm = 0.075 (peg_insertion.py:121)
Z_STEP_SIZE_MM = 0.075
# placeholder: mirrors the constructor default max_steps = 15 (peg_insertion.py:122)
MAX_STEPS = 15
# placeholder: mirrors the constructor defaults step_penalty = 1.0 and final_reward = 10.0 (peg_insertion.py:118-119)
STEP_PENALTY = 1.0
FINAL_REWARD = 10.0
# placeholder: mirrors the error thresholds 12 mm and 15 degrees (peg_insertion.py:961-965)
MAX_OFFSET_MM = 12.0
MAX_THETA_DEG = 15.0
# placeholder: mirrors the 1e-5 slack of the error thresholds (peg_insertion.py:962-964)
THRESHOLD_SLACK = 1e-5
# placeholder: mirrors the success depth gate of 0.35 mm (peg_insertion.py:975)
SUCCESS_DEPTH_MM = 0.35
# placeholder: mirrors the -0.3 mm peg-relative-z gate (peg_insertion.py:976)
SUCCESS_RELATIVE_Z_MM = -0.3
# placeholder: mirrors marker_flow_size = 128 (peg_insertion.py:1181)
MARKER_FLOW_SIZE = 128


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` for the bridge."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of member name to member space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _marker_flow():
    """A ``(2, 2, MARKER_FLOW_SIZE, 2)`` zero array; placeholder for the tactile marker-flow observation."""

    return [[[[0.0, 0.0] for _ in range(MARKER_FLOW_SIZE)] for _ in range(2)] for _ in range(2)]


class FakePegInsertionMarkerFlowEnv:
    """A kinematic stand-in for ``PegInsertionSimMarkerFLowEnv`` with no SAPIEN, IPC or CUDA dependency."""

    def __init__(self, **_options):
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, (3,), "float32")
        self.observation_space = Dict({
            "relative_motion": Box(-float("inf"), float("inf"), (4,), "float32"),
            "gt_offset": Box(-float("inf"), float("inf"), (3,), "float32"),
            "marker_flow": Box(-float("inf"), float("inf"),
                               (2, 2, MARKER_FLOW_SIZE, 2), "float32"),
        })
        self._rng = random.Random()
        self._seed = 0
        self._steps = 0
        self._offset = [0.0, 0.0, 0.0]
        self._depth_mm = 0.0
        self._relative_motion = [0.0, 0.0, 0.0, 0.0]
        self._closed = False

    def reset(self, offset_mm_deg=None, seed=None, peg_idx=None, options=None):
        """Reset the offset and the step counter; mirrors the upstream reset signature (peg_insertion.py:335-337)."""

        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        if offset_mm_deg is None:
            self._offset = [
                self._rng.uniform(-5.0, 5.0),    # placeholder: constructor default peg_x_max_offset_mm
                self._rng.uniform(-5.0, 5.0),    # placeholder: constructor default peg_y_max_offset_mm
                self._rng.uniform(-10.0, 10.0),  # placeholder: constructor default peg_theta_max_offset_deg
            ]
        else:
            self._offset = [float(value) for value in offset_mm_deg[:3]]
        self._steps = 0
        self._depth_mm = 0.0
        self._relative_motion = [0.0, 0.0, 0.0, 0.0]
        return self._observation(), self._info()

    def step(self, action):
        """Advance one insertion step; mirrors the five-value step contract (peg_insertion.py:770-809)."""

        values = [float(value) for value in action]
        if len(values) != 3:
            raise ValueError("the action must have three values")
        self._steps += 1
        self._offset[0] += values[0] * MAX_ACTION_MM_DEG[0]
        self._offset[1] += values[1] * MAX_ACTION_MM_DEG[1]
        self._offset[2] += values[2] * MAX_ACTION_MM_DEG[2]
        self._depth_mm += Z_STEP_SIZE_MM
        self._relative_motion = [self._offset[0], self._offset[1], self._offset[2], -self._depth_mm]
        info = self._info()
        reward = -STEP_PENALTY + (FINAL_REWARD if info["is_success"] else 0.0)
        return self._observation(), reward, info["is_success"], self._truncated(info), info

    def close(self):
        self._closed = True

    def _observation(self):
        return {
            "relative_motion": list(self._relative_motion),
            "gt_offset": list(self._offset),
            "marker_flow": _marker_flow(),
        }

    def _info(self):
        error_too_large = (
            abs(self._offset[0]) > MAX_OFFSET_MM + THRESHOLD_SLACK
            or abs(self._offset[1]) > MAX_OFFSET_MM + THRESHOLD_SLACK
            or abs(self._offset[2]) > MAX_THETA_DEG + THRESHOLD_SLACK
        )
        too_many_steps = self._steps >= MAX_STEPS
        peg_relative_z_mm = [-self._depth_mm]
        is_success = (
            not error_too_large
            and not too_many_steps
            and self._steps * Z_STEP_SIZE_MM > SUCCESS_DEPTH_MM
            and all(value < SUCCESS_RELATIVE_Z_MM for value in peg_relative_z_mm)
        )
        return {
            "steps": self._steps,
            "surface_diff_m": [0.0, 0.0],
            "tactile_movement_too_large": False,
            "too_many_steps": too_many_steps,
            "error_too_large": error_too_large,
            "peg_relative_z_mm": peg_relative_z_mm,
            "is_success": is_success,
            "relative_motion_mm_deg": list(self._relative_motion),
            "gt_offset_mm_deg": list(self._offset),
        }

    @staticmethod
    def _truncated(info):
        return bool(info["too_many_steps"] or info["tactile_movement_too_large"] or info["error_too_large"])
