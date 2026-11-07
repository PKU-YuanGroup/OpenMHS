"""Fake backend of the HoME driver: a pure Python stand-in for ``home_platform.gym.envs:HomeEnv``.

Why a fake: the upstream package is Python 2 code that imports ``Tkinter``, Panda3D and the SUNCG data loader
(``home_platform/gym/envs/home_env_basic.py:5-10``), none of which is available where the gate runs, and package code
never imports the clone.  This module re-implements the parts of ``HomeEnv`` that the Gymnasium bridge uses: the
documented two-component action (moving and looking, each 0-4), the fixed reset pose, the orientation updates of
``executeLooking`` and a kinematic stand-in for the Bullet impulse of ``executeMoving``.  The public names are the
legacy ``gym.Env`` methods (``reset`` and ``step``) that ``HomeEnv`` inherits from its external base, plus the two
``execute*`` helpers it defines itself; gate G7 reads the upstream class and the clone for every one of them.

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the agent is moved directly (impulse / mass * dt) on the horizontal plane: no Bullet contacts, friction, gravity or
  collision detection, so the collision flag is always 0 and the image is a small constant placeholder;
* the image is 4 x 4 x 3 values, not the upstream 500 x 500 x 3 (``home_env_basic.py:57``);
* the 1000-step TimeLimit that ``gym.make("Home-v0")`` adds from the registration
  (``home_platform/gym/__init__.py:6``) is not modelled: ``done`` is always False, as in ``HomeEnv._step``;
* the upstream package was never imported or run, so the fake was not compared with it.

Every constant below is either copied from a cited upstream line or a placeholder of this kinematic stand-in; none is
a fact about a physical device.  Nothing here talks to a device.
"""

# home_platform/gym/envs/home_env_basic.py:68 -- the clone ships one house id; a seed is a house index.
HOUSE_IDS = ["0004d52d1aeeb8ae6de39d6bd993e992"]
# home_platform/gym/envs/home_env_basic.py:156-157 -- fixed pose set on every reset.
START_POSITION = (42.0, -39.0, 1.0)              # placeholder: upstream reset pose
START_ORIENTATION = (0.0, 0.0, 0.0)              # placeholder: upstream reset pose
# home_platform/gym/envs/home_env_basic.py:34 -- constructor defaults.
TURNING_SPEED = 0.1
MOVING_SPEED = 100.0
# home_platform/env.py:93 -- BasicEnvironment's default integration interval.
TIMESTEP_S = 0.1
# home_platform/env.py:107 -- agentMass of the Bullet capsule.
AGENT_MASS = 60.0
# placeholder: a smaller image than the upstream 500 x 500 x 3 (home_env_basic.py:57).
IMAGE_SHAPE = (4, 4, 3)


class MultiDiscrete:
    """Duck-typed ``gym.spaces.MultiDiscrete``: ``nvec`` says how many values each component has."""

    def __init__(self, nvec):
        self.nvec = [int(value) for value in nvec]
        self.low = [0 for _ in self.nvec]
        self.high = [value - 1 for value in self.nvec]
        self.shape = (len(self.nvec),)
        self.dtype = "int64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.nvec):
            return False
        for item, size in zip(value, self.nvec):
            if isinstance(item, bool) or not isinstance(item, int) or not 0 <= item < size:
                return False
        return True


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = "float32"


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping of name to sub-space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeHomeEnv:
    """``HomeEnv`` without Panda3D: ``reset(seed, options)`` and ``step(action)`` over the documented action."""

    def __init__(self, turning_speed=TURNING_SPEED, moving_speed=MOVING_SPEED):
        self.turning_speed = turning_speed
        self.moving_speed = moving_speed
        self.metadata = {"render.modes": ["human", "rgb_array"]}   # home_env_basic.py:38
        # The class documents two components, moving and looking, each 0-4 (home_env_basic.py:17-30).  The upstream
        # constructor passes spaces.MultiDiscrete([[0, 4], [0, 4]]) (home_env_basic.py:47), which is not the
        # documented shape; this fake implements the documented two 0-4 components.
        self.action_space = MultiDiscrete([5, 5])
        self.observation_space = Dict({
            "position": Box([-100, -100, -100], [100, 100, 100], (3,)),          # home_env_basic.py:51
            "orientation": Box([-100, -100, -100], [100, 100, 100], (3,)),       # home_env_basic.py:55
            "image": Box(0, 255, IMAGE_SHAPE),                                   # home_env_basic.py:57
            "collision": Discrete(2),                                            # home_env_basic.py:60
        })
        self.list_of_houses = list(HOUSE_IDS)                                # home_env_basic.py:68
        self.next_house = 0                                                  # home_env_basic.py:73
        self.render_window = None                                            # home_env_basic.py:75
        self._reset()                                                        # home_env_basic.py:77

    # -- observation -----------------------------------------------------------
    def _observe(self):
        pixels = IMAGE_SHAPE[0] * IMAGE_SHAPE[1] * IMAGE_SHAPE[2]
        return {
            "position": [float(value) for value in self.position],
            "orientation": [float(value) for value in self.orientation],
            "image": [0] * pixels,                                          # placeholder: constant frame
            "collision": 0,                                                 # placeholder: no collision model
        }

    # -- old gym surface -------------------------------------------------------
    def reset(self, seed=None, options=None):
        """Reset to the fixed pose; a seed selects the house index (``HomeEnv._seed``)."""
        if options:                                                          # HomeEnv._reset takes no options
            raise ValueError("HomeEnv reset does not accept options")
        if seed is not None:
            self._seed(seed)
        return self._reset()

    def step(self, action):
        """Apply moving and looking, advance one 100 ms tick, and return the legacy 4-tuple."""
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} is not in {self.action_space.nvec!r}")
        self.executeMoving(action[0])
        self.executeLooking(action[1])
        self._advance()
        self.tick += 1
        self.observation = self._observe()
        return self.observation, 0, False, None

    # -- upstream helpers ------------------------------------------------------
    def executeLooking(self, action):
        new_orientation = list(self.orientation)
        if action == 0:
            pass                                                        # NOOP
        elif action == 1:
            new_orientation[0] -= self.turning_speed                    # home_env_basic.py:97
        elif action == 2:
            new_orientation[2] += self.turning_speed                    # home_env_basic.py:99
        elif action == 3:
            new_orientation[0] += self.turning_speed                    # home_env_basic.py:101
        elif action == 4:
            new_orientation[2] -= self.turning_speed                    # home_env_basic.py:103
        else:
            raise ValueError(f"unknown looking action {action!r}")
        self.orientation = new_orientation

    def executeMoving(self, action):
        new_impulse = [0.0, 0.0, 0.0]                                   # home_env_basic.py:111
        if action == 0:
            pass                                                        # NOOP
        elif action == 1:
            new_impulse[1] += self.moving_speed                         # home_env_basic.py:116
        elif action == 2:
            new_impulse[0] += self.moving_speed                         # home_env_basic.py:118
        elif action == 3:
            new_impulse[1] -= self.moving_speed                         # home_env_basic.py:120
        elif action == 4:
            new_impulse[0] -= self.moving_speed                         # home_env_basic.py:122
        else:
            raise ValueError(f"unknown moving action {action!r}")
        # placeholder: kinematic stand-in for Bullet -- velocity = impulse / agentMass, one tick per call
        self.velocity = [component / AGENT_MASS for component in new_impulse]

    # -- private legacy methods ------------------------------------------------
    def _advance(self):
        for axis in (0, 1):
            self.position[axis] += self.velocity[axis] * TIMESTEP_S
        self.position[2] = START_POSITION[2]

    def _seed(self, seed=0):
        # placeholder: upstream asserts seed < len(list_of_houses) (home_env_basic.py:85); with the one house the
        # clone ships, this fake maps any non-negative seed to that house so the generic cap.world.* contract stays
        # usable.  See the fidelity gap in driver.py.
        self.next_house = int(seed) % len(self.list_of_houses)
        return [self.next_house]

    def _reset(self):
        self.house_id = self.list_of_houses[self.next_house]            # home_env_basic.py:152
        self.position = list(START_POSITION)                            # home_env_basic.py:156
        self.orientation = list(START_ORIENTATION)                      # home_env_basic.py:157
        self.velocity = [0.0, 0.0, 0.0]
        self.tick = 0
        self.observation = self._observe()                              # home_env_basic.py:160
        self.next_house += 1                                            # home_env_basic.py:162
        if self.next_house == len(self.list_of_houses):                 # home_env_basic.py:165
            self.next_house = 0                                         # home_env_basic.py:166
        return self.observation
