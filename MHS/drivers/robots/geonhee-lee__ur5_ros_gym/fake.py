"""Pure-Python fake backend for the legacy Gym ``UnscrewingEnv``.

The upstream environment is ``rl_gym.envs:UnscrewingEnv``
(``rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py:14``).  Its constructor calls
``rospy.init_node`` and creates the ``/action_move`` publisher and the
``/reset_robot`` service proxy, ``step`` waits on ``/curr_pose`` and publishes the
action, and ``reset`` calls the service.  None of that can run where the gate
runs, so this module preserves the public legacy-Gym surface the bridge uses
(``action_space``, ``reset()`` and ``step(action)``) with a small analytic
stand-in.

What this models from the upstream code: the ``spaces.Discrete(7)`` action space
(:39), the pose boundaries (:36), the action-to-pose increments of the MoveIt
subscriber (``planning_script.py:37`` and :54-76), the -0.25 rad screw step of
``screw_control.py:37`` and :55-57, the discretisation rule (:151-168), the
terminal rule (``force_z < -10`` or the previous pose out of bounds, :227-244)
and the reward rules (:93-113).

What this is not: ROS, Gazebo, MoveIt, the UR5 model, contact physics, the force
sensor or the real scene.  The start pose, force values and screw-joint value are
placeholders; the force counter stands in for the FT sensor.  Every number in
this file is test data, marked ``# placeholder``, and none of it is a fact, a
limit or a source reference.
"""

import math

# placeholder: a pose inside the upstream boundaries (rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py:36)
START_X = 0.5000
START_Y = 0.0000
START_Z = 0.0300
# placeholder: the upstream MoveIt pose subscriber step (planning_script.py:37)
POSE_STEP = 0.0005
# placeholder: the upstream screw-controller step on the first tool joint (screw_control.py:37)
SCREW_STEP = -0.25
# placeholder: force change per unscrewing action; the real value comes from /FTsensor_topic
FORCE_STEP = -0.5
# placeholder: the force threshold of the upstream terminal rule (unscrewing_env.py:240)
FORCE_LIMIT = -10.0
# placeholder: the z height below which the upstream sets screw_touch_state (unscrewing_env.py:94)
TOUCH_Z = 0.0295
# placeholder: the upstream out-of-bounds margin (unscrewing_env.py:129-145)
BOUNDARY_MARGIN = 0.0001


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: ``n``, ``start``, ``shape`` and ``dtype``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and self.start <= value < self.start + self.n


class FakeUr5RosGym:
    """The legacy-Gym surface of ``UnscrewingEnv`` without ROS, Gazebo or MoveIt."""

    def __init__(self, **_options):
        self.action_space = Discrete(7)            # placeholder: the upstream spaces.Discrete(7) (:39)
        self.reward_range = (-math.inf, math.inf)  # upstream :40
        # placeholder: the upstream boundary dictionary (:36)
        self.boundaries = {
            "x_low": 0.478915,
            "x_high": 0.521085,
            "y_low": -0.021225,
            "y_high": 0.021225,
            "z_low": 0.02,
            "z_high": 0.04,
        }
        self.screw_touch_state = False
        self._pose = [START_X, START_Y, START_Z]
        self._force_z = 0.0
        self._screw_joint = 0.0

    def reset(self):
        """Clear the episode state and return the initial discretised observation."""
        self.screw_touch_state = False
        self._pose = [START_X, START_Y, START_Z]
        self._force_z = 0.0
        self._screw_joint = 0.0
        return self._state()

    def step(self, action):
        """Apply one Discrete action and return the legacy ``(state, reward, done, {})`` tuple."""
        previous = list(self._pose)
        index = int(action)
        if index == 0:
            self._pose[0] += POSE_STEP
        elif index == 1:
            self._pose[0] -= POSE_STEP
        elif index == 2:
            self._pose[1] += POSE_STEP
        elif index == 3:
            self._pose[1] -= POSE_STEP
        elif index == 4:
            self._pose[2] += POSE_STEP
        elif index == 5:
            self._pose[2] -= POSE_STEP
        elif index == 6:
            self._screw_joint += SCREW_STEP
            self._force_z += FORCE_STEP
        else:
            # the upstream MoveIt callback has no branch for another value; the bridge refuses it first
            pass
        state = self._state()
        done = self._is_done(state, previous)
        if not done:
            if state["z"] < TOUCH_Z:
                self.screw_touch_state = True
            if state["force_z"] < 0 and index == 6:
                reward = 2
            else:
                reward = 0
        else:
            if self._out_of_bounds(previous):
                reward = -10
            elif self.screw_touch_state:
                reward = 30 + 3000 * state["z"]
            else:
                reward = 10 + 1.5 / state["z"]
        return state, reward, done, {}

    def _state(self):
        """The discretisation of ``discretise_data`` (unscrewing_env.py:151-168)."""
        return {
            "x": round(self._pose[0], 4),
            "y": round(self._pose[1], 4),
            "z": round(self._pose[2], 4),
            "force_z": round(self._force_z, 1),
            "screw_joint_value": round(self._screw_joint, 3),
        }

    def _out_of_bounds(self, pose):
        """The comparison of ``out_of_bounds`` (unscrewing_env.py:119-148), on a plain pose list."""
        limits = self.boundaries
        if pose[0] > limits["x_high"] - BOUNDARY_MARGIN:
            return True
        if pose[0] < limits["x_low"] + BOUNDARY_MARGIN:
            return True
        if pose[1] > limits["y_high"] - BOUNDARY_MARGIN:
            return True
        if pose[1] < limits["y_low"] + BOUNDARY_MARGIN:
            return True
        if pose[2] > limits["z_high"] - BOUNDARY_MARGIN:
            return True
        if pose[2] < limits["z_low"] + BOUNDARY_MARGIN:
            return True
        return False

    def _is_done(self, state, previous):
        """``is_done`` (unscrewing_env.py:227-244) with the upstream previous-pose lag."""
        if state["force_z"] < FORCE_LIMIT:
            return True
        return self._out_of_bounds(previous)
