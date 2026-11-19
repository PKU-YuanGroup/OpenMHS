"""Fake backend of the Ravens Visual Foresight Gymnasium driver: an analytic pick-and-place stand-in.

Why a fake: the acceptance gate runs without ``pybullet``, ``gym==0.17.3`` or the upstream assets, and package code
never imports the clone.  This module models the interface of
``ravens.environments.environment_mcts:EnvironmentMCTS`` (the class the driver names as ``native``): ``seed``,
``reset``, ``step``, ``set_task``, ``close``, the ``action_space`` and ``observation_space``, and the
``is_static``/``info`` properties.  The task is the demo script's default ``put-block-base`` configuration
(``ravens/demos_tvf.py:12`` and ``:33`` with ``ravens/tasks/__init__.py:70``).

What this is not: the upstream PyBullet simulator.  It does not load a URDF, run a physics engine, render a camera or
execute the UR5 motion planner.  A step moves the nearest block directly from its pick pose to its place pose.  The
observation arrays are a tiny placeholder rendering, not the 480x640 RGB-D images of the three RealSense cameras
(``ravens/tasks/cameras.py:26``).  Everything below is test data or a copy of a constant whose upstream line is
named; it is not a fact or a bound.

The public members are the ones EnvironmentMCTS has (gate G7).  The three space classes duck-type
``gym.spaces.Dict``/``Tuple``/``Box`` so the bridge can read ``spaces``, ``low``, ``high`` and ``shape``.
"""

import math
import random

# ravens/tasks/cameras.py:22-26: three RealSense D415 cameras, image_size (480, 640).  The fake renders a smaller
# placeholder image because the bridge carries the observation as JSON; the real size is in the driver's gaps.
REAL_CAMERAS = 3
REAL_IMAGE_SIZE = (480, 640)  # cameras.py:26
FAKE_IMAGE_SIZE = (8, 8)      # placeholder: fake downsample, not the device size

# ravens/tasks/put_block_base_mcts.py:25-44: the demo task's block, base, place offsets and workspace.
BLOCK_SIZE = (0.04, 0.04, 0.04)                                # put_block_base_mcts.py:25
BASE_SIZE = (0.05, 0.15, 0.005)                                # put_block_base_mcts.py:31-33
BASE_URDF = "stand/stand_3.urdf"                               # put_block_base_mcts.py:28-30
BLOCK_URDF = "stacking/block.urdf"                             # put_block_base_mcts.py:68
PLACE_Y = (0.0, 0.05, 0.10)                                    # put_block_base_mcts.py:36-38
BOUNDS = ((0.25, 0.75), (-0.25, 0.25), (0.0, 0.28))            # put_block_base_mcts.py:44
NUM_BLOCKS = 3                                                 # put_block_base_mcts.py:27
BASE_ID = 0                                                    # placeholder: fake object id
BLOCK_IDS = (10, 11, 12)                                       # placeholder: fake object ids
# ravens/tasks/task_mcts.py:55: the task's positional match threshold.
POS_EPS = 0.01
# placeholder: how close the fake pick pose must be to a block's centre to grasp it.
PICK_RADIUS = 0.05
# placeholder: fake image colours and depth values, not sensor data.
BACKGROUND = [24, 24, 24]
BASE_COLOR = [120, 120, 120]
TARGET_COLOR = [30, 220, 30]
BLOCK_COLOR = [220, 30, 30]
BACKGROUND_DEPTH = 0.5
BASE_DEPTH = 0.35
TARGET_DEPTH = 0.45
BLOCK_DEPTH = 0.4


class Box:
    """Duck-typed ``gym.spaces.Box``: ``low``/``high`` are flat lists and ``shape`` is the array shape."""

    def __init__(self, low, high, shape=None):
        self.low = list(low) if isinstance(low, (list, tuple)) else [low]
        self.high = list(high) if isinstance(high, (list, tuple)) else [high]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Tuple:
    """Duck-typed ``gym.spaces.Tuple``: an ordered list of spaces."""

    def __init__(self, spaces):
        self.spaces = list(spaces)


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping from string keys to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _flat_distance(first, second):
    """Distance in the x-y plane; the task's is_match ignores z (task_mcts.py:326-328)."""
    return math.hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))


def _numeric_pose(pose):
    """A native pose is ``(position[3], orientation[4])``; the fake needs both parts to be finite numbers."""
    if not isinstance(pose, (list, tuple)) or len(pose) != 2:
        return False
    position, orientation = pose
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        return False
    if not isinstance(orientation, (list, tuple)) or len(orientation) != 4:
        return False
    for value in list(position) + list(orientation):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False
    return True


class _PutBlockBaseTask:
    """The shipped ``put-block-base-mcts`` task reduced to the fields the fake needs.

    It is not imported from the clone.  Its constants are copied with their upstream lines; the random layouts and
    the direct block transition are placeholders (see the driver's fidelity gaps).
    """

    def __init__(self, pp=True):
        self.pp = pp
        self.mode = "train"
        self.bounds = BOUNDS
        self.pos_eps = POS_EPS
        self.rot_eps = 15.0 * math.pi / 180.0  # task_mcts.py:56, np.deg2rad(15)
        self.pix_size = 0.003125               # environment.py:70
        self.goals = []
        self.progress = 0.0
        self._rewards = 0.0
        self.max_steps = None
        self.assets_root = None

    def set_assets_root(self, assets_root):
        self.assets_root = assets_root

    def reset(self, env):
        """Lay out three blocks and three target positions; return the base and block ids (task file:47-84)."""
        self.goals = [{"max_reward": 1.0, "objects": NUM_BLOCKS}]
        self.progress = 0.0
        self._rewards = 0.0
        # placeholder: the base jitter and the free-pose sampling replace get_random_pose (task_mcts.py:360-383).
        base_x = 0.5 + env._rng.uniform(-0.05, 0.05)
        base_y = env._rng.uniform(-0.05, 0.05)
        env.base_pose = ([base_x, base_y, 0.0], [0.0, 0.0, 0.0, 1.0])
        env.targets = [[base_x, base_y + offset, BLOCK_SIZE[2] / 2.0] for offset in PLACE_Y]
        env.block_positions = []
        for _ in range(NUM_BLOCKS):
            # placeholder: uniform free-space sample inside the task bounds.
            x = env._rng.uniform(BOUNDS[0][0] + BLOCK_SIZE[0], BOUNDS[0][1] - BLOCK_SIZE[0])
            y = env._rng.uniform(BOUNDS[1][0] + BLOCK_SIZE[1], BOUNDS[1][1] - BLOCK_SIZE[1])
            env.block_positions.append([x, y, BLOCK_SIZE[2] / 2.0])
        env.matched = set()
        env.claimed_targets = set()
        self.max_steps = NUM_BLOCKS + 2  # put_block_base_mcts.py:57
        return BASE_URDF, BASE_SIZE, BASE_ID, list(BLOCK_IDS)

    def done(self):
        """The task base's completion rule (task_mcts.py:316)."""
        return (len(self.goals) == 0) or (self._rewards > 0.99)


class FakeEnvironmentMCTS:
    """Pure-Python stand-in for ``EnvironmentMCTS`` with a seeded analytic put-block-base world."""

    def __init__(self, assets_root=None, task=None, disp=False, shared_memory=False, hz=240, use_egl=False):
        if use_egl and disp:
            raise ValueError("EGL rendering cannot be used with disp=True")
        self.assets_root = assets_root
        self.disp = disp
        self.shared_memory = shared_memory
        self.hz = hz
        self.use_egl = use_egl
        self._rng = random.Random()
        self._closed = False
        self._seed = None
        self._episode = 0
        self._tick = 0
        self.base_pose = ([0.5, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])  # placeholder: replaced by the seeded reset
        self.targets = []
        self.block_positions = []
        self.matched = set()
        self.claimed_targets = set()
        self.block_ids = list(BLOCK_IDS)
        self.position_bounds = Box([0.25, -0.5, 0.0], [0.75, 0.5, 0.28], shape=(3,))
        orientation = Box([-1.0, -1.0, -1.0, -1.0], [1.0, 1.0, 1.0, 1.0], shape=(4,))
        self.action_space = Dict({
            "pose0": Tuple((self.position_bounds, orientation)),
            "pose1": Tuple((self.position_bounds, Box([-1.0] * 4, [1.0] * 4, shape=(4,)))),
        })
        color = Box(0, 255, shape=FAKE_IMAGE_SIZE + (3,))
        depth = Box(0.0, 20.0, shape=FAKE_IMAGE_SIZE)
        self.observation_space = Dict({
            "color": Tuple((color, color, color)),
            "depth": Tuple((depth, depth, depth)),
        })
        self.task = task if task is not None else _PutBlockBaseTask()
        if self.task is not None and hasattr(self.task, "set_assets_root"):
            self.task.set_assets_root(self.assets_root)

    # -- native Gym-style API (the members EnvironmentMCTS has) ------------
    def seed(self, seed=None):
        """Set the fake's generator and return the seed (environment.py:175-177 uses numpy's RandomState)."""
        self._rng = random.Random(seed)
        self._seed = seed
        return seed

    def set_task(self, task):
        """Assign a task and give it the assets root (environment.py:343-345)."""
        task.set_assets_root(self.assets_root)
        self.task = task

    def reset(self):
        """Reset the analytic task and return the native 6-tuple (environment_mcts.py:123-166)."""
        if not self.task:
            raise ValueError("environment task must be set. Call set_task or pass the task arg in the "
                             "environment constructor.")
        self._episode += 1
        self._tick = 0
        self.base_urdf, self.base_size, self.base_id, self.block_ids = self.task.reset(self)
        self.block_positions = [list(position) for position in self.block_positions]
        [init_obs, _], _, _, info = self.step()
        return init_obs, self.base_urdf, self.base_size, self.base_id, list(self.block_ids), info

    def step(self, action=None):
        """Apply the pick/place pair and return the native 4-tuple (environment_mcts.py:58-116)."""
        if action is not None:
            pick_pose = action["pose0"]
            place_pose = action["pose1"]
            if not _numeric_pose(pick_pose) or not _numeric_pose(place_pose):
                obs = self._get_obs()
                return [obs, obs], 0.0, True, self.info
            pick, place = pick_pose[0], place_pose[0]
            if not self._inside_bounds(pick) or not self._inside_bounds(place):
                obs = self._get_obs()
                return [obs, obs], 0.0, True, self.info
            pick_obs = self._get_obs()
            previous = self.task._rewards
            block = self._nearest_unmatched_block(pick)
            if block is not None:
                self.block_positions[block] = [float(place[0]), float(place[1]), BLOCK_SIZE[2] / 2.0]
                target = self._nearest_unclaimed_target(place)
                if target is not None:
                    self.matched.add(block)
                    self.claimed_targets.add(target)
                    self.task.progress += 1.0 / NUM_BLOCKS
                    self.task._rewards = self.task.progress
                    if len(self.matched) == NUM_BLOCKS:
                        self.task.goals = []
            place_obs = self._get_obs()
            reward = self.task._rewards - previous
        else:
            pick_obs = self._get_obs()
            place_obs = None
            reward = 0.0
        self._tick += 1
        done = self.task.done()
        info = dict(self.info)
        return [pick_obs, place_obs], reward, done, info

    def close(self):
        self._closed = True

    @property
    def is_static(self):
        """The analytic world is settled immediately (environment.py:155-160)."""
        return True

    @property
    def info(self):
        """Object id -> (position, rotation, dimensions), as environment.py:322-340."""
        out = {self.base_id: (list(self.base_pose[0]), list(self.base_pose[1]), list(BASE_SIZE))}
        for block_id, position in zip(self.block_ids, self.block_positions):
            out[block_id] = (list(position), [0.0, 0.0, 0.0, 1.0], list(BLOCK_SIZE))
        return out

    def render(self, mode="rgb_array"):
        """Render only the colour image of the first fake camera (environment.py:259-264)."""
        if mode != "rgb_array":
            raise NotImplementedError("Only rgb_array implemented")
        color, _, _ = self._camera_image(0)
        return color

    # -- analytic world ----------------------------------------------------
    def _inside_bounds(self, position):
        low, high = self.position_bounds.low, self.position_bounds.high
        return all(float(low[i]) <= float(position[i]) <= float(high[i]) for i in range(3))

    def _nearest_unmatched_block(self, pick):
        best, best_distance = None, PICK_RADIUS
        for index, position in enumerate(self.block_positions):
            if index in self.matched:
                continue
            distance = _flat_distance(position, pick)
            if distance < best_distance:
                best, best_distance = index, distance
        return best

    def _nearest_unclaimed_target(self, place):
        best, best_distance = None, POS_EPS
        for index, target in enumerate(self.targets):
            if index in self.claimed_targets:
                continue
            distance = _flat_distance(target, place)
            if distance < best_distance:
                best, best_distance = index, distance
        return best

    def _camera_image(self, view):
        """A placeholder projection of the block and target positions into an 8x8 colour/depth image."""
        height, width = FAKE_IMAGE_SIZE
        color = [[list(BACKGROUND) for _ in range(width)] for _ in range(height)]
        depth = [[BACKGROUND_DEPTH for _ in range(width)] for _ in range(height)]

        def pixel(position):
            x = (float(position[0]) - BOUNDS[0][0]) / (BOUNDS[0][1] - BOUNDS[0][0])
            y = (float(position[1]) - BOUNDS[1][0]) / (BOUNDS[1][1] - BOUNDS[1][0])
            column = min(width - 1, max(0, int(round(x * (width - 1)))))
            row = min(height - 1, max(0, int(round((1.0 - y) * (height - 1)))))
            # placeholder: a different one-pixel shift per camera, not a camera model.
            column = min(width - 1, max(0, column + view - 1))
            return row, column

        row, column = pixel(self.base_pose[0])
        color[row][column] = list(BASE_COLOR)
        depth[row][column] = BASE_DEPTH
        for target in self.targets:
            row, column = pixel(target)
            color[row][column] = list(TARGET_COLOR)
            depth[row][column] = TARGET_DEPTH
        for position in self.block_positions:
            row, column = pixel(position)
            color[row][column] = list(BLOCK_COLOR)
            depth[row][column] = BLOCK_DEPTH
        return color, depth, None

    def _get_obs(self):
        """The native observation dict: one colour and one depth array per camera (environment.py:398-407)."""
        color, depth = (), ()
        for view in range(REAL_CAMERAS):
            view_color, view_depth, _ = self._camera_image(view)
            color += (view_color,)
            depth += (view_depth,)
        return {"color": color, "depth": depth}
