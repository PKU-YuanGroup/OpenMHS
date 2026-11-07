"""Fake backend of the robo-gym driver: an in-memory stand-in for ``robo_gym.envs:ExampleEnvSim``.

Why a fake: the clone is only the Gymnasium environment layer.  ``ExampleEnvSim`` launches an external
``example_robot_server`` with roslaunch (example_env.py:228) and every reset and step talks to it over gRPC
(example_env.py:89-99 and :128-133); the server side is a separate repository (README.md:102-103) and package code
never imports or runs the clone.  The gate therefore runs this fake, which keeps the environment's public surface
(``reset``, ``step``, ``close``; gate G7), its two spaces (example_env.py:211-214 and :224), the reset option
``position`` (example_env.py:67-73) and the 300-step episode limit (example_env.py:25 and :109-117).

What this is not: the upstream environment or Gazebo.  It has no robot, no physics and no contact model.  The
transition below is a placeholder kinematics; the numbers are test data (each marked ``# placeholder``), not facts of
the upstream environment.  The state layout [pos_x, pos_y, lin_vel, ang_vel] is the one the clone documents at
example_env.py:192-198; the values the external server would report are unknown here.
"""

# One fake step advances the placeholder positions by this many seconds; the upstream robot server decides its own
# control period, which the clone does not declare.
STEP_S = 0.05  # placeholder
# example_env.py:25 (ExampleEnv.max_episode_steps)
MAX_EPISODE_STEPS = 300
# example_env.py:211-214: four unbounded observation elements
OBSERVATION_SIZE = 4
# example_env.py:224: two action elements, each from -1.0 to 1.0
ACTION_SIZE = 2
ACTION_LOW = -1.0
ACTION_HIGH = 1.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        try:
            numbers = [float(item) for item in value]
        except (TypeError, ValueError):
            return False
        return all(low <= number <= high for low, number, high in zip(self.low, numbers, self.high))


class FakeExampleEnv:
    """The environment layer without the robot server: the same spaces, options and step limit."""

    real_robot = False
    max_episode_steps = MAX_EPISODE_STEPS

    def __init__(self, rs_address=None, rs_state_to_info=True, **kwargs):
        # The upstream constructor accepts rs_address and rs_state_to_info (example_env.py:27); the fake needs no
        # server address and keeps the flag for signature compatibility.
        self.rs_address = rs_address
        self.rs_state_to_info = rs_state_to_info
        self.observation_space = Box([float("-inf")] * OBSERVATION_SIZE,
                                     [float("inf")] * OBSERVATION_SIZE)
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE)
        self.elapsed_steps = 0
        self.rs_state = None
        self._state = [0.0] * OBSERVATION_SIZE  # placeholder
        self._closed = False

    def reset(self, *, seed=None, options=None):
        # example_env.py:64-75: seed goes to the parent environment, options.position is the starting [x, y].
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise ValueError("seed must be a non-negative integer")
        options = {} if options is None else options
        position = options["position"] if "position" in options else None
        if position:
            assert len(position) == 2
        else:
            position = [0, 0]
        self.elapsed_steps = 0
        # placeholder: the external server returns the state; the fake starts at rest at the requested position.
        self._state = [float(position[0]), float(position[1]), 0.0, 0.0]
        self.rs_state = {"pos_x": self._state[0], "pos_y": self._state[1], "lin_vel": 0.0, "ang_vel": 0.0}
        return list(self._state), {}

    def step(self, action):
        if isinstance(action, tuple):
            action = list(action)
        self.elapsed_steps += 1
        if not self.action_space.contains(action):
            raise ValueError(f"{action!r} is not contained in the action space")
        # placeholder kinematics: the two action elements are velocity commands held for STEP_S seconds.
        x, y, _lin_vel, _ang_vel = self._state
        lin_vel, ang_vel = float(action[0]), float(action[1])
        self._state = [x + lin_vel * STEP_S, y + ang_vel * STEP_S, lin_vel, ang_vel]
        self.rs_state = {"pos_x": self._state[0], "pos_y": self._state[1],
                         "lin_vel": lin_vel, "ang_vel": ang_vel}
        # example_env.py:109-117: the example reward is 0 and done is set at the step limit.
        done = self.elapsed_steps >= self.max_episode_steps
        info = {"final_status": "max_steps_exceeded"} if done else {}
        if self.rs_state_to_info:
            info["rs_state"] = dict(self.rs_state)
        return list(self._state), 0, done, False, info

    def close(self):
        # simulation_wrapper.py:89-108: closing stops the simulated server when one is running; the fake has none.
        self._closed = True
