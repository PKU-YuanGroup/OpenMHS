"""Fake backend of the drone_sim driver: the upstream environment without gym, numpy or matplotlib.

Why a fake: the acceptance gate must not import or install the upstream clone, and ``gym``/``numpy``/``matplotlib``
are not part of the SDK.  This module re-implements the public surface of
``drone_sim.gym.simple_drone_env:SimpleDroneEnv`` (the class the driver names as ``native``) and the rigid-body
update of ``drone_sim.sim.drone:Drone`` in pure Python.  Gate G7 checks the public members of
``FakeSimpleDroneEnv`` against that upstream class: this class defines only ``reset``, ``step``, ``render`` and
``dist``, the four public methods SimpleDroneEnv has (plus ``metadata``, a class attribute).

Every constant and rule below cites the line of the clone at the pinned commit
(1a324f178a5719676bdb0caaa2a2d545a7158fdd).  The two space classes duck-type ``gym.spaces.Box`` enough for the
gymnasium bridge (``low``, ``high``, ``shape``, ``dtype``, ``contains``).

What this is not: the upstream environment.  The differences are listed in the fidelity ``gaps`` of driver.py:

* no rendering (``render`` is a no-op here; upstream calls the matplotlib Graphics);
* observations are nested Python lists, not a numpy float32 array;
* no sensor models are attached (upstream SimpleDroneEnv does not attach the IMU/GPS either);
* the fake was not compared with a run of the upstream environment.

Nothing here talks to a device.
"""

import math

# drone_sim/sim/parameters.py:4 -- simulation step in seconds
DT = 0.004
# drone_sim/sim/parameters.py:8-13 -- drone parameters
MASS = 0.468
K = 2.980e-6
B = 1.140e-7
L = 0.225
G = 9.8
# drone_sim/sim/parameters.py:15 -- the factor the environment applies to a normalized action value
NULL_ROT = 620.2943
# drone_sim/sim/parameters.py:18-20 -- inertia
IXX = 4.856e-3
IYY = 4.856e-3
IZZ = 8.801e-3
# drone_sim/sim/parameters.py:23-25 -- drag
AX = 0.25
AY = 0.25
AZ = 0.25
# drone_sim/gym/simple_drone_env.py:65 -- the roll/pitch limit in degrees
TILT_LIMIT_RAD = math.radians(60.0)
# drone_sim/gym/simple_drone_env.py:76 -- the distance at which the episode is done
GOAL_DISTANCE = 0.01
# drone_sim/gym/simple_drone_env.py:19,28 -- the environment's start height and init_position
INIT_POSITION = [0.0, 0.0, 2.0]
# drone_sim/sim/drone.py:104 -- the position Drone.__reset__ restores
RESET_POSITION = [0.0, 0.0, 0.5]


def _matrix_vector(matrix, vector):
    return [sum(matrix[row][column] * vector[column] for column in range(3)) for row in range(3)]


def _matrix_matrix(left, right):
    return [[sum(left[row][k] * right[k][column] for k in range(3)) for column in range(3)]
            for row in range(3)]


class Box:
    """Duck-typed ``gym.spaces.Box``: a scalar or per-element lower and upper bound and a shape."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(int(item) for item in shape)
        self.dtype = dtype

    @property
    def size(self):
        total = 1
        for item in self.shape:
            total *= item
        return total

    def contains(self, value):
        try:
            values = [float(item) for item in value]
        except (TypeError, ValueError):
            return False
        if len(values) != self.size:
            return False
        lows = self.low if isinstance(self.low, (list, tuple)) else [self.low] * len(values)
        highs = self.high if isinstance(self.high, (list, tuple)) else [self.high] * len(values)
        return all(float(low) <= item <= float(high) for item, low, high in zip(values, lows, highs))


class _FakeDrone:
    """Pure-Python ``drone_sim.sim.drone:Drone``: the same state fields and the same update order."""

    def __init__(self, x=0.0, y=0.0, z=0.5, enable_death=True):
        # drone_sim/sim/drone.py:6-28
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.phi, self.theta, self.psi = 0.0, 0.0, 0.0
        self.vx, self.vy, self.vz = 0.0, 0.0, 0.0
        self.p, self.q, self.r = 0.0, 0.0, 0.0
        self.w1 = self.w2 = self.w3 = self.w4 = 0.0
        self.acceleration = [0.0, 0.0, 0.0]
        self.sensors = []
        self.body = None
        self.enable_death = bool(enable_death)

    def __reset__(self):
        """``Drone.__reset__`` (drone_sim/sim/drone.py:101-115): acceleration is not restored."""
        self.x, self.y, self.z = RESET_POSITION
        self.phi, self.theta, self.psi = 0.0, 0.0, 0.0
        self.vx, self.vy, self.vz = 0.0, 0.0, 0.0
        self.p, self.q, self.r = 0.0, 0.0, 0.0

    def step(self, velocities):
        """``Drone.step`` (drone_sim/sim/drone.py:117-125)."""
        self.w1, self.w2, self.w3, self.w4 = (float(velocities[0]), -float(velocities[1]),
                                              float(velocities[2]), -float(velocities[3]))
        self.update()
        if self.enable_death:
            self.death()

    def update(self):
        """``Drone.update`` (drone_sim/sim/drone.py:199-228), in the upstream order."""
        # __update_transformations__ (drone.py:128-161): R = R_phi @ R_theta @ R_psi
        cos_phi, sin_phi = math.cos(self.phi), math.sin(self.phi)
        cos_theta, sin_theta = math.cos(self.theta), math.sin(self.theta)
        cos_psi, sin_psi = math.cos(self.psi), math.sin(self.psi)
        r_phi = [[cos_phi, -sin_phi, 0.0], [sin_phi, cos_phi, 0.0], [0.0, 0.0, 1.0]]
        r_theta = [[1.0, 0.0, 0.0], [0.0, cos_theta, -sin_theta], [0.0, sin_theta, cos_theta]]
        r_psi = [[cos_psi, -sin_psi, 0.0], [sin_psi, cos_psi, 0.0], [0.0, 0.0, 1.0]]
        rotation = _matrix_matrix(_matrix_matrix(r_phi, r_theta), r_psi)

        # __update_thrust_and_torque__ (drone.py:163-181)
        w1, w2, w3, w4 = self.w1, self.w2, self.w3, self.w4
        thrust_z = K * (w1 ** 2 + w2 ** 2 + w3 ** 2 + w4 ** 2)
        torque = [L * K * (w1 ** 2 - w3 ** 2),
                  L * K * (w2 ** 2 - w4 ** 2),
                  B * (w1 ** 2 - w2 ** 2 + w3 ** 2 - w4 ** 2)]
        drag_force = [-AX * self.vx, -AY * self.vy, -AZ * self.vz]

        # __update_acceleration__ (drone.py:183-185): gravity + R*thrust/mass + drag/mass
        rotated_thrust = _matrix_vector(rotation, [0.0, 0.0, thrust_z])
        self.acceleration = [rotated_thrust[0] / MASS + drag_force[0] / MASS,
                             rotated_thrust[1] / MASS + drag_force[1] / MASS,
                             -G + rotated_thrust[2] / MASS + drag_force[2] / MASS]

        # __update_omega_dot__ (drone.py:187-197): p, q, r become the angular acceleration
        angular = [self.p, self.q, self.r]
        inertia_angular = [IXX * angular[0], IYY * angular[1], IZZ * angular[2]]
        cross = [angular[1] * inertia_angular[2] - angular[2] * inertia_angular[1],
                 angular[2] * inertia_angular[0] - angular[0] * inertia_angular[2],
                 angular[0] * inertia_angular[1] - angular[1] * inertia_angular[0]]
        moment = [torque[0] - cross[0], torque[1] - cross[1], torque[2] - cross[2]]
        self.p, self.q, self.r = moment[0] / IXX, moment[1] / IYY, moment[2] / IZZ

        # drone.py:209-228: Euler integration; the position uses the velocities updated just above
        self.phi = self.normalise_theta(self.phi + self.p * DT)
        self.theta = self.normalise_theta(self.theta + self.q * DT)
        self.psi = self.normalise_theta(self.psi + self.r * DT)
        self.vx += self.acceleration[0] * DT
        self.vy += self.acceleration[1] * DT
        self.vz += self.acceleration[2] * DT
        self.x += self.vx * DT
        self.y += self.vy * DT
        self.z += self.vz * DT

    def normalise_theta(self, angle):
        """``Drone.normalise_theta`` (drone_sim/sim/drone.py:231-241), including its two loops."""
        if angle > math.pi:
            while angle > math.pi:
                angle -= 2 * math.pi
            return angle
        if angle < -math.pi:
            while angle < math.pi:
                angle += 2 * math.pi
            return angle
        return angle

    def death(self):
        """``Drone.death`` (drone_sim/sim/drone.py:259-269); the environment constructs the drone with it off."""
        if abs(self.phi) > TILT_LIMIT_RAD or abs(self.theta) > TILT_LIMIT_RAD:
            self.__reset__()
        if self.z < 0:
            self.__reset__()


class FakeSimpleDroneEnv:
    """The public surface of ``drone_sim.gym.simple_drone_env:SimpleDroneEnv`` in pure Python."""

    metadata = {"render.modes": ["human"]}                      # simple_drone_env.py:12

    def __init__(self, goal_position=(0.0, 5.0, 5.0)):           # simple_drone_env.py:14
        # simple_drone_env.py:19-40
        self.drone = _FakeDrone(0.0, 0.0, 2.0, enable_death=False)
        self.body = None                                         # upstream: Body() from drone_sim.viz
        self.ui = None                                           # upstream: Graphics() from drone_sim.viz
        self.goal_position = [float(item) for item in goal_position]
        self.init_position = list(INIT_POSITION)
        self.obs_low = -math.inf
        self.obs_high = -math.inf
        self.action_space = Box(low=0.0, high=1.0, shape=(4,), dtype="float32")
        self.observation_space = Box(low=self.obs_low, high=self.obs_high, shape=(3, 3), dtype="float32")
        self.reward_range = (0, 100)
        self.NULL_ROT = NULL_ROT

    def _observation(self):
        """simple_drone_env.py:50-56 and :89-95."""
        drone = self.drone
        return [[drone.x, drone.y, drone.z],
                [drone.acceleration[0], drone.acceleration[1], drone.acceleration[2]],
                [drone.p, drone.q, drone.r]]

    def step(self, action):
        """simple_drone_env.py:42-84."""
        assert self.action_space.contains(action), f"{action} doesnot exist in the action space"
        # simple_drone_env.py:45-46: the action is (w1, w2, w3, w4) scaled by NULL_ROT
        self.drone.step([float(item) * self.NULL_ROT for item in action])
        observation = self._observation()
        # simple_drone_env.py:58-62: both distances are measured from init_position
        dist_to_go = self.dist([self.drone.x, self.drone.y, self.drone.z], self.init_position)
        total_dist = self.dist(self.goal_position, self.init_position)
        reward = 1 - dist_to_go / total_dist
        # simple_drone_env.py:64-81
        if abs(self.drone.phi) > TILT_LIMIT_RAD or abs(self.drone.theta) > TILT_LIMIT_RAD:
            done = True
            self.drone.__reset__()
            reward -= 5
        elif self.drone.z < 0:
            done = True
            self.drone.__reset__()
            reward -= 5
        elif dist_to_go < GOAL_DISTANCE:
            done = True
            reward += 10
        else:
            done = False
        return observation, reward, done, {}                     # simple_drone_env.py:84 (legacy four-value API)

    def reset(self):
        """simple_drone_env.py:86-97: no seed and no options in the upstream signature."""
        self.drone.__reset__()
        return self._observation()

    def render(self):
        """simple_drone_env.py:99-101 calls the matplotlib user interface; the fake has none."""
        return None

    def dist(self, x1, x2):
        """simple_drone_env.py:104-108."""
        x, y, z = x1
        goal_x, goal_y, goal_z = x2
        return math.sqrt((x - goal_x) ** 2 + (y - goal_y) ** 2 + (z - goal_z) ** 2)
