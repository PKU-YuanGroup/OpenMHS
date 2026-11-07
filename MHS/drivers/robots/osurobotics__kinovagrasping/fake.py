"""Fake backend of the kinovagripper-v0 driver: a pure-Python analytic stand-in for ``KinovaGripper_Env``.

The upstream class is a MuJoCo 1.50 / mujoco-py simulation; neither is installed where the gate runs and package
code never imports the clone.  This module therefore implements the gymnasium surface the bridge calls
(``reset(seed, options)`` and ``step(action)`` returning a five-tuple) and the upstream's public method names
(``reset``, ``step``, ``seed``, ``close``; gate G7).  The action and observation spaces have the upstream bounds:
four velocity commands in -0.8 .. 0.8 (kinova_gripper_env.py:128) and the 48-element Box declared at
kinova_gripper_env.py:211-237.  The integration is kinematic: one bridge tick applies the four commands for
``frame_skip`` model steps of 0.01 s (kinova_gripper_env.py:51, j2s7s300_end_effector_v1_mbox.xml:10), with no
contacts, forces or actuator model.  The lift reward follows the upstream rule (kinova_gripper_env.py:634,
:661-663): when the object z reaches the 0.2 target the reward is 50.0 and the episode terminates.

Every initial pose, object size and finger distance below is test data marked ``# placeholder``; none of them is
a Fact, a Limit or a claimed measurement.  This is not the upstream environment and was never compared with it.
"""

import random

# kinova_gripper_env.py:128 (the action space of the environment)
ACTION_LOW = [-0.8, -0.8, -0.8, -0.8]
ACTION_HIGH = [0.8, 0.8, 0.8, 0.8]
# kinova_gripper_env.py:51 (the constructor default)
FRAME_SKIP = 15
# kinova_gripper_env.py:122 (self.action_scale)
ACTION_SCALE = 0.0333
# j2s7s300_end_effector_v1_mbox.xml:10 (seconds)
MODEL_TIMESTEP_S = 0.01
# kinova_gripper_env.py:634, :661-663 (the lift reward and its tolerance)
OBJECT_TARGET_Z = 0.2
LIFT_TOLERANCE = 0.005
LIFT_REWARD = 50.0

# kinova_gripper_env.py:211-237: the observation Box declared for the local/global state representation
OBS_LOW = ([-0.1, -0.1, 0.0] * 7) + [-0.1, -0.01, 0.0] + ([0.0] * 7) + ([0.0] * 3) + ([0.0] * 13) + [0.0]
OBS_HIGH = (([0.1, 0.1, 0.5] * 7) + [0.1, 0.7, 0.5] + [0.2, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0]
            + ([0.5] * 3) + ([0.1] * 13) + [1.0])


def _clamp(value, low, high):
    return low if value < low else high if value > high else value


class Box:
    """Duck-typed gym ``spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeKinovaGripperEnv:
    """An analytic stand-in for ``gym_kinova_gripper.envs:KinovaGripper_Env``; it talks to no device."""

    metadata = {"render.modes": ["human"]}                       # kinova_gripper_env.py:50

    def __init__(self, arm_or_end_effector="hand", frame_skip=FRAME_SKIP, **_options):
        self.arm_or_hand = arm_or_end_effector
        self.frame_skip = frame_skip
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        self.observation_space = Box(OBS_LOW, OBS_HIGH)
        self._rng = random.Random()
        self._closed = False
        self._done = False
        self._tick = 0
        self._shape_keys = []
        self._hand_orientation = "normal"
        self._hand = [0.0, 0.0, 0.03]                             # placeholder
        self._object = [0.0, 0.3, 0.0]                            # placeholder
        self._joints = [0.0] * 7                                  # placeholder
        self._finger_distance = [0.1] * 13                        # placeholder
        self._object_size = [0.05, 0.05, 0.05]                    # placeholder

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        options = dict(options or {})
        self._shape_keys = options.get("shape_keys", [])           # placeholder default
        self._hand_orientation = options.get("hand_orientation", "normal")  # placeholder default
        self._tick = 0
        self._done = False
        self._hand = [self._rng.uniform(-0.02, 0.02),             # placeholder
                      self._rng.uniform(-0.02, 0.02),             # placeholder
                      0.03]                                       # placeholder
        self._object = [self._hand[0],                            # placeholder
                        self._hand[1] + 0.3,                      # placeholder
                        0.0]                                      # placeholder
        self._joints = [0.0] * 7                                  # placeholder
        self._finger_distance = [0.1] * 13                        # placeholder
        self._object_size = [0.05, 0.05, 0.05]                    # placeholder
        return self._observation(), {"shape_keys": list(self._shape_keys),
                                     "hand_orientation": self._hand_orientation}

    def step(self, action, graspnetwork=False):
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        try:
            values = [float(value) for value in action]
        except (TypeError, ValueError) as exc:
            raise ValueError("action must be four numbers") from exc
        if len(values) != 4:
            raise ValueError("action must be four numbers")
        travel = self.frame_skip * ACTION_SCALE                  # kinova_gripper_env.py:122, :130
        self._hand[0] = _clamp(self._hand[0] + values[0] * travel, -0.1, 0.1)
        self._hand[1] = _clamp(self._hand[1] + values[1] * travel, -0.1, 0.1)
        self._hand[2] = _clamp(self._hand[2] + values[2] * travel, 0.0, 0.5)
        for index in range(4):
            self._joints[index] = _clamp(self._joints[index] + abs(values[index]) * 0.01,  # placeholder gain
                                         0.0, OBS_HIGH[24 + index])
        closed = values[3] * MODEL_TIMESTEP_S * self.frame_skip  # kinova_gripper_env.py:51 with the model timestep
        self._finger_distance = [_clamp(value - closed, 0.0, 0.1) for value in self._finger_distance]
        self._object[0] = self._hand[0]                           # placeholder grasp offset
        self._object[1] = _clamp(self._hand[1] + 0.3, -0.01, 0.7)  # placeholder grasp offset
        self._object[2] = max(self._object[2], self._hand[2])     # placeholder lift coupling
        lifted = (abs(self._object[2] - OBJECT_TARGET_Z) < LIFT_TOLERANCE
                  or self._object[2] >= OBJECT_TARGET_Z)
        reward = LIFT_REWARD if lifted else 0.0
        self._done = lifted
        self._tick += 1
        info = {"finger_reward": 0.0, "grasp_reward": 0.0, "lift_reward": reward}
        return self._observation(), reward, self._done, False, info

    def seed(self, seed=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        return [seed]

    def close(self):
        self._closed = True

    def _observation(self):
        obs = list(self._hand) * 7                                # kinova_gripper_env.py:211-237 layout
        obs += list(self._object)                                 # indices 21-23
        obs += list(self._joints)                                 # indices 24-30
        obs += list(self._object_size)                            # indices 31-33
        obs += list(self._finger_distance)                        # indices 34-46
        obs.append(1.0 if max(self._finger_distance) < 0.05 else 0.0)  # placeholder threshold and flag
        return [_clamp(value, low, high) for value, low, high in zip(obs, OBS_LOW, OBS_HIGH)]
