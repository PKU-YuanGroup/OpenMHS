"""Fake backend of the UR5/Robotiq driver: a pure Python stand-in for ``ClutteredPushGrasp``.

Why a fake: the upstream environment needs PyBullet, numpy, the YCB asset tree and a robot loaded from URDF, and
package code never imports the clone.  This module mirrors the *interface* of ``env:ClutteredPushGrasp`` (the class
the driver names as ``native``): ``step(action, control_method)`` reads the seven-element action, advances one
control step, and returns ``(observation, reward, done, info)``; ``reset()`` restores the start state;
``get_observation()`` returns the robot observation dict; ``close()`` closes the backend (``env.py:81-137``).
The public members are the upstream class's members (gate G7).

What this is not: the upstream PyBullet environment.  It does not simulate contacts, inverse kinematics, gravity,
the box button, the reward thresholds or the camera.  Every number below is test data, not a fact about the
device.  The fake was not compared with the upstream environment.  Nothing here talks to a device.
"""

#: Joint count of the UR5 arm plus the gripper joints the URDF loads (test data, not a fact).
_JOINT_COUNT = 12  # placeholder
#: Start end-effector position (test data, not a fact).
_START_EE = [0.0, 0.0, 0.5]  # placeholder
#: Start joint positions (test data, not a fact).
_START_POSITIONS = [0.0] * _JOINT_COUNT  # placeholder
#: Reward of every simulated step (test data, not a fact).
_STEP_REWARD = 0.0  # placeholder


class FakeClutteredPushGrasp:
    """A stand-in for ``ClutteredPushGrasp`` with the same public interface and no physics."""

    def __init__(self, robot=None, models=None, camera=None, vis=False):
        self.robot = robot
        self.models = models
        self.camera = camera
        self.vis = vis
        self.tick = 0  # placeholder
        self.closed = False
        self.box_opened = False
        self.btn_pressed = False
        self.box_closed = False
        self._positions = list(_START_POSITIONS)
        self._velocities = [0.0] * _JOINT_COUNT  # placeholder
        self._ee_pos = list(_START_EE)
        self._info = {"box_opened": False, "btn_pressed": False, "box_closed": False}

    def step(self, action, control_method="joint"):
        """Read the seven-element action and return one step result (``env.py:81-97``)."""
        assert control_method in ("joint", "end")
        values = list(action)
        if len(values) != 7:
            raise ValueError("action must hold seven values")
        if control_method == "end":
            # The end-effector target of the documented demo; no IK or physics is modelled.
            self._ee_pos = [float(values[0]), float(values[1]), float(values[2])]  # placeholder
        else:
            self._positions = [float(value) for value in values[:-1]]
        self.tick += 1  # placeholder
        return self.get_observation(), _STEP_REWARD, False, dict(self._info)

    def reset(self):
        """Restore the start state and return the observation (``env.py:131-134``)."""
        self.tick = 0  # placeholder
        self.box_opened = False
        self.btn_pressed = False
        self.box_closed = False
        self._positions = list(_START_POSITIONS)
        self._velocities = [0.0] * _JOINT_COUNT  # placeholder
        self._ee_pos = list(_START_EE)
        self._info = {"box_opened": False, "btn_pressed": False, "box_closed": False}
        return self.get_observation()

    def get_observation(self):
        """The robot observation dict of ``get_joint_obs`` (``robot.py:130-138``)."""
        return {
            "positions": list(self._positions),
            "velocities": list(self._velocities),
            "ee_pos": list(self._ee_pos),
        }

    def close(self):
        """Close the backend (``env.py:136-137``)."""
        self.closed = True
