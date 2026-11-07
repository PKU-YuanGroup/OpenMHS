"""Fake backend of the RIGOL driver: an in-memory stand-in for rigol:RigolDP832A.

Gate G7: every public method defined here exists on the upstream class rigol:RigolDP832A in the clone
(rigol.py:62-132).  The driver reaches no other attribute of the backend.  The upstream class sends one command or
query per method and returns floats and booleans; this fake keeps the same method shapes and value kinds.

Every number and string below is test data, not a statement about a device; each is marked "# placeholder".  The
state never moves by itself except through the methods, so reading it twice gives the same state.  Nothing here
talks to a device.
"""


class FakeRigolDP832A:
    def __init__(self, **_options):
        self.device = "/dev/usbtmc2"                    # placeholder
        self.idn = "RIGOL TECHNOLOGIES,DP832A,FAKE,0.0"  # placeholder
        self._channels = (1, 2, 3)                      # placeholder channel set
        # all values below are placeholders (test data), not device facts or limits
        self._output = {channel: False for channel in self._channels}       # placeholder
        self._voltage_set = {channel: 0.0 for channel in self._channels}    # placeholder
        self._current_set = {channel: 0.0 for channel in self._channels}    # placeholder
        self._ovp = {channel: 0.0 for channel in self._channels}            # placeholder
        self._ocp = {channel: 0.0 for channel in self._channels}            # placeholder

    def output_on(self, channel):
        self._output[channel] = True

    def output_off(self, channel):
        self._output[channel] = False

    def get_output(self, channel):
        return self._output[channel]

    def set_voltage(self, channel, voltage):
        self._voltage_set[channel] = float(voltage)

    def get_voltage_setpoint(self, channel):
        return self._voltage_set[channel]

    def measure_voltage(self, channel):
        return self._voltage_set[channel] if self._output[channel] else 0.0   # placeholder

    def set_current(self, channel, current):
        self._current_set[channel] = float(current)

    def get_current_setpoint(self, channel):
        return self._current_set[channel]

    def measure_current(self, channel):
        return self._current_set[channel] if self._output[channel] else 0.0   # placeholder

    def measure_power(self, channel):
        if not self._output[channel]:
            return 0.0                                                        # placeholder
        return float(self._voltage_set[channel]) * float(self._current_set[channel])

    def set_ovp(self, channel, voltage):
        self._ovp[channel] = float(voltage)

    def set_ocp(self, channel, current):
        self._ocp[channel] = float(current)

    def all_off(self):
        for channel in self._channels:
            self.output_off(channel)
