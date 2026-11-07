"""Fake backend of the SpectraMax driver: an in-memory stand-in for spectramax:Spectramax.

Gate G7: every public method defined here exists on the upstream class (spectramax.py:100-412): get_data,
get_instrument_status, set_temperature, read_UVVis and disconnect.  The state starts from fixed in-memory values
and never moves by itself, so reading the state twice gives the same state.  The plate payload is deliberately
smaller than a real one: the real GetDataCopy reply carries one field per well of the plate and method, while this
fake returns a few placeholder wells so receipts stay small (RESULT.json notes the gap).  Nothing here talks to a
device or writes a file.
"""


class FakeSpectramax:
    def __init__(self, **_options):
        self.connected = True                        # the upstream attribute set by __init__ (spectramax.py:58)
        self._status = "IDLE"                        # placeholder: a SoftMax Pro instrument status
        self._temperature = 25.0                     # placeholder: incubator set point in Celsius
        self._plate_data = "\t".join(                # placeholder: synthetic wells, not a device reading
            f"{value:.3f}" for value in (0.101, 0.102, 0.103, 0.104, 0.105, 0.106,
                                         0.107, 0.108, 0.109, 0.110, 0.111, 0.112)
        )

    def get_instrument_status(self):
        return self._status

    def get_data(self):
        return self._plate_data

    def set_temperature(self, temperature):
        self._temperature = float(temperature)
        return True

    def read_UVVis(self, method, results):
        return True

    def disconnect(self):
        self.connected = False
