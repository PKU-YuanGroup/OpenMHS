"""Fake backend of the Zaber stage driver: an in-memory stand-in for zaber_device.zaber_device:ZaberStage.

Gate G7: every public method defined here exists on the upstream ``ZaberStage`` class
(``zaber_device/zaber_device.py:721-1251``).  The private state is one Zaber device with three actuators, already
mapped to the x, y and z axes.  Every number below is test data and is marked ``# placeholder``; none is a fact or a
bound of any stage.  Moves complete immediately and nothing here talks to a device.
"""


class FakeZaberStage:
    def __init__(self, **_options):
        self._position = [0.0, 0.0, 0.0]                    # placeholder, in microsteps
        self._stored = {}                                   # address -> microsteps, test data
        self._microstep = [1.0, 1.0, 1.0]                   # placeholder
        self._travel = [100.0, 100.0, 100.0]                # placeholder
        self._actuator_ids = [1001, 1002, 1003]             # placeholder
        self._homed = [False, False, False]                 # placeholder
        self._moving = [False, False, False]                # placeholder

    def _microsteps(self, index, value):
        return float(value) / self._microstep[index]

    def _move_absolute(self, index, position):
        microsteps = self._microsteps(index, position)
        if microsteps < 0:
            return  # ZaberDevice.move_absolute ignores a negative target (zaber_device.py:312-318)
        self._position[index] = microsteps

    def _move_relative(self, index, distance):
        self._position[index] += self._microsteps(index, distance)

    def _store_position(self, index, address):
        entry = self._stored.setdefault(int(address), [0.0, 0.0, 0.0])
        entry[index] = self._position[index]

    def _stored_position(self, index, address):
        entry = self._stored.get(int(address), [0.0, 0.0, 0.0])
        return entry[index] * self._microstep[index]

    def _move_to_stored_position(self, index, address):
        entry = self._stored.get(int(address), [0.0, 0.0, 0.0])
        self._position[index] = entry[index]

    # -- reads -----------------------------------------------------------------------------------------------------
    def get_actuator_ids(self):
        return tuple(self._actuator_ids)

    def get_positions(self):
        return [self._position[index] * self._microstep[index] for index in range(3)]

    def get_x_microstep_size(self):
        return self._microstep[0]

    def get_y_microstep_size(self):
        return self._microstep[1]

    def get_z_microstep_size(self):
        return self._microstep[2]

    def get_x_travel(self):
        return self._travel[0]

    def get_y_travel(self):
        return self._travel[1]

    def get_z_travel(self):
        return self._travel[2]

    def get_stored_x_position(self, address):
        return self._stored_position(0, address)

    def get_stored_y_position(self, address):
        return self._stored_position(1, address)

    def get_stored_z_position(self, address):
        return self._stored_position(2, address)

    def homed(self):
        return tuple(self._homed)

    # -- writes ----------------------------------------------------------------------------------------------------
    def set_x_microstep_size(self, microstep_size):
        self._microstep[0] = float(microstep_size)

    def set_y_microstep_size(self, microstep_size):
        self._microstep[1] = float(microstep_size)

    def set_z_microstep_size(self, microstep_size):
        self._microstep[2] = float(microstep_size)

    def set_x_travel(self, travel):
        self._travel[0] = float(travel)

    def set_y_travel(self, travel):
        self._travel[1] = float(travel)

    def set_z_travel(self, travel):
        self._travel[2] = float(travel)

    # -- actions ---------------------------------------------------------------------------------------------------
    def home(self):
        self._position = [0.0, 0.0, 0.0]
        self._homed = [True, True, True]

    def stop(self):
        self._moving = [False, False, False]

    def move_x_absolute(self, position):
        self._move_absolute(0, position)

    def move_y_absolute(self, position):
        self._move_absolute(1, position)

    def move_z_absolute(self, position):
        self._move_absolute(2, position)

    def move_x_relative(self, position):
        self._move_relative(0, position)

    def move_y_relative(self, position):
        self._move_relative(1, position)

    def move_z_relative(self, position):
        self._move_relative(2, position)

    def store_x_position(self, address):
        self._store_position(0, address)

    def store_y_position(self, address):
        self._store_position(1, address)

    def store_z_position(self, address):
        self._store_position(2, address)

    def move_to_stored_x_position(self, address):
        self._move_to_stored_position(0, address)

    def move_to_stored_y_position(self, address):
        self._move_to_stored_position(1, address)

    def move_to_stored_z_position(self, address):
        self._move_to_stored_position(2, address)
