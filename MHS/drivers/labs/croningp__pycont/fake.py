"""Fake backend of the pycont driver: an in-memory stand-in for pycont.controller:C3000Controller.

The fake mirrors the public methods of the upstream C3000Controller that this package uses
(pycont/controller.py:339-1243).  It is a recording fake, not the upstream VirtualC3000Controller: the package never
imports or runs the upstream clone.  Volumes are kept in mL like the upstream class (pycont/controller.py:385) and the
plunger position is quantised to the fake's step resolution.  The state never moves by itself; a pump or deliver call
is instantaneous and its result is visible in get_volume()/get_plunger_position().

Every number below is test data of this in-memory stand-in and is marked ``# placeholder``; none of them is a fact,
a limit or a reference.  Nothing here talks to a device.
"""


class FakeC3000Controller:
    """An in-memory C3000 pump with the upstream method names and call signatures."""

    def __init__(self, name="pump", address="1", total_volume=5.0, micro_step_mode=2,
                 top_velocity=6000, initialize_valve_position="I", **_options):
        self.name = name
        self.address = address
        self.total_volume = float(total_volume)        # placeholder: 5.0 mL syringe
        self.micro_step_mode = int(micro_step_mode)    # placeholder: upstream default mode 2
        steps = 3000 if self.micro_step_mode == 0 else 24000   # placeholder: mirrors the upstream step counts
        self.number_of_steps = steps                   # placeholder: 24000 steps in the default mode
        self.steps_per_ml = int(steps / self.total_volume)
        self.default_top_velocity = int(top_velocity)  # placeholder: 6000 steps/s
        self.initialize_valve_position = initialize_valve_position

        self._volume_ml = 2.5                          # placeholder: half-full, so pump and deliver both fit
        self._valve_position = initialize_valve_position
        self._top_velocity = int(top_velocity)         # placeholder: 6000 steps/s
        self._initialized = False
        self._busy = False
        self._eeprom_config = "fake-eeprom"            # placeholder: only a recording stand-in

    # -- state ------------------------------------------------------------------------------------------------
    def get_volume(self):
        """Current volume in the syringe in mL (pycont/controller.py:798-806)."""
        return self._volume_ml

    def get_plunger_position(self):
        """Plunger position in steps (pycont/controller.py:768-778)."""
        return self.volume_to_step(self._volume_ml)

    def is_idle(self):
        return not self._busy

    def is_busy(self):
        return self._busy

    def is_initialized(self):
        return self._initialized

    def get_top_velocity(self):
        return self._top_velocity

    def get_default_top_velocity(self):
        return self.default_top_velocity

    def get_valve_position(self, max_repeat=10):
        return self._valve_position

    def get_raw_valve_position(self):
        return {"I": "i", "O": "o", "B": "b", "E": "e"}.get(self._valve_position, self._valve_position)

    def get_eeprom_config(self):
        return self._eeprom_config

    # -- conversion -------------------------------------------------------------------------------------------
    def volume_to_step(self, volume_in_ml):
        return int(round(float(volume_in_ml) * self.steps_per_ml))

    def step_to_volume(self, step):
        return step / float(self.steps_per_ml)

    def is_volume_pumpable(self, volume_in_ml):
        return self.volume_to_step(volume_in_ml) <= self.number_of_steps - self.get_plunger_position()

    def is_volume_deliverable(self, volume_in_ml):
        return self.volume_to_step(volume_in_ml) <= self.get_plunger_position()

    # -- commands ---------------------------------------------------------------------------------------------
    def set_valve_position(self, valve_position, max_repeat=10, secure=True):
        if valve_position not in ("I", "O", "B", "E", "1", "2", "3", "4", "5", "6"):
            raise ValueError("Valve position {} unknown".format(valve_position))
        self._valve_position = valve_position
        return True

    def set_top_velocity(self, top_velocity, max_repeat=10, secure=True):
        self._top_velocity = int(top_velocity)
        return True

    def set_default_top_velocity(self, top_velocity):
        self.default_top_velocity = int(top_velocity)

    def set_microstep_mode(self, micro_step_mode):
        self.micro_step_mode = int(micro_step_mode)

    def init_all_pump_parameters(self, secure=True):
        self.set_microstep_mode(self.micro_step_mode)
        self.set_top_velocity(self.default_top_velocity, secure=secure)

    def pump(self, volume_in_ml, from_valve=None, speed_in=None, wait=False, secure=True):
        """Aspirate into the syringe; the sign is the upstream one (pycont/controller.py:845-888)."""
        if not self.is_volume_pumpable(volume_in_ml):
            return False
        if from_valve is not None:
            self.set_valve_position(from_valve, secure=secure)
        if speed_in is not None:
            self.set_top_velocity(speed_in, secure=secure)
        self._volume_ml = self.step_to_volume(self.get_plunger_position() + self.volume_to_step(volume_in_ml))
        return True

    def deliver(self, volume_in_ml, to_valve=None, speed_out=None, wait=False, secure=True):
        """Dispense from the syringe; the sign is the upstream one (pycont/controller.py:906-947)."""
        if not self.is_volume_deliverable(volume_in_ml):
            return False
        if to_valve is not None:
            self.set_valve_position(to_valve, secure=secure)
        if speed_out is not None:
            self.set_top_velocity(speed_out, secure=secure)
        self._volume_ml = self.step_to_volume(self.get_plunger_position() - self.volume_to_step(volume_in_ml))
        return True

    def go_to_volume(self, volume_in_ml, speed=None, wait=False, secure=True):
        if not 0 <= float(volume_in_ml) <= self.total_volume:
            return False
        self._volume_ml = self.step_to_volume(self.volume_to_step(volume_in_ml))
        return True

    def wait_until_idle(self):
        return None

    def terminate(self):
        """Stop the current action (pycont/controller.py:1239-1243)."""
        self._busy = False
