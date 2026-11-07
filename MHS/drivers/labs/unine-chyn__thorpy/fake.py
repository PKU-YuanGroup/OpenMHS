"""Fake Thorlabs APT port of the Thorpy driver: an in-memory GenericStage behind a fake Port.

The fake answers only the surface the driver uses: ``Port.get_stages`` returns a ``FakeStage`` that mirrors the
``GenericStage`` properties of the clone (``position``, ``max_velocity``, ``acceleration``, ``status_homed``,
``home_non_blocking``), and ``Port.send_message`` decodes the six-byte ``MGMSG_MOT_MOVE_STOP`` frame so the e-stop
and the stop action have an observable effect.  No upstream module is imported and nothing here talks to a device;
the numbers below are test data and are marked as placeholders, never facts or limits.
"""

import struct

STOP_MESSAGE_ID = 0x465
STOP_IMMEDIATE = 0x01


class FakeStage:
    """The GenericStage surface the driver reads and writes (a stand-in, not the upstream class)."""

    def __init__(self, port):
        self._port = port
        self._position = 0.0          # placeholder: start position of the simulated axis
        self._max_velocity = 1.0      # placeholder: simulated default velocity
        self._acceleration = 10.0     # placeholder: simulated default acceleration
        self._min_velocity = 0.0      # placeholder: simulated start velocity
        self._velocity = 0.0          # placeholder: the axis starts at rest
        self._homed = False
        self._moving = False
        self._home_polls = 0
        self._home_polls_needed = 2   # placeholder: simulated length of a home move

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, new_value):
        self._position = float(new_value)
        self._velocity = 0.0

    @property
    def max_velocity(self):
        return self._max_velocity

    @max_velocity.setter
    def max_velocity(self, new_value):
        self._max_velocity = float(new_value)

    @property
    def acceleration(self):
        return self._acceleration

    @acceleration.setter
    def acceleration(self, new_value):
        self._acceleration = float(new_value)

    @property
    def min_velocity(self):
        return self._min_velocity

    @property
    def velocity(self):
        return self._velocity

    @property
    def units(self):
        return "mm"

    @property
    def status_homed(self):
        if self._moving:
            self._home_polls += 1
            if self._home_polls >= self._home_polls_needed:
                self._homed = True
                self._moving = False
        return self._homed

    @property
    def status_in_motion_forward(self):
        return self._moving

    @property
    def status_in_motion_reverse(self):
        return False

    def home_non_blocking(self, force=True):
        if self._homed and not force:
            return True
        self._homed = False
        self._moving = True
        self._home_polls = 0
        return True

    def _apply_stop(self, stop_mode):
        self._moving = False
        self._home_polls = 0
        self._velocity = 0.0


class FakePort:
    """The fake backend entry: the two public Port methods the driver calls."""

    def __init__(self, **_options):
        self._stage = FakeStage(self)
        self.serial_number = 0        # placeholder: simulated serial number
        self.channel_count = 1        # placeholder: one simulated channel
        self.sent = []

    def get_stages(self, only_chan_idents=None):
        if only_chan_idents is None:
            only_chan_idents = [0x01]
        return {chan: self._stage for chan in only_chan_idents}

    def send_message(self, msg):
        data = bytes(msg)
        self.sent.append(data)
        if len(data) >= 6:
            message_id = struct.unpack_from("<H", data, 0)[0]
            if message_id == STOP_MESSAGE_ID:
                chan_ident = data[2]
                stop_mode = data[3]
                if chan_ident == 0x01 and stop_mode == STOP_IMMEDIATE:
                    self._stage._apply_stop(stop_mode)
