"""Fake backend of the laser suite DoorOpen driver: a physics-free stand-in for the robosuite environment.

Why a fake: the upstream environment constructs a robosuite/MuJoCo world through mujoco-py and needs mujoco-py,
numpy, scipy and the clone's model assets.  Those packages are not installed where the acceptance gate runs, package
code never imports the clone, and the clone must never be executed.  This module instead mirrors the public
environment interface the driver uses: ``reset()``, ``step(action)`` and ``close()``, which the upstream class
inherits from the environment base class (``robosuite/environments/base.py:137-142``, ``:180-201`` and ``:344``).
Gate G7 compares these names with ``robosuite.environments.door_open:DoorOpen``.

What this is not: the upstream environment.  There is no MuJoCo world, no robosuite robot, no table, door object or
controller, no camera and no contact model.  Its state is a short list of placeholder numbers; every number below is
test data, marked ``# placeholder``, not a fact, a limit or a device property.  The driver's fidelity ``gaps`` state
the same.  Nothing here talks to a device.
"""

#: placeholder: number of end-effector coordinates kept by the stand-in.
_EEF_DIM = 3
#: placeholder: number of gripper coordinates kept by the stand-in.
_GRIPPER_DIM = 2
#: placeholder: fraction of an action value that one fake step applies to the end effector.
_ACTION_GAIN = 0.01
#: placeholder: fraction of the first action value that one fake step applies to the door hinge.
_HINGE_GAIN = 0.02


class FakeDoorOpen:
    """A deterministic, physics-free stand-in for ``DoorOpen``."""

    def __init__(self, **_options):
        self._tick = 0                                  # placeholder
        self._episode = 0                               # placeholder
        self._eef = [0.5, 0.0, 1.0]                     # placeholder
        self._gripper = [0.0, 0.0]                      # placeholder
        self._hinge = 0.0                               # placeholder
        self._closed = False

    def reset(self):
        """Start a new episode; the upstream reset returns an observation dictionary."""

        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._episode += 1
        self._tick = 0                                  # placeholder
        self._eef = [0.5, 0.0, 1.0]                     # placeholder
        self._gripper = [0.0, 0.0]                      # placeholder
        self._hinge = 0.0                               # placeholder
        return self._observation()

    def step(self, action):
        """``base.py:180-201``: advance one step and return ``(obs, reward, done, info)``."""

        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = [float(item) for item in action]
        self._tick += 1
        for index in range(_EEF_DIM):
            if index < len(values):
                self._eef[index] = self._eef[index] + _ACTION_GAIN * values[index]  # placeholder gain
        if values:
            self._hinge = self._hinge + _HINGE_GAIN * values[0]                     # placeholder gain
        return self._observation(), 0.0, False, {"success": False}                  # placeholders

    def close(self):
        """``base.py:344``: the upstream close releases the viewer; the stand-in marks itself closed."""

        self._closed = True

    def _observation(self):
        """A placeholder observation with the robot and task keys the clone's observation builds."""

        return {
            "robot0_eef_pos": list(self._eef),            # placeholder
            "robot0_eef_quat": [0.0, 0.0, 0.0, 1.0],     # placeholder
            "robot0_gripper_qpos": list(self._gripper),  # placeholder
            "task_state": [0.0, self._hinge, 0.0] + list(self._eef),  # placeholder
            "target_pos": [0.0, 0.0, 0.0],               # placeholder
            "tick": self._tick,                           # placeholder
        }
