"""Fake backend of the Lake Shore 336 driver: an in-memory stand-in for instruments.ls336:DeviceConnection.

Gate G7: every public method defined here exists on instruments.ls336:DeviceConnection (the methods at
instruments/ls336.py:113-272).  The signatures and return types follow the upstream methods: every per-channel method
takes the 1-based channel; the set_* methods write and return the parsed readback; the mode and range readbacks are
floats, because the upstream parses every reply group with float() (instruments/ls336.py:199-201, 212-214, 226-228,
239-241); read_temps returns four floats.  read_pid ignores its channel as the upstream does: it sends PID? without an
output number (instruments/ls336.py:140-147) and the clone does not say which output's gains the controller returns, so
the fake answers one placeholder reply for every channel.  set_pid is not modelled: the driver never calls it, and its
PID? readback has the same unknown output.  set_outmode keeps the control input and the powerup flag it is sent, as the
controller does.

The starting values are test data, not device facts or bounds: each is marked ``# placeholder``.  Nothing here talks to
a device, records traffic, moves a temperature or simulates a plant; the values only change when a setter writes them.
Not modelled: the upstream's 2 s reply timeout and the OSError it raises, a reply that arrives late, replies crossed
between concurrent callers of the one socket, and the messages the upstream prints to stdout on a failure.
"""


class FakeLs336:
    def __init__(self, **_options):
        # All values below are placeholders chosen to make the fake readable; they are not device data.
        self._temps = [295.0, 294.5, 293.0, 292.5]            # placeholder: four Kelvin readings
        self._setpoints = {1: 300.0, 2: 300.0}                # placeholder: setpoints in the controller's unit (K here)
        self._heater = {1: 0.0, 2: 0.0}                       # placeholder: heater output percent
        self._manual = {1: 0.0, 2: 0.0}                       # placeholder: manual heater percent
        self._pid_reply = (10.0, 1.0, 0.0)                    # placeholder: the reply to PID? (no output number)
        self._mode = {1: 0, 2: 0}                             # placeholder: OUTMODE mode 0, Off
        self._input = {1: 1, 2: 2}                            # placeholder: OUTMODE control input
        self._powerup = {1: 0, 2: 0}                          # placeholder: OUTMODE powerup enable
        self._range = {1: 3, 2: 0}                            # placeholder: RANGE code 3, High

    def read_temps(self):
        return list(self._temps)

    def read_pid(self, channel):
        # The upstream sends PID? without the channel (instruments/ls336.py:143): the reply does not follow it.
        return list(self._pid_reply)

    def read_heater(self, channel):
        return float(self._heater[channel])

    def read_man_heater(self, channel):
        return float(self._manual[channel])

    def set_man_heater(self, channel, value):
        self._manual[channel] = float(value)
        return float(self._manual[channel])

    def read_outmode(self, channel):
        return float(self._mode[channel])

    def set_outmode(self, channel, mode, in_channel, powerup_on):
        self._mode[channel] = int(mode)
        self._input[channel] = int(in_channel)
        self._powerup[channel] = int(powerup_on)
        return float(self._mode[channel])

    def read_range(self, channel):
        return float(self._range[channel])

    def set_range(self, channel, hrange):
        self._range[channel] = int(hrange)
        return float(self._range[channel])

    def read_setpoint(self, channel):
        return float(self._setpoints[channel])

    def set_setpoint(self, channel, value):
        self._setpoints[channel] = float(value)
        return float(self._setpoints[channel])
