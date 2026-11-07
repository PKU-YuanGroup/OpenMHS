"""Fake backend of the Unitree G1 whole-body cylinder task: a pure Python kinematic stand-in.

Why a fake: the acceptance gate has no Isaac Sim, no Isaac Lab, no GPU and no fetched USD assets (README.md:127), and
package code never imports the clone.  This module stands in for the environment that
``gym.make("Isaac-Move-Cylinder-G129-Dex1-Wholebody", cfg=env_cfg).unwrapped`` builds in sim_main.py:185.  It exposes
only the members of the Gymnasium environment interface (``action_space``, ``observation_space``, ``reset``, ``step``,
``close``; gate G7), and it returns the observation terms the task's policy group declares
(tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:74-83).

What this is not: the Isaac Lab environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* no PhysX, rigid-body dynamics, contacts or USD robot model; the action moves two reduced joint targets with a
  first-order stand-in;
* the camera image is 1x2x2x3 instead of the deployed 1x480x640x3 placeholder;
* the initial joint values, the gain and the reward are test data, not measurements.

Timing facts used here (the only non-test numbers): one control step is 20 ms (decimation 4 * sim.dt 0.005,
hw_env_cfg.py:144-147) and an episode is configured for 20.0 s (hw_env_cfg.py:145), i.e. 1000 control steps.  The task
has no termination terms (TerminationsCfg is empty, hw_env_cfg.py:90-94), so the fake never terminates and only
truncates at the episode length.
"""

import math
import random

# hw_env_cfg.py:144-147: decimation 4 at sim.dt = 0.005 s -> one control step of 20 ms
CONTROL_STEP_S = 0.02
# hw_env_cfg.py:145: episode_length_s = 20.0, so 20.0 / 0.02 = 1000 control steps
EPISODE_STEPS = 1000
# g1_29dof_state.py:152-156: 29 positions, 29 velocities and 29 torques
BODY_JOINTS = 29
BODY_OBSERVATION = 3 * BODY_JOINTS
# gripper_state.py:104-106: the two gripper joints are read at indices 31 and 29
GRIPPER_VALUES = 2
# camera_state.py:79-81: the deployed placeholder is (1, 480, 640, 3); this small stand-in keeps receipts short
CAMERA_SHAPE = (1, 2, 2, 3)  # placeholder
# placeholder: the fake moves two reduced joint targets; the real action covers every articulation joint and its
# count comes from the USD asset (robots/unitree.py:538), not from text in the clone
ACTION_VALUES = 2  # placeholder
# placeholder: first-order gain and reward of the stand-in, not measured behaviour
TRACKING_GAIN = 0.5  # placeholder
STEP_REWARD = 1.0  # placeholder
# placeholder: the fake's initial joint range, not a device or USD joint limit
RESET_JOINT_RANGE = (-0.2, 0.2)  # placeholder
RESET_GRIPPER_RANGE = (0.0, 0.05)  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element, as the bridge reads them."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named sub-spaces, as the bridge reads them."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _flat(shape):
    count = 1
    for item in shape:
        count *= item
    return count


class FakeMoveCylinderG129Dex1WholebodyEnv:
    """The registered task without Isaac Sim: ``reset(seed, options)`` and ``step(action)`` of a Gymnasium env.

    The action space is unbounded because the deployed joint-position limits live in the USD asset and are not stated
    in the clone; the fake therefore publishes no invented bound.  The camera image is a smaller stand-in.
    """

    def __init__(self, **_options):
        self.action_space = Box([-math.inf] * ACTION_VALUES, [math.inf] * ACTION_VALUES,
                                (ACTION_VALUES,))
        self.observation_space = Dict({
            "robot_joint_state": Box([-math.inf] * BODY_OBSERVATION, [math.inf] * BODY_OBSERVATION,
                                     (BODY_OBSERVATION,)),
            "robot_gipper_state": Box([-math.inf] * GRIPPER_VALUES, [math.inf] * GRIPPER_VALUES,
                                      (GRIPPER_VALUES,)),
            "camera_image": Box([0.0] * _flat(CAMERA_SHAPE), [255.0] * _flat(CAMERA_SHAPE), CAMERA_SHAPE),  # placeholder
        })
        self._rng = random.Random()
        self._joint_pos = [0.0] * BODY_JOINTS  # placeholder
        self._joint_vel = [0.0] * BODY_JOINTS  # placeholder
        self._joint_torque = [0.0] * BODY_JOINTS  # placeholder
        self._gripper_pos = [0.0] * GRIPPER_VALUES  # placeholder
        self._episode_steps = 0  # placeholder

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        self._joint_pos = [self._rng.uniform(*RESET_JOINT_RANGE) for _ in range(BODY_JOINTS)]  # placeholder
        self._joint_vel = [0.0] * BODY_JOINTS  # placeholder
        self._joint_torque = [0.0] * BODY_JOINTS  # placeholder
        self._gripper_pos = [self._rng.uniform(*RESET_GRIPPER_RANGE) for _ in range(GRIPPER_VALUES)]  # placeholder
        self._episode_steps = 0  # placeholder
        return self._observation(), {}

    def step(self, action):
        values = [float(value) for value in action]
        if len(values) != ACTION_VALUES:
            raise ValueError(f"the action has {len(values)} values; this environment takes {ACTION_VALUES}")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("the action values must be finite")
        for index, target in enumerate(values):
            previous = self._joint_pos[index]
            self._joint_pos[index] = previous + TRACKING_GAIN * (target - previous)  # placeholder
            self._joint_vel[index] = (self._joint_pos[index] - previous) / CONTROL_STEP_S  # placeholder
        self._episode_steps += 1
        # hw_env_cfg.py:90-94 has no termination terms; hw_env_cfg.py:145 gives the 20 s episode length
        terminated = False
        truncated = self._episode_steps >= EPISODE_STEPS
        return self._observation(), STEP_REWARD, terminated, truncated, {}

    def close(self):
        pass

    def _observation(self):
        body = list(self._joint_pos) + list(self._joint_vel) + list(self._joint_torque)
        camera = [
            [
                [[0.0, 0.0, 0.0] for _ in range(CAMERA_SHAPE[2])]  # placeholder
                for _ in range(CAMERA_SHAPE[1])  # placeholder
            ]
            for _ in range(CAMERA_SHAPE[0])  # placeholder
        ]
        return {
            "robot_joint_state": body,
            "robot_gipper_state": list(self._gripper_pos),
            "camera_image": camera,
        }
