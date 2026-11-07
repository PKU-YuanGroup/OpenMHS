"""Fake backend of the Panda reach driver: an F0 stand-in for the upstream Gazebo environment.

Why a fake: the gate runs without ROS, Gazebo, MoveIt, ``gymnasium_robotics`` or the catkin workspace, and package
code never imports the clone.  The fake therefore reproduces the *interface and task* of
``ros_gazebo_gym.task_envs.panda.panda_reach:PandaReachEnv`` as configured by the shipped
``task_envs/panda/config/panda_reach.yaml``: a ``Box(7)`` effort action space, a ``Dict`` observation of
``observation``/``desired_goal``/``achieved_goal``, the dense distance reward, goal-reaching termination after
``hold_samples`` consecutive samples and the 500-step time limit that ``gymnasium.make("PandaReach-v1")`` adds.

Like the live backend, the fake runs in the isolated simulator host process (``process_by_backend["fake"]`` in
driver.py, ``mhs.bridge.sim_host``): the gate drives it through the same host, stop and read-back as the live
environment.  It models the pause state that the stop and the read-back act on: ``gazebo`` stands for the upstream
``GazeboConnection`` (``robot_gazebo_goal_env.py:83``) with the ``pause_proxy`` service proxy of
``/gazebo/pause_physics`` (``core/gazebo_connection.py:143``) and ``get_physics_properties()``, whose ``pause``
field the read-back compares (``core/gazebo_connection.py:562-580``).  As upstream, construction ends with the world
running (``robot_gazebo_goal_env.py:125-128``), every step unpauses it first (``:158``) and, with the shipped
``pause_after_step``, pauses it after the step (``:161-162``), and a reset ends paused (``:222-223``).

What this is not: the upstream environment.  There is no arm, no Gazebo, no contact model and no controller.  The
fake keeps a 3-D end-effector position and moves it by a placeholder linear map of the first three effort components;
all differences are listed in the driver's fidelity ``gaps``.  The action-space numbers are the shipped configuration
(the fake copies the upstream space, so ``action_space_ref`` in driver.py cites them), the reward/termination numbers
are the shipped configuration, and every invented constant is marked ``# placeholder``.

The public members are the ones the upstream class has through its bases (``reset``, ``step``, ``close``; gate G7).
The two space classes duck-type ``gymnasium.spaces.Dict`` and ``Box`` (the host describes ``spaces``, ``low``,
``high``, ``shape`` and ``dtype`` to the endpoint).  Two constructor switches exist only for the package tests:
``stop_ignored`` makes ``pause_proxy`` acknowledge without pausing (a simulator that does not stop) and
``step_delay_s`` makes a step take that long (a step in flight at the e-stop).
"""

import math
import random
import time

# Shipped effort bounds: src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:209-227.
# The shipped panda_reach.yaml loads no gripper (line 10) and lists seven controlled joints (lines 23-33), so the
# deployed action space contains these seven arm-effort bounds and no gripper bound.
EFFORT_LOW = [-87.0, -87.0, -87.0, -87.0, -12.0, -12.0, -12.0]
EFFORT_HIGH = [87.0, 87.0, 87.0, 87.0, 12.0, 12.0, 12.0]

# Target/initial sampling bounds of the shipped config: panda_reach.yaml:97-103 and 140-146.
SPACE_LOW = [0.1, -0.4, 0.1]
SPACE_HIGH = [0.8, 0.4, 1.0]

# Shipped training settings: panda_reach.yaml:159-162.
DISTANCE_THRESHOLD = 0.05
HOLD_SAMPLES = 2

# Shipped environment setting: panda_reach.yaml:169 (pause_after_step: True), passed on as pause_simulation
# (robot_envs/panda_env.py:342-344).
PAUSE_AFTER_STEP = True

# gymnasium.make("PandaReach-v1") adds a TimeLimit of max_episode_steps:
# src/ros_gazebo_gym/task_envs/task_envs_list.py:21-24.
MAX_EPISODE_STEPS = 500

# placeholder: this fake has no arm dynamics; it moves the end effector by this many metres per effort unit.
# A positive value means the first three action components push the end effector along +x, +y and +z.
EFFORT_TO_METRES = 0.02


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the host reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the host reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()


class FakePhysicsProperties:
    """The fields of the ``gazebo_msgs/GetPhysicsProperties`` response the read-back uses (``pause``, ``success``)."""

    def __init__(self, pause):
        self.pause = pause
        self.success = True
        self.status_message = "GetPhysicsProperties: got properties"


class FakeGazeboConnection:
    """The pause surface of ``ros_gazebo_gym.core.gazebo_connection.GazeboConnection`` (no ROS, no Gazebo).

    ``pause_proxy`` stands for the ``rospy.ServiceProxy`` of ``/gazebo/pause_physics`` (std_srvs/Empty,
    gazebo_connection.py:50, 143), ``unpause_proxy`` for ``/gazebo/unpause_physics`` (:51, 155);
    ``pause_sim``/``unpause_sim`` call them (:328-386, without the retry loop); ``get_physics_properties`` returns
    the ``/gazebo/get_physics_properties`` response (:562-580, 805-808).
    """

    def __init__(self, stop_ignored=False):
        self._paused = True        # GazeboConnection's constructor ends paused (gazebo_connection.py:321-324)
        self._stop_ignored = bool(stop_ignored)
        self.pauses = 0

    def pause_proxy(self):
        self.pauses += 1
        if not self._stop_ignored:
            self._paused = True

    def unpause_proxy(self):
        self._paused = False

    def pause_sim(self):
        self.pause_proxy()

    def unpause_sim(self):
        self.unpause_proxy()

    def get_physics_properties(self):
        return FakePhysicsProperties(self._paused)


class FakePandaReachEnv:
    """The Panda reach task without ROS: ``reset(seed, options)`` and ``step(action)`` as the upstream env has them."""

    def __init__(self, control_type="effort", stop_ignored=False, step_delay_s=0.0, **_options):
        if control_type != "effort":
            raise ValueError("the fake models the shipped effort action space only")
        self.action_space = Box(EFFORT_LOW, EFFORT_HIGH, shape=(len(EFFORT_LOW),))
        unbounded_low = [-math.inf] * 3
        unbounded_high = [math.inf] * 3
        self.observation_space = Dict({
            "observation": Box(unbounded_low, unbounded_high, shape=(3,)),
            "desired_goal": Box(unbounded_low, unbounded_high, shape=(3,)),
            "achieved_goal": Box(unbounded_low, unbounded_high, shape=(3,)),
        })
        self.gazebo = FakeGazeboConnection(stop_ignored=stop_ignored)
        self._step_delay_s = float(step_delay_s)   # test switch: a step in flight at the e-stop
        self._rng = random.Random()
        self._ee = None
        self._goal = None
        self._elapsed_steps = 0
        self._hold = 0
        self._closed = False
        # Upstream ends construction with the simulation running (robot_gazebo_goal_env.py:125-128).
        self.gazebo.unpause_sim()

    @staticmethod
    def _info(ee, goal):
        return {
            "reference": list(goal),
            "state_of_interest": list(ee),
            "reference_error": [ee[i] - goal[i] for i in range(3)],
        }

    def _observation(self):
        return {
            "observation": list(self._ee),
            "desired_goal": list(self._goal),
            "achieved_goal": list(self._ee),
        }

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        # Upstream randomises the initial EE pose and then samples the goal:
        # panda_reach.py:1586-1791 and :1497-1574.  Both draws use this fake's generator (placeholder RNG stream).
        self._ee = [self._rng.uniform(SPACE_LOW[i], SPACE_HIGH[i]) for i in range(3)]
        self._goal = [self._rng.uniform(SPACE_LOW[i], SPACE_HIGH[i]) for i in range(3)]
        self._elapsed_steps = 0
        # Upstream does not clear _is_done_samples in _init_env_variables (panda_reach.py:1793-1800); only a
        # termination resets it (panda_reach.py:1483), so a truncated episode can carry one held sample into the
        # next episode.
        self._closed = False
        if PAUSE_AFTER_STEP:
            self.gazebo.pause_sim()       # robot_gazebo_goal_env.py:222-223
        return self._observation(), self._info(self._ee, self._goal)

    def step(self, action):
        values = action.tolist() if hasattr(action, "tolist") else list(action)
        if len(values) != len(EFFORT_LOW):
            raise ValueError("the action must contain the seven arm-effort values")
        if self._ee is None:
            raise RuntimeError("Call reset before using step method.")
        self.gazebo.unpause_sim()         # robot_gazebo_goal_env.py:158, before the action is applied
        if self._step_delay_s:
            time.sleep(self._step_delay_s)
        # placeholder: no arm dynamics; the first three effort components move the EE linearly.
        for index in range(3):
            self._ee[index] += EFFORT_TO_METRES * float(values[index])

        distance = math.dist(self._ee, self._goal)
        reward = -distance                     # dense reward of the shipped config, panda_reach.py:1314-1325
        if distance < DISTANCE_THRESHOLD:
            self._hold += 1
            terminated = self._hold >= HOLD_SAMPLES
            if terminated:
                self._hold = 0
        else:
            self._hold = 0
            terminated = False
        if PAUSE_AFTER_STEP:
            self.gazebo.pause_sim()       # robot_gazebo_goal_env.py:161-162
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._observation(), reward, terminated, truncated, self._info(self._ee, self._goal)

    def close(self):
        self._closed = True
