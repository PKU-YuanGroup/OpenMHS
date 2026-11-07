"""ROS-free analytic fake for the Turtlebot4 Gymnasium environment.

The upstream ``tb4_drl_navigation.envs.diffdrive.turtlebot4:Turtlebot4Env``
creates ROS 2 nodes and talks to Gazebo in its constructor, so it cannot be
imported by the gate's isolated fake backend.  This fake reproduces only the
Gymnasium surface the bridge uses: the upstream action space, a matching
``Dict`` observation space, ``reset`` and ``step``.

No number below describes the real sensor or the real simulator.  The
observation vectors are analytic placeholders (marked ``# placeholder``).
The two-element action space is copied from the upstream environment
(``.../envs/diffdrive/turtlebot4.py:187-191``) so the bridge derives the same
bounds; it is cited by ``action_space_ref`` in driver.py.
"""

#: Number of lidar bins the fake reports.  Upstream's constructor defaults
#: ``num_bins`` to 30 (docs/Tutorial.md:42); the live length comes from /scan.
_BINS = 30  # placeholder: upstream constructor default, not a device fact


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: only the members the bridge reads."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: only the members the bridge reads."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeTurtlebot4Env:
    """Analytic stand-in for ``Turtlebot4Env``; it never imports ROS or Gazebo.

    The action space is the upstream one.  The observation space mirrors the
    upstream ``Dict`` structure, but ``min_ranges`` and ``min_ranges_angle``
    use fixed placeholder bounds and a fixed placeholder 30-bin length instead
    of the live ``LaserScan`` metadata.
    """

    def __init__(self, **_options):
        self.action_space = Box(
            low=[0.0, -1.0],                 # upstream turtlebot4.py:188
            high=[1.0, 1.0],                # upstream turtlebot4.py:189
            shape=(2,),
        )
        self.observation_space = Dict({
            "min_ranges": Box(
                low=[0.0] * _BINS,          # placeholder: real low is the scan range_min
                high=[12.0] * _BINS,        # placeholder: real high is the scan range_max
                shape=(_BINS,),
            ),
            "min_ranges_angle": Box(
                low=[-3.141592653589793] * _BINS,   # placeholder
                high=[3.141592653589793] * _BINS,   # placeholder
                shape=(_BINS,),
            ),
            # placeholder bounds copied from the upstream observation space
            "dist_to_goal": Box(low=[0.0], high=[100.0], shape=(1,)),  # placeholder; turtlebot4.py:226
            "orient_to_goal": Box(
                low=[-3.141592653589793], high=[3.141592653589793], shape=(1,)
            ),                                                  # placeholder; turtlebot4.py:227
            # upstream action bounds (the action-space exception, not a placeholder)
            "action": Box(low=[0.0, -1.0], high=[1.0, 1.0], shape=(2,)),
        })
        self._bins = _BINS
        self._seed = 0                       # placeholder
        self._tick = 0                       # placeholder
        self._last_action = [0.0, 0.0]        # placeholder
        self._distance = 5.0           # placeholder start distance
        self._goal_distance = 5.0      # placeholder goal distance

    def _observation(self):
        angles = [-3.141592653589793 + index * (2.0 * 3.141592653589793 / (self._bins - 1))
                  for index in range(self._bins)]           # placeholder
        return {
            "min_ranges": [self._distance] * self._bins,   # placeholder
            "min_ranges_angle": angles,                    # placeholder
            "dist_to_goal": [self._distance],              # placeholder
            "orient_to_goal": [0.0],                       # placeholder
            "action": list(self._last_action),
        }

    def reset(self, seed=None, options=None):
        self._seed = 0 if seed is None else int(seed)   # placeholder default seed
        self._tick = 0                                  # placeholder
        self._last_action = [0.0, 0.0]                   # placeholder
        # placeholder: a fixed distance selected by the seed, not a real scenario
        self._distance = self._goal_distance = 5.0 + float(self._seed % 5)
        options = options or {}
        # reset options are accepted for interface parity with the upstream
        # environment; the fake applies none of them.
        _ = options
        return self._observation(), {"distance_to_goal": self._distance}

    def step(self, action):
        self._last_action = [float(action[0]), float(action[1])]
        self._tick += 1
        # placeholder: no TurtleBot4 dynamics; move the placeholder distance a
        # fixed amount selected by the linear component and keep it non-negative.
        self._distance = max(0.0, self._distance - 0.1 * float(action[0]))  # placeholder decrement
        observation = self._observation()
        reward = 0.0                   # placeholder
        terminated = False             # placeholder: never reaches goal or collision
        truncated = False              # placeholder: no registered TimeLimit here
        info = {"distance_to_goal": self._distance}
        return observation, reward, terminated, truncated, info

    def close(self):
        return None
