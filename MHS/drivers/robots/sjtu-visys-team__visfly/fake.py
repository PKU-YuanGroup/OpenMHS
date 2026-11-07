"""Fake backend of the VisFly driver: a pure Python stand-in for one ``NavigationEnv`` world.

Why a fake: the upstream environment imports ``habitat_sim``, ``torch`` and the clone's own modules
(``envs/NavigationEnv.py:1-13``), and package code never imports or runs the clone, so the acceptance gate cannot open
the Habitat-Sim world.  This module mirrors the public surface of ``envs.NavigationEnv:NavigationEnv`` that the gate
checks (``reset``, ``step`` and ``close``; G7) and the two spaces the bridge reads (a four-element ``Box`` action and a
``Dict`` observation with ``state`` and ``target``).  The reset and step signatures follow the upstream stable-baselines3
``VecEnv`` wrapper: ``reset(state=None, ...)`` returns one observation mapping and ``step(_action, ...)`` returns
``(observation, reward, done, info)`` (``envs/base/droneGymEnv.py:141`` and ``:302``).  The driver's
``_NavigationGymAdapter`` translates that interface to the Gymnasium contract the bridge serves.

The start position, the action-to-motion mapping and the reward below are test data, marked ``# placeholder``: they are
not facts, limits or evidence, and they do not reproduce the upstream bodyrate dynamics or the Habitat-Sim scene.

What this is not: the upstream simulator.  Differences, all listed in the fidelity ``gaps`` of the driver:

* kinematic point model: the four commands are mapped directly to a velocity vector; there is no motor, drag, contact,
  wind, sensor-noise or scene model and no rendered depth image;
* the start state comes from Python's ``random.Random(seed)``, while upstream draws it from a torch state generator,
  so one seed does not give the same trajectory on the two;
* observations are plain lists (state 13, target 3), upstream returns a batched ``TensorDict`` of torch tensors and,
  with ``visual=True``, also a depth sensor array (``envs/NavigationEnv.py:69-74``);
* the reward is a placeholder distance term, not the upstream navigation reward (``envs/NavigationEnv.py:85-99``).

Nothing here talks to a device.
"""

import math
import random

#: The upstream control interval (``envs/base/dynamics.py:33``); the fake uses it as its test clock.
CTRL_DT = 0.03                                  # placeholder: test clock aligned with the upstream ctrl_dt
#: Default episode length (``envs/NavigationEnv.py:41``).
MAX_EPISODE_STEPS = 256                         # placeholder: test limit aligned with the upstream default
#: The success radius and the default target (``envs/NavigationEnv.py:61`` and ``:58``).
SUCCESS_RADIUS = 0.5                            # placeholder: test geometry
DEFAULT_TARGET = [9.0, 0.0, 1.0]                # placeholder: test geometry
START_POSITION = [0.0, 0.0, 1.0]                # placeholder: test start
IDENTITY_QUATERNION = [1.0, 0.0, 0.0, 0.0]      # placeholder: test start
START_JITTER = 0.1                              # placeholder: test geometry
MAX_SPEED = 1.0                                 # placeholder: test motion mapping
MAX_RATE = 1.0                                  # placeholder: test motion mapping


def _shape(value):
    """The nested shape of a list, so the space objects can report ``shape`` without numpy."""
    shape = []
    item = value
    while isinstance(item, (list, tuple)):
        shape.append(len(item))
        item = item[0] if item else None
    return tuple(shape)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = _shape(self.low)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class _FakeEnvs:
    """Stand-in for the ``DroneEnvsBase`` object a NavigationEnv holds as ``self.envs``.

    The driver adapter applies a reset seed through ``envs.set_seed`` because that is the method the upstream base
    object exposes (``envs/base/droneEnv.py:381-385``); on the fake it reseeds the start-state generator.
    """

    def __init__(self, env):
        self._env = env

    def set_seed(self, seed):
        self._env._set_seed(seed)


class FakeNavigationEnv:
    """One VisFly ``NavigationEnv`` world without Habitat-Sim, torch or the clone.

    ``reset`` and ``step`` keep the upstream return shapes; the driver adapter converts them for the bridge.  The
    public members are exactly the ones the upstream class (and its base) has that the adapter uses.
    """

    def __init__(
            self,
            num_agent_per_scene=1,
            num_scene=1,
            seed=42,
            visual=True,
            requires_grad=False,
            random_kwargs=None,
            dynamics_kwargs=None,
            scene_kwargs=None,
            sensor_kwargs=None,
            device="cpu",
            target=None,
            max_episode_steps=256,
    ):
        # The upstream constructor (envs/NavigationEnv.py:28-42); the fake keeps the arguments so the factory call
        # shape is the same, and ignores the ones it does not model.
        self.num_agent = int(num_agent_per_scene) * int(num_scene)
        self.num_envs = self.num_agent
        self.visual = bool(visual)
        self.max_episode_steps = int(max_episode_steps)
        self.success_radius = SUCCESS_RADIUS
        self.target = list(DEFAULT_TARGET if target is None else target)
        # envs/base/droneGymEnv.py:108-116: a four-element Box from -1 to 1 for the bodyrate command.
        self.action_space = Box([-1.0, -1.0, -1.0, -1.0], [1.0, 1.0, 1.0, 1.0])   # placeholder
        # envs/base/droneGymEnv.py:76-80 and envs/NavigationEnv.py:59: state (13) and target (3).
        self.observation_space = Dict({
            "state": Box([-math.inf] * 13, [math.inf] * 13),                      # placeholder: unbounded
            "target": Box([-math.inf] * 3, [math.inf] * 3),                       # placeholder: unbounded
        })
        self.envs = _FakeEnvs(self)
        self._rng = random.Random(seed)                 # placeholder: test seed
        self._state = None
        self._is_initial = False
        self._step_count = 0

    # -- the members the upstream class has (G7) ---------------------------------
    def reset(self, state=None, predicted_obs=None, is_test=False, stoch=None, deter=None):
        """Start an episode and return one observation mapping, as ``DroneGymEnvsBase.reset`` does (:302-326)."""
        if state is not None:
            self._state = self._state_from(state)
        else:
            position = [START_POSITION[axis] + self._rng.uniform(-START_JITTER, START_JITTER)
                        for axis in range(3)]                                  # placeholder
            self._state = position + list(IDENTITY_QUATERNION) + [0.0] * 6    # placeholder
        self._is_initial = True
        self._step_count = 0
        return self._observation()

    def step(self, _action, is_test=False, predict=False, world=None):
        """Advance one control tick and return ``(observation, reward, done, info)`` (:141-229)."""
        if not self._is_initial:
            raise AssertionError("You should call reset() before step()")
        values = self._action_row(_action)
        if len(values) != 4 or any(value < -1.0 or value > 1.0 for value in values):
            raise AssertionError(f"action {values!r} is outside the four-element Box [-1, 1]")
        position = self._state[0:3]
        # Placeholder kinematics: the four commands are mapped to a velocity vector.  This is not the upstream
        # bodyrate dynamics; it only makes every accepted command change the observable state.
        velocity = [values[0] * MAX_SPEED, values[1] * MAX_SPEED, values[2] * MAX_SPEED]   # placeholder
        angular_velocity = [0.0, 0.0, values[3] * MAX_RATE]                                # placeholder
        position = [position[axis] + velocity[axis] * CTRL_DT for axis in range(3)]        # placeholder
        self._state = position + IDENTITY_QUATERNION + velocity + angular_velocity         # placeholder
        self._step_count += 1
        distance = math.sqrt(sum((position[axis] - self.target[axis]) ** 2 for axis in range(3)))  # placeholder
        success = distance <= self.success_radius
        truncated = self._step_count >= self.max_episode_steps
        reward = -distance + (1.0 if success else 0.0)                                    # placeholder
        info = {
            "episode_done": bool(success or truncated),
            "is_success": bool(success),
            "TimeLimit.truncated": bool(truncated and not success),
        }
        return self._observation(), reward, bool(success or truncated), [info]

    def close(self):
        """Release the state; the upstream base closes its dynamics and scene manager (``droneGymEnv.py:471-472``)."""
        self._state = None
        self._is_initial = False

    # -- helpers (private: G7 reads only public members) --------------------------
    def _set_seed(self, seed):
        self._rng = random.Random(int(seed))

    def _observation(self):
        return {"state": list(self._state), "target": list(self.target)}

    @staticmethod
    def _action_row(action):
        """The single row of the batched ``(num_agent, 4)`` action the upstream step receives (:122 and :143)."""
        if isinstance(action, (list, tuple)) and len(action) == 1 and isinstance(action[0], (list, tuple)):
            action = action[0]
        return [float(value) for value in action]

    @staticmethod
    def _state_from(state):
        """A 13-value state from the four-part reset state the upstream accepts (``droneEnv.py:270-276``)."""
        if not isinstance(state, (list, tuple)) or len(state) < 4:
            raise ValueError("state must be [position, orientation, velocity, angular_velocity]")
        position, orientation, velocity, angular_velocity = state[:4]
        if (len(position), len(orientation), len(velocity), len(angular_velocity)) != (3, 4, 3, 3):
            raise ValueError("state parts must have lengths 3, 4, 3 and 3")
        return ([float(value) for value in position] + [float(value) for value in orientation]
                + [float(value) for value in velocity] + [float(value) for value in angular_velocity])
