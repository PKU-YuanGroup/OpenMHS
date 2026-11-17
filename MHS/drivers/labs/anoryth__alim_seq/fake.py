"""Fake backend of the HMP4040 driver: an in-memory stand-in for ``alim_seq.psu:HMP4040``.

Gate G7: every public method defined here exists on the upstream class ``alim_seq.psu:HMP4040`` in the clone
(``alim_seq/psu.py:143-397``).  The driver reaches only those methods and the ``idn`` attribute, which
``HMP4040.__init__`` defines (``alim_seq/psu.py:169``).  The upstream class sends one SCPI command or query per
method; measurements return floats and writes return None. This fake keeps those method shapes and value kinds.

The fake is an in-memory stand-in, not a recording: it does not import the upstream package, and it does not
reproduce the upstream MockPSU load model.  Every number and reply below is test data, not a statement about a
device; each is marked ``# placeholder``.  The state never moves by itself except through the methods.  Nothing
here talks to a device.
"""


class FakeHMP4040:
    #: The HMP4040 has four channels (alim_seq/psu.py:119); this mirror is test data the driver never reads.
    n_channels = 4  # placeholder

    def __init__(self, **_options):
        # All start values below are placeholders (test data), not device facts or limits.
        self.idn = "Rohde&Schwarz,HMP4040,FAKE,0.0"  # placeholder
        self._voltage = {channel: 0.0 for channel in (1, 2, 3, 4)}  # placeholder
        self._current = {channel: 0.0 for channel in (1, 2, 3, 4)}  # placeholder
        self._output = {channel: False for channel in (1, 2, 3, 4)}  # placeholder

    def connect(self):
        pass

    def close(self):
        self.all_outputs_off()

    def set_voltage(self, channel, voltage):
        self._voltage[int(channel)] = float(f"{voltage:.4f}")

    def set_current(self, channel, current):
        self._current[int(channel)] = float(f"{current:.4f}")

    def set_output(self, channel, on):
        self._output[int(channel)] = bool(on)

    def measure_voltage(self, channel):
        channel = int(channel)
        return self._voltage[channel] if self._output[channel] else 0.0  # placeholder model

    def measure_current(self, channel):
        channel = int(channel)
        return self._current[channel] if self._output[channel] else 0.0  # placeholder model

    def measure_mode(self, channel):
        return "CV" if self._output[int(channel)] else None  # placeholder mode

    def measure_status(self, channel):
        return {"mode": self.measure_mode(channel), "faults": []}  # placeholder reply

    def all_outputs_off(self):
        for channel in (1, 2, 3, 4):  # placeholder channel set
            self.set_output(channel, False)
