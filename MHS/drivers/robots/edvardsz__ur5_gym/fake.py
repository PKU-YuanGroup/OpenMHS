"""Fake backend of the UR5 Reach driver: a Gazebo-free stand-in for the upstream task class.

Why a fake: the upstream environment is a legacy Gym environment whose entry point is
``gym_ignition.runtimes.gazebo_runtime:GazeboRuntime`` (``src/gym_ur5/__init__.py:10``).  It needs Ignition Gazebo,
gym-ignition and numpy, none of which is available where the gate runs, and package code never imports the clone.
``FakeReach`` therefore implements only the public methods of ``gym_ur5.tasks.reach:Reach`` (gate G7): the task
interface, not the Gazebo runtime.

What is modelled: the task's own command arithmetic -- ``set_action`` scales the action by 0.1 and clamps the result
to the workspace (``src/gym_ur5/tasks/reach.py:50-74``), the observation is the end-effector position followed by
the target position (``:76-81``), the reward is +1 when the distance is below 0.05 and -1 otherwise (``:83-90``),
and the info is ``is_success`` (``:92-98``).  What is not modelled: the Gazebo rigid-body dynamics, the inverse
kinematics call, the joint controllers, the RedPoint/table assets and their Fuel downloads, rendering, and the
randomizer that draws the target from numpy's global generator.  The start position and target below are placeholder
test data, not device facts; every workspace constant and rule is cited to the clone at the pinned commit.

Nothing here talks to a device or imports the clone.
"""

# src/gym_ur5/tasks/reach.py:31-32 (Reach.__init__)
WORKSPACE_CENTRE = (0.50143738, 0.15, 1.36)
WORKSPACE_VOLUME = (0.4, 0.4, 0.4)
# src/gym_ur5/tasks/reach.py:55 (set_action: ee_position + action * 0.1)
ACTION_SCALE = 0.1
# src/gym_ur5/tasks/reach.py:86 and :94 (the reward and info success distance)
SUCCESS_DISTANCE = 0.05

# placeholder: the fake has no Gazebo/IK state, so it starts at the workspace centre and puts the target 0.2 m
# further along x (half the workspace volume), which is inside the workspace of reach.py:59-63.
START = list(WORKSPACE_CENTRE)
TARGET = [WORKSPACE_CENTRE[0] + 0.2, WORKSPACE_CENTRE[1], WORKSPACE_CENTRE[2]]


class FakeReach:
    """The task object: the same public methods as ``gym_ur5.tasks.reach:Reach`` without Gazebo."""

    def __init__(self, **_options):
        self._is_done = False
        self._ee = list(START)                  # placeholder
        self._target = list(TARGET)             # placeholder

    def reset_task(self):
        """Reach.reset_task (reach.py:103-111): clear done and return to the start configuration."""
        self._is_done = False
        self._ee = list(START)                  # placeholder
        return None

    def set_action(self, action):
        """Reach.set_action (reach.py:50-74): displace the end effector and clamp it to the workspace."""
        ee_position = self.get_ee_position()
        target_pos = [ee_position[0] + float(action[0]) * ACTION_SCALE,
                      ee_position[1] + float(action[1]) * ACTION_SCALE,
                      ee_position[2] + float(action[2]) * ACTION_SCALE]
        for index in range(3):
            target_pos[index] = min(self._workspace_limit(index, 1.0),
                                    max(self._workspace_limit(index, -1.0), target_pos[index]))
        self._ee = target_pos
        return None

    def _workspace_limit(self, index, side):
        """The clamp bound of reach.py:60-62 (a private helper, not an upstream method)."""
        return WORKSPACE_CENTRE[index] + side * WORKSPACE_VOLUME[index] / 2.0

    def get_observation(self):
        """Reach.get_observation (reach.py:76-81): end-effector position followed by target position."""
        return self.get_ee_position() + self.get_target_position()

    def get_reward(self):
        """Reach.get_reward (reach.py:83-90)."""
        return 1.0 if self.get_distance_to_target() < SUCCESS_DISTANCE else -1.0

    def get_info(self):
        """Reach.get_info (reach.py:92-98)."""
        distance = self.get_distance_to_target()
        return {"is_success": False if distance > SUCCESS_DISTANCE else True}

    def is_done(self):
        """Reach.is_done (reach.py:99-101)."""
        return self._is_done

    def get_distance_to_target(self):
        """Reach.get_distance_to_target (reach.py:140-148): Euclidean end-effector to target distance."""
        ee_position = self.get_ee_position()
        target_position = self.get_target_position()
        return sum((ee_position[index] - target_position[index]) ** 2 for index in range(3)) ** 0.5

    def get_target_position(self):
        """Reach.get_target_position (reach.py:163-165): the RedPoint model's base position."""
        return list(self._target)               # placeholder

    def get_ee_position(self):
        """Reach.get_ee_position (reach.py:173-175): the tool0 link's position."""
        return list(self._ee)                   # placeholder
