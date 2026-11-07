"""Fake backend of the TDW-MAT driver: a reduced analytic stand-in for ``tdw_gym:TDW``.

Why a fake: the acceptance gate cannot install or run the upstream environment.  TDW-MAT needs Python 3.9, an
editable install of the ``tdw_mat`` project, a ThreeDWorld build and its own X server, a pinned ``tdw`` package
(``tdw_mat/requirements.txt:17``) and downloaded transport-challenge asset bundles
(``tdw_mat/README.md:59``), and package code never imports the clone.  This module re-implements the parts of
``tdw_gym.py`` the ``cap.world.*`` contract needs: the corrected single-agent spaces, a seeded reset, an analytic
action transition, the per-action reward penalty and the legacy reset/step tuple shapes.

What this is not: the ThreeDWorld simulator.  The fidelity ``gaps`` of the driver say what is not modelled.  In
particular the images are 2x2 placeholders instead of the screen_size-pixel camera frames (512 by default), the object ids, positions,
camera matrix and scene are test data, and the fake does not talk to a controller.  Every number that re-states an
upstream default or an upstream rule cites the line of ``tdw_gym.py`` at the pinned commit; a placeholder is
marked ``# placeholder`` and is never a Fact, a Limit or a reference.  The public members below are methods of TDW
(``reset``, ``step``, ``get_obs``, ``check_goal``, ``close``; gate G7), and the space classes duck-type
``gym.spaces`` (the bridge reads ``n``, ``start``, ``low``, ``high``, ``shape``, ``spaces`` and ``max_length``).
"""

import math
import random

# tdw_gym.py:52: the fake's defaults mirror the upstream constructor, which the device may be configured
# differently; they are not limits.
DEFAULT_NUMBER_OF_AGENTS = 1
DEFAULT_SCREEN_SIZE = 512
DEFAULT_MAX_FRAMES = 3000
# tdw_gym.py:628-633: one step of type 0 moves 0.5 m, of type 1/2 turns 15 degrees
FORWARD_METERS = 0.5
TURN_DEGREES = 15
# tdw_gym.py:67: an object farther than the reach threshold cannot be grasped
REACH_THRESHOLD = 2
# tdw_gym.py:251: reset sets the field of view to 90 degrees
FOV_DEGREES = 90
# tdw_gym.py:725-726: a failed agent action costs 0.1 of reward
FAILED_ACTION_PENALTY = 0.1


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gym.spaces.Box``: an element shape and one low/high pair per element (or a pair of bounds)."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape) if shape is not None else ()
        self.dtype = dtype

    def contains(self, value):
        values = value if isinstance(value, (list, tuple)) else [value]
        return all(float(self.low) <= float(item) <= float(self.high) for item in values)


class Text:
    """Duck-typed ``gym.spaces.Text``: the bridge does not derive a schema from it (it stays open)."""

    def __init__(self, max_length, charset=None):
        self.max_length = int(max_length)
        self.charset = charset
        self.shape = ()
        self.dtype = "str"


class Dict:
    """Duck-typed ``gym.spaces.Dict``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = "object"


class Tuple:
    """Duck-typed ``gym.spaces.Tuple``."""

    def __init__(self, spaces):
        self.spaces = tuple(spaces)
        self.shape = (len(self.spaces),)
        self.dtype = "object"


def _hand_space():
    """``hand_object_space`` of tdw_gym.py:110-116."""
    return Dict({
        "id": Discrete(30),
        "type": Discrete(4),
        "name": Text(max_length=100),
        "contained": Tuple(Discrete(30) for _ in range(3)),
        "contained_name": Tuple(Text(max_length=100) for _ in range(3)),
    })


class FakeTDW:
    """A small, deterministic stand-in for ``TDW`` with the same reset/step contract (test data only)."""

    def __init__(self, number_of_agents=DEFAULT_NUMBER_OF_AGENTS, screen_size=DEFAULT_SCREEN_SIZE,
                 max_frames=DEFAULT_MAX_FRAMES, **_options):
        self.number_of_agents = int(number_of_agents)
        self.screen_size = int(screen_size)
        self.max_frame = int(max_frames)                      # tdw_gym.py:142
        self.seed = None                                      # tdw_gym.py:69 (instance state, not a bound)
        self.num_step = 0
        self.num_frames = 0
        self.reward = 0.0
        self.done = False
        self.success = False
        self.obs = None
        self.messages = [None for _ in range(self.number_of_agents)]
        self.action_buffer = [[] for _ in range(self.number_of_agents)]
        self.target_object_ids = [0]                          # placeholder
        self.container_ids = [1]                              # placeholder
        self.goal_position_id = 2                             # placeholder
        self.goal_description = {"target": 1}                 # placeholder
        self.satisfied = {}
        # tdw_gym.py:104-108: the single-agent action space the upstream step expects.
        self.action_space_single = Dict({
            "type": Discrete(7),
            "object": Discrete(30),
            "arm": Discrete(2),
            "message": Text(max_length=1000),
        })
        # tdw_gym.py:86-103: the image and object spaces.
        rgb_space = Box(0, 256, (3, self.screen_size, self.screen_size), dtype="int32")
        seg_space = Box(0, 256, (self.screen_size, self.screen_size, 3), dtype="int32")
        depth_space = Box(0, 256, (self.screen_size, self.screen_size), dtype="int32")
        object_space = Dict({
            "id": Discrete(30),
            "type": Discrete(4),
            "seg_color": Box(0, 255, (3,), dtype="int32"),
            "name": Text(max_length=100),
        })
        hand_object_space = _hand_space()
        # tdw_gym.py:119-133: the single-agent observation space.
        self.observation_space_single = Dict({
            "rgb": rgb_space,
            "seg_mask": seg_space,
            "depth": depth_space,
            "agent": Box(-30, 30, (6,), dtype="float32"),
            "held_objects": Tuple((hand_object_space, hand_object_space)),
            "oppo_held_objects": Tuple((hand_object_space, hand_object_space)),
            "visible_objects": Tuple(object_space for _ in range(50)),
            "status": Discrete(4),
            "valid": Discrete(2),
            "FOV": Box(0, 120, (1,), dtype="float32"),
            "camera_matrix": Box(-30, 30, (4, 4), dtype="float32"),
            "messages": Tuple(Text(max_length=1000) for _ in range(2)),
            "current_frames": Discrete(30),
        })
        self.observation_space = Dict({
            str(i): self.observation_space_single for i in range(self.number_of_agents)
        })
        # tdw_gym.py:139-140 builds this from observation_space_single by mistake.  The bridge's limit paths are
        # field names, so an upstream agent map keyed "0" cannot be the contract; the single-agent space is, and
        # step() wraps it under agent id 0 (tdw_gym.py:619 reads actions[str(replicant_id)]).
        self.action_space = self.action_space_single
        self._rng = random.Random()
        self._mark = 0
        self._agent_position = []
        self._agent_yaw = []
        self._held = []
        self._delivered = set()
        self._objects = {}

    # -- episode -----------------------------------------------------------
    def reset(self, *, seed=None, options=None, output_dir=None):
        """Seeded reset; returns the legacy ``(observation, info, env_api)`` three-tuple (tdw_gym.py:346)."""
        self.seed = seed
        self._rng = random.Random(seed)                       # upstream: np.random.RandomState(seed), tdw_gym.py:229
        self._mark = self._rng.randrange(256)                 # placeholder: makes the seeded reset observable
        self.num_step = 0
        self.num_frames = 0
        self.reward = 0.0
        self.done = False
        self.success = False
        self.satisfied = {}
        self._delivered = set()
        self.messages = [None for _ in range(self.number_of_agents)]
        self.action_buffer = [[] for _ in range(self.number_of_agents)]
        self._agent_position = [[0.0, 1.5, 0.0] for _ in range(self.number_of_agents)]  # placeholder
        self._agent_yaw = [0.0 for _ in range(self.number_of_agents)]                  # placeholder
        self._held = [[None, None] for _ in range(self.number_of_agents)]
        self._objects = {
            0: {"name": "target", "type": 0, "seg_color": [255, 0, 0],
                "position": [self._rng.uniform(-1.0, 1.0), 0.0, self._rng.uniform(-1.0, 1.0)]},  # placeholder
            1: {"name": "container", "type": 1, "seg_color": [0, 255, 0],
                "position": [self._rng.uniform(-3.0, 3.0), 0.0, self._rng.uniform(-3.0, 3.0)]},  # placeholder
            2: {"name": "bed", "type": 2, "seg_color": [0, 0, 255],
                "position": [self._rng.uniform(-3.0, 3.0), 0.0, self._rng.uniform(-3.0, 3.0)]},  # placeholder
        }
        self.obs = self.get_obs()
        info = {
            "goal_description": dict(self.goal_description),   # placeholder
            "rooms_name": [],                                  # placeholder
            "agent_colors": {i: [255, 255, 255] for i in range(self.number_of_agents)},  # placeholder
        }
        env_api = [{} for _ in range(self.number_of_agents)]    # placeholder (upstream exposes bound helpers)
        return self.obs, info, env_api

    def step(self, actions):
        """One action decision per agent; returns the legacy four-tuple (tdw_gym.py:754)."""
        if self.obs is None:
            raise AssertionError("Call reset before using step method.")
        if isinstance(actions, dict) and "type" in actions:
            if self.number_of_agents != 1:
                raise ValueError("the single-agent action contract serves number_of_agents=1")
            actions = {"0": actions}                           # tdw_gym.py:619: actions[str(replicant_id)]
        valid = [True for _ in range(self.number_of_agents)]
        for agent_id in range(self.number_of_agents):
            valid[agent_id] = self._apply_action(agent_id, actions[str(agent_id)])
        reward = 0.0
        for agent_id in range(self.number_of_agents):
            if not valid[agent_id]:
                reward -= FAILED_ACTION_PENALTY                # tdw_gym.py:725-726
        self.num_frames += 1                                   # tdw_gym.py:706-708 (upstream counts controller frames; the fake advances one per action)
        self.num_step += 1
        self.reward += reward
        goal_put, goal_total, self.success = self.check_goal()
        done = self.num_frames >= self.max_frame or self.success   # tdw_gym.py:731
        self.done = done
        obs = self.get_obs()
        for agent_id in range(self.number_of_agents):
            obs[str(agent_id)]["valid"] = 1 if valid[agent_id] else 0
            obs[str(agent_id)]["current_frames"] = self.num_frames
        info = {"done": done, "num_frames_for_step": 1, "num_step": self.num_step}   # tdw_gym.py:747-749
        if done:
            info["reward"] = self.reward
        self.obs = obs
        return obs, reward, done, info

    def _apply_action(self, agent_id, action):
        """Apply one action of the single-agent space; a False result is an invalid action (upstream ``valid``)."""
        kind = action.get("type")
        if kind == "ongoing":                                  # tdw_gym.py:620
            return True
        if kind == 0:                                          # move forward 0.5 m (tdw_gym.py:628)
            yaw = math.radians(self._agent_yaw[agent_id])
            self._agent_position[agent_id][0] += FORWARD_METERS * math.sin(yaw)
            self._agent_position[agent_id][2] += FORWARD_METERS * math.cos(yaw)
            return True
        if kind == 1:                                          # turn left 15 degrees (tdw_gym.py:630)
            self._agent_yaw[agent_id] += TURN_DEGREES
            return True
        if kind == 2:                                          # turn right 15 degrees (tdw_gym.py:632)
            self._agent_yaw[agent_id] -= TURN_DEGREES
            return True
        if kind == 3:                                          # reach for and grasp (tdw_gym.py:634-636)
            object_id = action.get("object")
            arm = action.get("arm")
            if object_id not in self._objects or arm not in (0, 1):
                return False
            if self._distance(agent_id, object_id) > REACH_THRESHOLD:   # tdw_gym.py:667-669
                return False
            self._held[agent_id][arm] = object_id
            return True
        if kind == 4:                                          # put in container (tdw_gym.py:637-638)
            delivered = False
            for arm in (0, 1):
                if self._held[agent_id][arm] in self.target_object_ids:
                    self._delivered.add(self._held[agent_id][arm])
                    self._held[agent_id][arm] = None
                    delivered = True
            return delivered
        if kind == 5:                                          # drop (tdw_gym.py:639-640)
            arm = action.get("arm")
            if arm in (0, 1):
                self._held[agent_id][arm] = None
            return True
        if kind == 6:                                          # send message (tdw_gym.py:641-642)
            self.messages[agent_id] = action.get("message") or ""   # placeholder text
            return True
        return False                                           # tdw_gym.py:643-644 asserts False

    def check_goal(self):
        """The upstream goal check (tdw_gym.py:419-431); the fake counts delivered target object ids."""
        count = sum(1 for object_id in self.target_object_ids if object_id in self._delivered)
        total = len(self.target_object_ids)
        return count, total, count == total

    def _distance(self, agent_id, object_id):
        position = self._agent_position[agent_id]
        target = self._objects[object_id]["position"]
        return math.hypot(position[0] - target[0], position[2] - target[2])

    # -- observation -------------------------------------------------------
    def get_obs(self):
        """The observation dict keyed by agent id; the arrays are 2x2 placeholders (see the driver's gaps)."""
        obs = {}
        for agent_id in range(self.number_of_agents):
            my_hands = [self._hand_entry(self._held[agent_id][hand]) for hand in range(2)]
            other_agent = (agent_id + 1) % self.number_of_agents
            other_hands = ([self._hand_entry(self._held[other_agent][hand]) for hand in range(2)]
                           if self.number_of_agents > 1 else [self._empty_hand(), self._empty_hand()])
            visible = []
            for object_id, obj in sorted(self._objects.items()):
                visible.append({"id": object_id, "type": obj["type"], "seg_color": list(obj["seg_color"]),
                                "name": obj["name"]})
            for other in range(self.number_of_agents):
                visible.append({"id": 100 + other, "type": 3, "seg_color": [255, 255, 255],
                                "name": "agent"})           # tdw_gym.py:480-488 (agents are visible, type 3)
            while len(visible) < 50:
                visible.append(self._empty_object())
            position, forward = self._pose(agent_id)
            obs[str(agent_id)] = {
                "rgb": self._rgb(),
                "seg_mask": self._seg_mask(),
                "depth": [[0.1, 0.2], [0.3, 0.4]],                          # placeholder depths
                "agent": [position[0], position[1], position[2], forward[0], forward[1], forward[2]],
                "held_objects": my_hands,
                "oppo_held_objects": other_hands,
                "visible_objects": visible[:50],
                "status": 1,                                                # placeholder: success
                "valid": 1,
                "FOV": [float(FOV_DEGREES)],
                "camera_matrix": [1.0, 0.0, 0.0, 0.0,                        # placeholder identity matrix
                                  0.0, 1.0, 0.0, 0.0,
                                  0.0, 0.0, 1.0, 0.0,
                                  0.0, 0.0, 0.0, 1.0],
                "messages": ["", ""],                                       # placeholder message slots
                "current_frames": self.num_frames,
            }
        return obs

    def _pose(self, agent_id):
        position = self._agent_position[agent_id]
        yaw = math.radians(self._agent_yaw[agent_id])
        return position, (math.sin(yaw), 0.0, math.cos(yaw))

    def _rgb(self):
        value = (self._mark + self.num_frames) % 256                   # placeholder pixel
        return [[[value, 0, 0], [0, 0, 0]],
                [[0, 0, 0], [0, 0, 0]],
                [[0, 0, 0], [0, 0, 0]]]

    def _seg_mask(self):
        value = self.num_frames % 256                                  # placeholder pixel
        return [[[0, 0, 0], [0, 0, 0]],
                [[0, 0, 0], [value, 0, 0]]]

    def _empty_object(self):
        return {"id": -1, "type": -1, "seg_color": [0, 0, 0], "name": ""}   # placeholder empty slot (upstream: None)

    def _empty_hand(self):
        return {"id": -1, "type": -1, "name": "", "contained": [-1, -1, -1],
                "contained_name": ["", "", ""]}                         # placeholder empty hand (upstream: None)

    def _hand_entry(self, object_id):
        if object_id is None:
            return self._empty_hand()
        obj = self._objects[object_id]
        return {"id": object_id, "type": obj["type"], "name": obj["name"], "contained": [-1, -1, -1],
                "contained_name": ["", "", ""]}                         # placeholder containment

    def close(self):
        self.obs = None
