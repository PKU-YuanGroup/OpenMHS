"""Fake backend of the robosuite Task Zoo HammerPlace driver: a pure Python stand-in for ``HammerPlaceEnv``.

Why a fake: robosuite, mujoco-py, numpy, numba and scipy are not installed where the acceptance gate runs, and
package code never imports the clone.  This module models the public surface the driver uses -- ``reset()``,
``step(action)`` and ``close()`` -- of ``HammerPlaceEnv`` and its robosuite ``SingleArmEnv`` base
(hammer_place.py:19, :489-499).  The observation dictionary uses the keys the clone's ``get_state_vector`` reads
(``robot0_gripper_qpos``, ``robot0_eef_pos``, ``robot0_eef_quat``, hammer_place.py:530-533) and the activated
``robot0_joint_pos`` observable (hammer_place.py:332).

What this is not: the upstream environment.  There is no MuJoCo, robosuite, controller, contact, friction,
actuator, sensor, camera or task-success model.  The state transition is a placeholder first-order update, the
reward is always 0.0 and done is always false; the initial state is a fixed placeholder.  The real observation also
carries the agentview and eye-in-hand camera images that the constructor enables by default (hammer_place.py:28,
:43-45); this fake returns none of them.  These differences are listed in the driver's fidelity ``gaps``.  Every
number below is test data, not a fact about the device, and is marked ``# placeholder``.

Nothing here talks to a device.
"""

#: placeholder: the fixed initial end-effector position in the fake's tabletop frame.
START_EEF_POS = [0.0, 0.0, 0.9]
#: placeholder: how far one fake step moves the end effector per unit of the first three action values.
STEP_GAIN = 0.005
#: placeholder: the fixed hammer pose reported by the fake.
START_HAMMER_POS = [0.14, -0.165, 0.92]
#: placeholder: the fixed cabinet pose reported by the fake.
START_CABINET_POS = [0.2, 0.30, 0.03]
#: placeholder: joint count of the fake's seven-joint single arm.
JOINT_COUNT = 7
#: placeholder: the fake force-history width and length named by hammer_place.py:496.
FORCE_WIDTH = 6
FORCE_HISTORY = 16


def _zeros(count):
    """A fresh zero list; placeholder joint state."""
    return [0.0] * count


class FakeHammerPlaceEnv:
    """``HammerPlaceEnv`` without robosuite: ``reset``, ``step`` and ``close`` only (gate G7)."""

    def __init__(self, **_options):
        self._closed = False
        self._started = False
        self._tick = 0
        self._eef_pos = list(START_EEF_POS)          # placeholder
        self._gripper_qpos = [0.0, 0.0]               # placeholder
        self._joint_pos = _zeros(JOINT_COUNT)         # placeholder
        self._joint_vel = _zeros(JOINT_COUNT)         # placeholder
        self._hammer_pos = list(START_HAMMER_POS)     # placeholder
        self._cabinet_pos = list(START_CABINET_POS)   # placeholder

    def reset(self):
        """``HammerPlaceEnv.reset()`` -> the observation dictionary; it takes no seed (hammer_place.py:443-456)."""
        self._closed = False
        self._started = True
        self._tick = 0
        self._eef_pos = list(START_EEF_POS)           # placeholder
        self._gripper_qpos = [0.0, 0.0]               # placeholder
        self._joint_pos = _zeros(JOINT_COUNT)         # placeholder
        self._joint_vel = _zeros(JOINT_COUNT)         # placeholder
        self._hammer_pos = list(START_HAMMER_POS)     # placeholder
        self._cabinet_pos = list(START_CABINET_POS)   # placeholder
        return self._observation()

    def step(self, action):
        """``HammerPlaceEnv.step(action)`` -> ``(observation, reward, done, info)`` (hammer_place.py:489-499)."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if not self._started:
            raise RuntimeError("call reset before step")
        try:
            values = [float(value) for value in action]
        except (TypeError, ValueError) as exc:
            raise ValueError("action must be a numeric vector") from exc
        if not values:
            raise ValueError("action must be a non-empty numeric vector")
        # hammer_place.py:489-492: the environment reads the first three values and the last one as the gripper.
        deltas = (values[:3] + [0.0, 0.0, 0.0])[:3]
        self._eef_pos = [position + STEP_GAIN * delta
                         for position, delta in zip(self._eef_pos, deltas)]   # placeholder
        self._gripper_qpos = [0.0, values[-1]]                              # placeholder
        self._joint_pos = [0.0] * JOINT_COUNT                               # placeholder
        self._joint_vel = [0.0] * JOINT_COUNT                               # placeholder
        self._tick += 1
        # The fake never reaches the cabinet success predicate (hammer_place.py:463-475): done stays false.
        info = {
            "history_ft": [[0.0] * FORCE_WIDTH for _ in range(FORCE_HISTORY)],   # placeholder
            "recent_ft": [],                                                     # placeholder
        }
        return self._observation(), 0.0, False, info

    def close(self):
        """``SingleArmEnv.close()`` releases the simulator; here it marks the fake closed."""
        self._closed = True

    def _observation(self):
        """The observation keys the clone names, with placeholder values."""
        return {
            "robot0_eef_pos": list(self._eef_pos),
            "robot0_eef_quat": [0.0, 0.0, 0.0, 1.0],          # placeholder
            "robot0_gripper_qpos": list(self._gripper_qpos),
            "robot0_joint_pos": list(self._joint_pos),
            "robot0_joint_vel": list(self._joint_vel),
            "robot0_contact": False,                           # placeholder
            "robot0_eef_force_norm": 0.0,                      # placeholder
            "hammer_pos": list(self._hammer_pos),
            "hammer_quat": [0.0, 0.0, 0.0, 1.0],              # placeholder
            "CabinetObject_pos": list(self._cabinet_pos),
            "CabinetObject_quat": [0.0, 0.0, 0.0, 1.0],       # placeholder
        }
