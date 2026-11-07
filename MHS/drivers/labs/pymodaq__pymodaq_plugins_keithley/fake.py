"""Fake backend of the Keithley 2100 driver.

Every public method here exists on ``Keithley2100VISADriver`` in the clone (G7); the state is kept in plain
attributes and every canned value is test data, not a fact about an instrument.  The fake answers the native
methods the driver calls: it does not replay a session, because the gate and the conformance suite call the
methods in different orders and each endpoint gets a fresh object.
"""


class FakeKeithley2100:
    def __init__(self, **_options):
        # placeholder: an identity of the shape *IDN? returns, not a recorded instrument
        self._idn = "Keithley Instruments,2100,0000000,1.0"
        # placeholder: an option-card reply, not the card of a real unit
        self._card = "NONE"
        # placeholder: the no-error reply used by the upstream configuration sequence
        self._error = '0,"No error"'
        # placeholder: a reading, not a measurement
        self._reading = 1.0
        self._mode = "unknown"
        self._closed = False
        self.reset_calls = 0
        self.read_calls = 0
        self.written_modes = []

    def read(self):
        self.read_calls += 1
        return self._reading

    def get_idn(self):
        return self._idn

    def get_card(self):
        return self._card

    def get_error(self):
        return self._error

    def set_mode(self, mode, **kwargs):
        self._mode = str(mode)
        self.written_modes.append(self._mode)

    def reset(self):
        self.reset_calls += 1
        # placeholder: the reset reply state used by the fake, not a device default
        self._mode = "unknown"
        self._reading = 0.0
        self._error = '0,"No error"'

    def close(self):
        self._closed = True
