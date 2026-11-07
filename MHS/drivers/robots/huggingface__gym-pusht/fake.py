"""Fake backend of the gym-pusht driver: a pure Python stand-in for ``gym_pusht.envs:PushTEnv``.

Why a fake: the acceptance gate never installs or imports the upstream clone (``gym_pusht`` needs ``pymunk``,
``shapely``, ``pygame``, ``opencv-python`` and ``scikit-image``, ``pyproject.toml:24-30``), and package code never
imports it either.  This module re-implements the parts of ``PushTEnv`` that the Gymnasium bridge drives -- ``reset``,
``step`` and ``close`` -- with the action and observation spaces derived from the same constants as the upstream class
(gate G7 checks this public surface against the class in the clone).  The geometry, the PD control, the coverage-based
reward and the success threshold follow ``gym_pusht/envs/pusht.py``; the contact solver of pymunk does not, and every
difference is listed in the fidelity ``gaps`` of driver.py.

Every upstream constant below cites the line of the clone at the pinned commit
1dce32970bc3d25e7fad5872c3020159bc5eb31f.  Numbers marked ``placeholder`` are test data of this stand-in (the contact
transfer and the damping that replace pymunk's collision solver); they are not facts and are cited nowhere.

Nothing here talks to a device.
"""

import math
import random
from collections.abc import Mapping

# -- the modelled environment (gym_pusht/envs/pusht.py) -----------------------------------------------------------
# The workspace is a 512 x 512 surface with four wall segments at 5 and 506 of radius 2.
SURFACE_SIZE = 512.0                                            # pusht.py:298 (the pygame surface)
WALL_MIN, WALL_MAX, WALL_RADIUS = 5.0, 506.0, 2.0               # pusht.py:437-440
# The agent is a circle of radius 15 (pusht.py:445) and the block is the tee shape built by add_tee with scale 30,
# length 4 and mass 1 (pusht.py:485-516).
AGENT_RADIUS = 15.0                                             # pusht.py:445
BLOCK_MASS = 1                                                  # pusht.py:488
TEE_LENGTH, TEE_SCALE = 4, 30                                   # pusht.py:485 and :489
# The two rectangles of the tee in the body frame of add_tee (pusht.py:490-502).
TEE_BAR = [
    (-TEE_LENGTH * TEE_SCALE / 2, TEE_SCALE),
    (TEE_LENGTH * TEE_SCALE / 2, TEE_SCALE),
    (TEE_LENGTH * TEE_SCALE / 2, 0.0),
    (-TEE_LENGTH * TEE_SCALE / 2, 0.0),
]
TEE_STEM = [
    (-TEE_SCALE / 2, TEE_SCALE),
    (-TEE_SCALE / 2, TEE_LENGTH * TEE_SCALE),
    (TEE_SCALE / 2, TEE_LENGTH * TEE_SCALE),
    (TEE_SCALE / 2, TEE_SCALE),
]
TEE_RECTS = (TEE_BAR, TEE_STEM)
# add_tee puts the body centre of gravity halfway between the two rectangle centres of gravity (0, 15) and (0, 75)
# (pusht.py:511).
BLOCK_COG = (0.0, 45.0)                                         # pusht.py:511
# The goal body of get_goal_pose_body never sets a centre of gravity, so its transform keeps the origin (0, 0)
# (pusht.py:403-412).
GOAL_COG = (0.0, 0.0)
# The union area of the two tee rectangles: 120 x 30 plus 30 x 90 (pusht.py:490-502).
TEE_AREA = 120.0 * 30.0 + 30.0 * 90.0

# -- control and reward -------------------------------------------------------------------------------------------
# The PD gains are k_p 100 and k_v 20 (pusht.py:164); the physics timestep is dt 0.01 s and control_hz is the
# metadata render_fps of 10 (pusht.py:135 and :165-166).  One step runs int(1 / (dt * control_hz)) = 10 substeps
# (pusht.py:242).
K_P, K_V = 100, 20                                              # pusht.py:164
DT = 0.01                                                       # pusht.py:166
CONTROL_HZ = 10                                                 # pusht.py:135
SUBSTEPS = int(1 / (DT * CONTROL_HZ))                           # pusht.py:242
SUCCESS_THRESHOLD = 0.95                                        # pusht.py:181
# The goal pose of _setup is x 256, y 256 and angle pi/4 radians (pusht.py:447).
GOAL_POSE = (256.0, 256.0, math.pi / 4)                         # pusht.py:447
# The start poses of _setup: the agent at (256, 400) and the block at (256, 300) with angle 0 (pusht.py:445-446).
START_AGENT = (256.0, 400.0)                                    # pusht.py:445
START_BLOCK = (256.0, 300.0)                                    # pusht.py:446
# A reset draws the agent x and y from the integers 50 to 449, the block x and y from 100 to 399 and the block angle
# from -pi to pi (pusht.py:276-284); numpy integers(low, high) excludes high.
RESET_AGENT_LOW, RESET_AGENT_HIGH = 50, 450                     # pusht.py:278-279
RESET_BLOCK_LOW, RESET_BLOCK_HIGH = 100, 400                    # pusht.py:280-281
# PushT-v0 is registered with max_episode_steps 300, which gymnasium.make() applies as a TimeLimit wrapper around
# PushTEnv (gym_pusht/__init__.py:3-8; the number is on line 6).
MAX_EPISODE_STEPS = 300
# placeholder: the share of the agent's closing speed a contact passes to the block, the torque share, and the
# per-substep velocity and spin loss that stand in for pymunk's collision solver and friction
CONTACT_TRANSFER = 0.5
ANGULAR_TRANSFER = 0.02
LINEAR_DAMPING = 0.999
ANGULAR_DAMPING = 0.995
# placeholder: the tee's moment of inertia about its centre of gravity, the plate formula m * (w^2 + h^2) / 12
BLOCK_INERTIA = BLOCK_MASS * (120.0 ** 2 + 120.0 ** 2) / 12.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` (what the bridge reads)."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class _Body:
    """The position, velocity and angle a pymunk body exposes; a plain object so the fake needs no pymunk."""

    def __init__(self, position, velocity=None, angle=0.0, angular_velocity=0.0):
        self.position = list(position)
        self.velocity = list(velocity or (0.0, 0.0))
        self.angle = float(angle)
        self.angular_velocity = float(angular_velocity)


# -- geometry helpers (the fake replaces pymunk and shapely) ------------------------------------------------------
def _world_polygon(vertices, position, angle, cog):
    """A tee rectangle in the world: ``position + R(angle) * (vertex - cog)`` (a pymunk body's transform)."""

    cos, sin = math.cos(angle), math.sin(angle)
    return [
        (position[0] + (vx - cog[0]) * cos - (vy - cog[1]) * sin,
         position[1] + (vx - cog[0]) * sin + (vy - cog[1]) * cos)
        for vx, vy in vertices
    ]


def _signed_area(polygon):
    total = 0.0
    for index in range(len(polygon)):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % len(polygon)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _point_in_polygon(point, polygon):
    """Ray casting; both tee rectangles are simple convex polygons."""

    x, y = point
    inside = False
    for index in range(len(polygon)):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _closest_point_on_segment(point, start, end):
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return (ax, ay)
    t = min(1.0, max(0.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return (ax + t * dx, ay + t * dy)


def _intersection_area(subject, clip):
    """The area shared by two convex polygons (Sutherland-Hodgman clipping); the tee rectangles are convex."""

    if _signed_area(clip) < 0.0:
        clip = list(reversed(clip))
    output = list(subject)
    for index in range(len(clip)):
        if not output:
            return 0.0
        ax, ay = clip[index]
        bx, by = clip[(index + 1) % len(clip)]
        inputs, output = output, []
        edge_x, edge_y = bx - ax, by - ay
        for position in range(len(inputs)):
            px, py = inputs[position]
            qx, qy = inputs[(position + 1) % len(inputs)]
            p_side = edge_x * (py - ay) - edge_y * (px - ax)
            q_side = edge_x * (qy - ay) - edge_y * (qx - ax)
            if p_side >= 0.0:
                output.append((px, py))
            if (p_side >= 0.0) != (q_side >= 0.0):
                dx, dy = qx - px, qy - py
                denominator = edge_x * dy - edge_y * dx
                if abs(denominator) < 1e-12:
                    continue
                t = -p_side / denominator
                output.append((px + t * dx, py + t * dy))
    return abs(_signed_area(output))


class FakePushTEnv:
    """``PushTEnv`` without pymunk, shapely, pygame or numpy, serving the ``obs_type='state'`` observation."""

    # pusht.py:22-24 (the render modes) and :135 (render_fps)
    metadata = {"render_modes": ["rgb_array", "human"], "render_fps": CONTROL_HZ}

    def __init__(self, obs_type="state", render_mode="rgb_array", block_cog=None, damping=None,
                 observation_width=96, observation_height=96, visualization_width=680,
                 visualization_height=680):
        """The keyword arguments of ``PushTEnv.__init__`` (pusht.py:137-147); only the state observation is modelled."""

        if obs_type != "state":
            raise NotImplementedError(f"the fake serves obs_type='state'; got {obs_type!r} (pusht.py:93-94)")
        self.obs_type = obs_type                                    # pusht.py:150
        self.render_mode = render_mode                              # pusht.py:153
        self.observation_width = observation_width                  # pusht.py:154
        self.observation_height = observation_height                # pusht.py:155
        self.visualization_width = visualization_width              # pusht.py:156
        self.visualization_height = visualization_height            # pusht.py:157
        # pusht.py:161: Box(low=0, high=512, shape=(2,), dtype=float32); gymnasium broadcasts the two scalars
        self.action_space = Box(0.0, SURFACE_SIZE, (2,), "float32")
        # pusht.py:184-190: Box low [0, 0, 0, 0, 0] high [512, 512, 512, 512, 2*pi], dtype float64
        self.observation_space = Box([0.0, 0.0, 0.0, 0.0, 0.0],
                                     [SURFACE_SIZE, SURFACE_SIZE, SURFACE_SIZE, SURFACE_SIZE, 2 * math.pi],
                                     (5,), "float64")
        self.k_p, self.k_v = K_P, K_V                               # pusht.py:164
        self.control_hz = CONTROL_HZ                                # pusht.py:165
        self.dt = DT                                                # pusht.py:166
        self.block_cog = block_cog                                  # pusht.py:167 (not modelled)
        self.damping = damping                                      # pusht.py:168 (damping 0.0 is assumed)
        self.window = None                                          # pusht.py:175
        self.clock = None                                           # pusht.py:176
        self.teleop = None                                          # pusht.py:178
        self._last_action = None                                    # pusht.py:179
        self.success_threshold = SUCCESS_THRESHOLD                  # pusht.py:181
        self._random = random.Random()
        self._ticks = 0
        self._episode = 0
        self._setup()

    # -- the bridge surface (the public members PushTEnv has) -------------------------------------------------
    def reset(self, *, seed=None, options=None):
        """``pusht.py:268-294``: seed the generator, rebuild the space, set the state, return the observation."""

        if seed is not None:
            self._random = random.Random(int(seed))
        self._setup()
        reset_to_state = options.get("reset_to_state") if isinstance(options, Mapping) else None
        if reset_to_state is not None:
            state = [float(value) for value in reset_to_state]      # pusht.py:272-273
            if len(state) != 5:
                raise ValueError(f"reset_to_state needs 5 values, got {len(state)}")
        else:
            # pusht.py:276-284: the environment's own generator, not the global numpy one
            state = [
                self._random.randrange(RESET_AGENT_LOW, RESET_AGENT_HIGH),
                self._random.randrange(RESET_AGENT_LOW, RESET_AGENT_HIGH),
                self._random.randrange(RESET_BLOCK_LOW, RESET_BLOCK_HIGH),
                self._random.randrange(RESET_BLOCK_LOW, RESET_BLOCK_HIGH),
                self._random.uniform(-math.pi, math.pi),
            ]
        self._set_state(state)                                      # pusht.py:285
        self._ticks = 0
        self._episode += 1
        info = self._info()                                         # pusht.py:288
        info["is_success"] = False                                  # pusht.py:289
        return self._observation(), info

    def step(self, action):
        """``pusht.py:240-266``, plus the 300-step TimeLimit that ``gymnasium.make`` adds to PushT-v0."""

        values = [float(value) for value in action]
        if len(values) != 2:
            raise AssertionError(f"an action of two values is expected, got {len(values)}")
        self.n_contact_points = 0                                   # pusht.py:241
        self._last_action = values                                  # pusht.py:243
        for _ in range(SUBSTEPS):                                   # pusht.py:242-253
            acceleration_x = K_P * (values[0] - self.agent.position[0]) + K_V * (0.0 - self.agent.velocity[0])
            acceleration_y = K_P * (values[1] - self.agent.position[1]) + K_V * (0.0 - self.agent.velocity[1])
            self.agent.velocity[0] += acceleration_x * DT           # pusht.py:250
            self.agent.velocity[1] += acceleration_y * DT
            self._physics_step()                                    # pusht.py:253
        coverage = self._coverage()                                 # pusht.py:256
        reward = min(max(coverage / SUCCESS_THRESHOLD, 0.0), 1.0)   # pusht.py:257
        terminated = coverage > SUCCESS_THRESHOLD                   # pusht.py:258
        observation = self._observation()                           # pusht.py:260
        info = self._info()                                         # pusht.py:261
        info["is_success"] = terminated                             # pusht.py:262
        info["coverage"] = coverage                                 # pusht.py:263
        self._ticks += 1
        truncated = self._ticks >= MAX_EPISODE_STEPS                # gym_pusht/__init__.py:6 (the TimeLimit)
        return observation, reward, terminated, truncated, info

    def close(self):
        """``pusht.py:363-366``: only a pygame window is quit, and this fake opens none."""

        return None

    # -- the model (private: gate G7 checks the public surface against PushTEnv) ------------------------------
    def _setup(self):
        """``pusht.py:429-454``: a fresh space with the start poses, gravity 0 and no damping."""

        self.agent = _Body(START_AGENT)                             # pusht.py:445
        self.block = _Body(START_BLOCK)                             # pusht.py:446
        self.goal_pose = [GOAL_POSE[0], GOAL_POSE[1], GOAL_POSE[2]]  # pusht.py:447
        self.n_contact_points = 0                                   # pusht.py:454
        self.teleop = False                                         # pusht.py:433

    def _set_state(self, state):
        """``pusht.py:456-465``: the agent position, then the block position and angle, then one physics step."""

        self.agent.position = [float(state[0]), float(state[1])]
        self.agent.velocity = [0.0, 0.0]
        self.block.position = [float(state[2]), float(state[3])]
        self.block.angle = float(state[4])
        self.block.velocity = [0.0, 0.0]
        self.block.angular_velocity = 0.0
        self._physics_step()

    def _physics_step(self):
        """One substep: the kinematic agent moves, then the contacts, then the dynamic block (pusht.py:244-253)."""

        self.agent.position[0] += self.agent.velocity[0] * DT
        self.agent.position[1] += self.agent.velocity[1] * DT
        self._keep_agent_inside()
        for rectangle in self._block_polygons():
            self._push_block(rectangle)
        self.block.position[0] += self.block.velocity[0] * DT
        self.block.position[1] += self.block.velocity[1] * DT
        self.block.angle += self.block.angular_velocity * DT
        self.block.velocity[0] *= LINEAR_DAMPING
        self.block.velocity[1] *= LINEAR_DAMPING
        self.block.angular_velocity *= ANGULAR_DAMPING
        self._keep_block_inside()

    def _push_block(self, rectangle):
        """The agent circle against one tee rectangle: an approximate contact (pymunk's solver is not modelled)."""

        centre = self.agent.position
        nearest_distance, nearest_point = None, None
        for index in range(len(rectangle)):
            point = _closest_point_on_segment(centre, rectangle[index],
                                              rectangle[(index + 1) % len(rectangle)])
            distance = math.hypot(centre[0] - point[0], centre[1] - point[1])
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance, nearest_point = distance, point
        if _point_in_polygon(centre, rectangle):
            # the agent centre is inside the tee: push the block out through the nearest edge
            away = (centre[0] - nearest_point[0], centre[1] - nearest_point[1])
            length = math.hypot(away[0], away[1])
            if length < 1e-9:
                return
            push = (away[0] / length, away[1] / length)
            penetration = AGENT_RADIUS + nearest_distance
        else:
            if nearest_distance >= AGENT_RADIUS:
                return
            push = ((nearest_point[0] - centre[0]) / nearest_distance,
                    (nearest_point[1] - centre[1]) / nearest_distance)
            penetration = AGENT_RADIUS - nearest_distance
        self.n_contact_points += 1
        self.block.position[0] += push[0] * penetration
        self.block.position[1] += push[1] * penetration
        closing = -(self.agent.velocity[0] * push[0] + self.agent.velocity[1] * push[1])
        if closing <= 0.0:
            return
        impulse = closing * CONTACT_TRANSFER
        self.block.velocity[0] += push[0] * impulse
        self.block.velocity[1] += push[1] * impulse
        offset = (nearest_point[0] - self.block.position[0], nearest_point[1] - self.block.position[1])
        torque = (offset[0] * push[1] - offset[1] * push[0]) * impulse
        self.block.angular_velocity += torque / BLOCK_INERTIA * ANGULAR_TRANSFER

    def _keep_agent_inside(self):
        """The wall segments bound the agent circle; the fake clamps instead of solving the collision."""

        low = WALL_MIN + WALL_RADIUS + AGENT_RADIUS
        high = WALL_MAX - WALL_RADIUS - AGENT_RADIUS
        for axis in (0, 1):
            if self.agent.position[axis] < low:
                self.agent.position[axis] = low
                self.agent.velocity[axis] = max(self.agent.velocity[axis], 0.0)
            elif self.agent.position[axis] > high:
                self.agent.position[axis] = high
                self.agent.velocity[axis] = min(self.agent.velocity[axis], 0.0)

    def _keep_block_inside(self):
        """The wall segments bound the block; an inelastic wall stop keeps it in the 512 x 512 workspace."""

        low = WALL_MIN + WALL_RADIUS
        high = WALL_MAX - WALL_RADIUS
        polygons = self._block_polygons()
        xs = [point[0] for polygon in polygons for point in polygon]
        ys = [point[1] for polygon in polygons for point in polygon]
        shift_x = shift_y = 0.0
        if min(xs) < low:
            shift_x = low - min(xs)
        elif max(xs) > high:
            shift_x = high - max(xs)
        if min(ys) < low:
            shift_y = low - min(ys)
        elif max(ys) > high:
            shift_y = high - max(ys)
        if shift_x:
            self.block.position[0] += shift_x
            self.block.velocity[0] = 0.0
        if shift_y:
            self.block.position[1] += shift_y
            self.block.velocity[1] = 0.0

    def _block_polygons(self):
        """The two tee rectangles in the world, with the body's centre of gravity (pusht.py:511)."""

        return [_world_polygon(rectangle, self.block.position, self.block.angle, BLOCK_COG)
                for rectangle in TEE_RECTS]

    def _goal_polygons(self):
        """The same tee at the goal pose; the goal body has no centre of gravity (pusht.py:403-412)."""

        return [_world_polygon(rectangle, self.goal_pose[:2], self.goal_pose[2], GOAL_COG)
                for rectangle in TEE_RECTS]

    def _coverage(self):
        """``pusht.py:232-238``: the area of the block inside the goal tee over the area of the goal tee."""

        goal_polygons = self._goal_polygons()
        intersection = 0.0
        for block in self._block_polygons():
            for goal in goal_polygons:
                intersection += _intersection_area(block, goal)
        return intersection / TEE_AREA

    def _observation(self):
        """``pusht.py:381-386``: [agent_x, agent_y, block_x, block_y, block_angle] with the angle modulo 2*pi."""

        return [
            self.agent.position[0],
            self.agent.position[1],
            self.block.position[0],
            self.block.position[1],
            self.block.angle % (2 * math.pi),
        ]

    def _info(self):
        """``pusht.py:414-424``: the agent pose and velocity, the block pose, the goal pose and the contact count."""

        return {
            "pos_agent": [self.agent.position[0], self.agent.position[1]],
            "vel_agent": [self.agent.velocity[0], self.agent.velocity[1]],
            "block_pose": [self.block.position[0], self.block.position[1], self.block.angle],
            "goal_pose": list(self.goal_pose),
            "n_contacts": self.n_contact_points,
        }
