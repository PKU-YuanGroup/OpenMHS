"""Fake backend of the Fixedwing-Airsim driver: a protocol stand-in for ``SingleObservation``.

Why a fake: the gate never imports the upstream clone and the upstream environment needs the AirSim runtime, JSBSim
and a JSBSim aircraft directory (README.md:6-10).  This module implements the public environment surface of
``envs.single_observation:SingleObservation`` (``action_space``, ``observation_space``, ``reset``, ``step``, ``seed``,
``render``) with the same action bounds and the same reward/termination rule, but no flight dynamics.  Every constant
that comes from the clone cites its line at the pinned commit c5054486fb05dc67668b123c7789e399c8d4ce02; every number
invented for the stand-in is marked ``# placeholder``.

What this is not: the upstream environment.  Differences, all in the fidelity ``gaps`` of driver.py:

* steps advance a counter, not a JSBSim FDM; there is no AirSim pose update and no collision geometry;
* the observation is a 3 x 8 x 8 placeholder image.  Upstream reshapes the AirSim Scene response to
  ``(3, image_response.height, image_response.width)`` (src/image_processing.py:49), a runtime size the clone does not
  fix, so the fake cannot name the real size;
* the collision is an invented schedule: the fake reports an airport collision on step 50 instead of reading AirSim's
  collision information;
* the seed is stored and returned but does not change the reset state, like the upstream seed method.

Nothing here talks to a device.
"""

# Upstream values of SingleObservation.__init__ (src/envs/single_observation.py:47-79).
MAX_SIM_TIME_S = 100.0          # src/envs/single_observation.py:47
AIRSPEED_M_S = 50.0             # src/envs/single_observation.py:49
AIRSIM_FREQUENCY_HZ = 48.0      # src/envs/single_observation.py:50
JSBSIM_FREQUENCY_HZ = 240.0     # src/envs/single_observation.py:51
AIRCRAFT_ID = "x8"              # src/envs/single_observation.py:52 (upstream carries the Aircraft namedtuple)
MAX_HDG_DEG = 45.0              # src/envs/single_observation.py:62
MIN_HDG_DEG = -45.0             # src/envs/single_observation.py:63
MAX_PITCH_DEG = 0.0             # src/envs/single_observation.py:64
MIN_PITCH_DEG = -30.0           # src/envs/single_observation.py:65

#: placeholder: the real shape is (3, runtime height, runtime width) from AirSim (src/image_processing.py:49);
#: the fake keeps the three channels and a small array so receipts stay short.
IMAGE_SHAPE = (3, 8, 8)
#: placeholder: the fake reports an airport collision on this step.  The clone has no fixed collision schedule; it
#: reads AirSim's collision_info every step (src/envs/single_observation.py:93-100).
COLLISION_STEP = 50


class Box:
    """Duck-typed ``spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = low
        self.high = high
        if shape is not None:
            self.shape = tuple(shape)
        elif isinstance(low, (list, tuple)):
            self.shape = (len(low),)
        else:
            self.shape = ()
        self.dtype = dtype


class _CollisionInfo:
    """The two members ``SingleObservation.step`` reads from AirSim's collision info."""

    def __init__(self, has_collided, object_name):
        self.has_collided = has_collided
        self.object_name = object_name


class FakeSingleObservation:
    """The public environment surface of ``SingleObservation`` without JSBSim, AirSim or numpy."""

    def __init__(self, **_options):
        self.max_sim_time = MAX_SIM_TIME_S
        self.display_graphics = True
        self.airspeed = AIRSPEED_M_S
        self.airsim_frequency_hz = AIRSIM_FREQUENCY_HZ
        self.jsbsim_frequency_hz = JSBSIM_FREQUENCY_HZ
        self.aircraft = AIRCRAFT_ID
        self.init_conditions = None
        self.debug_level = 0
        self.max_hdg = MAX_HDG_DEG
        self.min_hdg = MIN_HDG_DEG
        self.max_pitch = MAX_PITCH_DEG
        self.min_pitch = MIN_PITCH_DEG
        self.action_space = Box([self.min_hdg, self.min_pitch], [self.max_hdg, self.max_pitch], shape=(2,))
        self.observation_space = Box(0, 255, shape=IMAGE_SHAPE, dtype="uint8")
        self.over = False
        self.graphic_update = 0
        self.max_updates = int(self.max_sim_time * self.jsbsim_frequency_hz)
        self.relative_update = self.airsim_frequency_hz / self.jsbsim_frequency_hz
        self.id = 0
        self.desired_heading = 0
        self.desired_pitch = 0
        self._seed = None

    def seed(self, seed=None):
        """Upstream forwards this to ``gym.utils.seeding.np_random`` (src/envs/single_observation.py:81-83)."""
        self._seed = seed
        return [seed]

    def step(self, action):
        """Mirror the upstream step order: image, collision, graphics tick, one physics update."""
        self.desired_heading, self.desired_pitch = action
        observation = self._image()
        graphic_i = self.relative_update * self.id
        graphic_update_old = self.graphic_update
        self.graphic_update = graphic_i // 1.0
        collision = self._collision_info()
        done = False
        reward = 0
        if collision.has_collided:
            done = True
            if collision.object_name == "airport":
                reward = 1
        if self.display_graphics and self.graphic_update > graphic_update_old:
            pass  # placeholder: the AirSim pose update (src/jsbsim_simulator.py:235-248) is not modelled
        self.id = self.id + 1
        return observation, reward, done, {}

    def reset(self):
        """Mirror the upstream reset: counters reset and the simulation starts from its initial conditions.

        The upstream signature takes no seed or options.  The bridge therefore follows the legacy Gym path
        (``env.seed(seed)`` then ``env.reset()``) when a reset carries a seed; ``seed`` stores it below.
        """
        self.graphic_update = 0
        self.max_updates = int(self.max_sim_time * self.jsbsim_frequency_hz)
        self.relative_update = self.airsim_frequency_hz / self.jsbsim_frequency_hz
        self.id = 0
        self.desired_heading = 0
        self.desired_pitch = 0
        self.over = False
        return self._image(), {}

    def render(self, mode="human"):
        """Upstream renders through UE4 and returns None."""
        return None

    def _image(self):
        """A placeholder Scene image; upstream returns the AirSim response (src/image_processing.py:41-50)."""
        channels = []
        for channel in range(IMAGE_SHAPE[0]):
            rows = []
            for row_index in range(IMAGE_SHAPE[1]):
                row = []
                for column in range(IMAGE_SHAPE[2]):
                    # placeholder: 7, 31, 17 and 13 only spread the counter over the pixel range
                    value = (self.id * 7 + channel * 31 + row_index * 17 + column * 13
                             + int(self.desired_heading)) % 256
                    row.append(value)
                rows.append(row)
            channels.append(rows)
        return channels

    def _collision_info(self):
        """placeholder: a fixed airport collision instead of AirSim's collision_info."""
        if self.id + 1 >= COLLISION_STEP:
            return _CollisionInfo(True, "airport")
        return _CollisionInfo(False, "")
