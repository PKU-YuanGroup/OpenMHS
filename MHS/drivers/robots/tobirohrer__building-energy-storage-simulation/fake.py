"""Fake backend of the Building Energy Storage Simulation driver: pure Python stand-ins for the upstream classes.

Why a fake: gymnasium is not importable where the gate runs and package code never imports the clone, so this module
re-implements the observable behaviour of ``building_energy_storage_simulation.environment:Environment`` (the class
the driver names as ``native``) together with the two in-memory classes it wraps:
``building_energy_storage_simulation.building_simulation:BuildingSimulation`` and
``building_energy_storage_simulation.battery:Battery``.  The energy arithmetic, the reward, the observation layout,
the action handling and the termination rule follow the lines cited in ``driver.py`` and ``facts.md``.

The public members of ``FakeEnvironment`` are the ones ``Environment`` has (``reset``, ``step``, ``render``,
``get_observation`` and the static ``calc_reward``; gate G7).  The helper ``Box`` duck-types
``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape`` from the two spaces.

Every number in this module is test data, not a fact: the synthetic profile rows, the constructor defaults and the
noise constants are placeholders, marked ``# placeholder`` below, and none of them is copied into a ``Fact``, a
``Limit`` or the reference.  Differences from the upstream environment, all listed in the driver's fidelity ``gaps``:

* the profile rows are synthesized instead of loaded from the package's CSV files;
* a seed supplied to ``reset`` seeds this fake's private ``random.Random`` (upstream ignores the seed and draws a
  randomized start from numpy's global generator);
* observations are plain Python float lists; upstream concatenates numpy arrays and returns an ``np.ndarray``;
* there is no gymnasium wrapper, no ``PassiveEnvChecker`` and no rendering (upstream ``render`` is a no-op too).

Nothing here talks to a device.
"""

import math
import random

# placeholder: the length of the synthesized profiles, mirroring the default profile length only as test data.
PROFILE_LENGTH = 8760
# placeholder: battery defaults used by the fake simulation when the caller passes none.
BATTERY_CAPACITY = 100.0
MAX_BATTERY_CHARGE_PER_TIMESTEP = 20.0
# placeholder: the fake environment's own step limit and forecast length when the caller passes none.
MAX_TIMESTEPS = 2000
NUM_FORECASTING_STEPS = 4
# placeholder: the upstream forecast-noise defaults, kept only so the fake has the same knobs as the class.
NOISE_START = 0.2
NOISE_END = 1.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element of a fixed shape."""

    def __init__(self, low, high, shape):
        self.shape = tuple(int(item) for item in shape)
        count = 1
        for item in self.shape:
            count *= item
        self.low = [float(low)] * count if not hasattr(low, "__len__") else [float(item) for item in low]
        self.high = [float(high)] * count if not hasattr(high, "__len__") else [float(item) for item in high]
        self.dtype = "float32"

    def contains(self, value):
        try:
            values = list(value) if hasattr(value, "__len__") else [value]
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            low <= float(item) <= high for item, low, high in zip(values, self.low, self.high))


class Battery:
    """``building_energy_storage_simulation.battery.Battery`` in pure Python (battery.py:14-58)."""

    def __init__(self, capacity=BATTERY_CAPACITY, initial_state_of_charge=0.0,
                 max_battery_charge_per_timestep=MAX_BATTERY_CHARGE_PER_TIMESTEP):
        self.max_battery_charge_per_timestep = float(max_battery_charge_per_timestep)   # placeholder value
        self.capacity = float(capacity)                                                  # placeholder value
        self.initial_state_of_charge = float(initial_state_of_charge)                    # placeholder value
        self.state_of_charge = float(initial_state_of_charge)

    def use(self, amount):
        """Charge (positive) or discharge (negative) by ``amount`` kWh; return the energy actually moved."""
        amount = float(amount)
        if amount > self.max_battery_charge_per_timestep:                               # battery.py:35-38
            amount = self.max_battery_charge_per_timestep
        if amount < -1 * self.max_battery_charge_per_timestep:
            amount = -1 * self.max_battery_charge_per_timestep
        if self.state_of_charge + amount < 0:                                           # battery.py:41-43
            electricity_used = self.state_of_charge
            self.state_of_charge = 0.0
        elif self.state_of_charge + amount > self.capacity:                             # battery.py:46-48
            electricity_used = self.capacity - self.state_of_charge
            self.state_of_charge = self.capacity
        else:                                                                          # battery.py:49-51
            electricity_used = amount
            self.state_of_charge += amount
        return electricity_used

    def reset(self):
        self.state_of_charge = self.initial_state_of_charge                             # battery.py:54-58


def _synthetic_profiles(length):
    """Three profile rows of ``length`` values: synthesized test data, not the upstream CSV data.

    The shapes are arbitrary (a daily cycle for the load and the solar series, a price that follows the load);
    every constant here is a placeholder.
    """
    load, solar, price = [], [], []
    for index in range(int(length)):
        hour = index % 24                                                              # placeholder
        load.append(0.8 + 0.3 * math.sin(2 * math.pi * hour / 24.0))                    # placeholder
        solar.append(max(0.0, 1.5 * math.sin(2 * math.pi * (hour - 6) / 24.0)))         # placeholder
        price.append(20.0 + 5.0 * math.cos(2 * math.pi * hour / 24.0))                  # placeholder
    return load, solar, price


class BuildingSimulation:
    """``building_energy_storage_simulation.building_simulation.BuildingSimulation`` in pure Python."""

    def __init__(self, electricity_load_profile=None, solar_generation_profile=None, electricity_price=None,
                 battery_capacity=BATTERY_CAPACITY,
                 max_battery_charge_per_timestep=MAX_BATTERY_CHARGE_PER_TIMESTEP):
        if electricity_load_profile is None and solar_generation_profile is None and electricity_price is None:
            electricity_load_profile, solar_generation_profile, electricity_price = _synthetic_profiles(
                PROFILE_LENGTH)
        elif electricity_load_profile is None or solar_generation_profile is None or electricity_price is None:
            raise ValueError("the fake needs the load, solar and price profiles together, or none of them")
        self.electricity_load_profile = [float(item) for item in electricity_load_profile]      # sim.py:35-36
        self.solar_generation_profile = [float(item) for item in solar_generation_profile]
        if isinstance(electricity_price, (float, int)):                                         # sim.py:38-41
            self.electricity_price = [float(electricity_price)] * len(self.solar_generation_profile)
        else:
            self.electricity_price = [float(item) for item in electricity_price]
        self._check_data_profiles_same_length()                                                 # sim.py:43,99-103
        self.battery = Battery(capacity=battery_capacity,                                       # sim.py:45-46
                               max_battery_charge_per_timestep=max_battery_charge_per_timestep)
        self.step_count = 0                                                                     # sim.py:48-49
        self.start_index = 0

    def reset(self):
        self.battery.reset()                                                                    # sim.py:51-61
        self.step_count = 0

    def simulate_one_step(self, action):
        """Apply ``action`` times the maximum charge per step and return (consumption, price)."""
        index = self.start_index + self.step_count
        electricity_load_this_timestep = self.electricity_load_profile[index]                    # sim.py:86-88
        solar_generation_this_timestep = self.solar_generation_profile[index]
        electricity_price_this_timestep = self.electricity_price[index]
        consumed_for_battery = self.battery.use(float(action) *                                  # sim.py:90
                                                self.battery.max_battery_charge_per_timestep)
        consumption = (consumed_for_battery + electricity_load_this_timestep
                       - solar_generation_this_timestep)                                         # sim.py:91-92
        if consumption < 0:                                                                      # sim.py:94-95
            consumption = 0.0
        self.step_count += 1                                                                     # sim.py:96
        return float(consumption), float(electricity_price_this_timestep)

    def _check_data_profiles_same_length(self):
        if not (len(self.solar_generation_profile) == len(self.electricity_load_profile)
                == len(self.electricity_price)):
            raise ValueError('Data profiles passed to simulation are not of the same length.')


class FakeEnvironment:
    """``Environment`` without gymnasium or numpy: ``reset(seed, options)`` and ``step(action)`` as upstream."""

    def __init__(self, building_simulation=None, max_timesteps=MAX_TIMESTEPS,
                 num_forecasting_steps=NUM_FORECASTING_STEPS, randomize_start_time_step=False,
                 randomize_forecasts_in_observation=False, electricity_load_profile=None,
                 solar_generation_profile=None, electricity_price=None, battery_capacity=BATTERY_CAPACITY,
                 max_battery_charge_per_timestep=MAX_BATTERY_CHARGE_PER_TIMESTEP, profile_length=PROFILE_LENGTH,
                 seed=None):
        if building_simulation is None:
            if electricity_load_profile is None and solar_generation_profile is None and electricity_price is None:
                electricity_load_profile, solar_generation_profile, electricity_price = _synthetic_profiles(
                    profile_length)
            building_simulation = BuildingSimulation(
                electricity_load_profile=electricity_load_profile,
                solar_generation_profile=solar_generation_profile, electricity_price=electricity_price,
                battery_capacity=battery_capacity,
                max_battery_charge_per_timestep=max_battery_charge_per_timestep,
            )
        self.building_simulation = building_simulation                                          # environment.py:35-40
        self.max_timesteps = int(max_timesteps)
        self.num_forecasting_steps = int(num_forecasting_steps)
        self.randomize_start_time_step = bool(randomize_start_time_step)
        self.randomize_forecasts_in_observation = bool(randomize_forecasts_in_observation)
        self.data_profile_length = len(self.building_simulation.solar_generation_profile)
        if self.max_timesteps + self.num_forecasting_steps > self.data_profile_length:          # environment.py:42-43
            raise AssertionError("`max_timesteps` plus the forecast length cannot be greater than the length of "
                                 "the data profiles.")
        self.action_space = Box(-1.0, 1.0, (1,))                                                # environment.py:45
        self.observation_space = Box(-math.inf, math.inf,                                        # environment.py:49-52
                                     (self.num_forecasting_steps * 3 + 1,))
        # placeholder/test data: the fake's private RNG, used only for the optional random start and forecast noise.
        self._rng = random.Random(seed)
        self._seed = None if seed is None else int(seed)

    def render(self):
        """Not implemented, as upstream (environment.py:54-59)."""
        return None

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
            self._seed = int(seed)
        self.building_simulation.reset()                                                        # environment.py:73
        if self.randomize_start_time_step:                                                      # environment.py:74-76
            latest_possible_start_time_step = (self.data_profile_length - self.max_timesteps
                                               - self.num_forecasting_steps)
            if latest_possible_start_time_step > 0:
                self.building_simulation.start_index = int(
                    self._rng.uniform(0, latest_possible_start_time_step))
                if self.building_simulation.start_index >= latest_possible_start_time_step:
                    self.building_simulation.start_index = latest_possible_start_time_step - 1
            else:
                self.building_simulation.start_index = 0
        return self.get_observation(), {}

    def step(self, action):
        if hasattr(action, "__len__"):                                                          # environment.py:104-105
            action = action[0]
        consumption, price = self.building_simulation.simulate_one_step(action)                 # environment.py:106
        reward = self.calc_reward(consumption, price)                                            # environment.py:107
        observation = self.get_observation()                                                     # environment.py:108
        return observation, reward, self._get_terminated(), False, {                             # environment.py:109-110
            'electricity_consumption': consumption, 'electricity_price': price}

    def _get_terminated(self):
        return self.building_simulation.step_count >= self.max_timesteps                         # environment.py:112-115

    def get_observation(self):
        current_index = self.building_simulation.start_index + self.building_simulation.step_count
        simulation = self.building_simulation
        load = simulation.electricity_load_profile[current_index:
                                                   current_index + self.num_forecasting_steps]
        solar = simulation.solar_generation_profile[current_index:
                                                    current_index + self.num_forecasting_steps]
        price = simulation.electricity_price[current_index:
                                             current_index + self.num_forecasting_steps]
        if self.randomize_forecasts_in_observation:                                             # environment.py:124-127
            load = self._randomize_forecast(load)
            solar = self._randomize_forecast(solar)
            price = self._randomize_forecast(price)
        return [float(simulation.battery.state_of_charge)] + list(load) + list(solar) + list(price)

    def _randomize_forecast(self, forecast, standard_deviation_start=NOISE_START,
                            standard_deviation_end=NOISE_END):
        gamma = standard_deviation_end - standard_deviation_start                                # environment.py:140
        randomized = []
        for index, value in enumerate(forecast):
            std = standard_deviation_end - gamma ** index                                       # environment.py:142
            randomized.append(value + self._rng.normalvariate(0, std))
        return randomized

    @staticmethod
    def calc_reward(electricity_consumption, electricity_price):
        return -1 * float(electricity_consumption) * float(electricity_price)                   # environment.py:147-148
