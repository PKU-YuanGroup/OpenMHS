"""Fake backend of the Benning MM12 driver: a recording stand-in for the upstream serial wrapper.

The upstream class has three query methods, and this object implements exactly those three plus the upstream
``closeConnection`` the driver's teardown calls.  Each query appends its name to ``calls`` (so a test can see that
the driver used the upstream method rather than the SDK) and returns a fixed reply with the same shape the upstream
returns: ``getDeviceInfos`` returns ``{key: (label, value)}`` and the two measurement methods return a dict with the
function/value/unit fields (Benning_MM12_class.py:303-337, 458-460, 486-513).

Every number and text below is placeholder test data of this stand-in, not a fact about an instrument.  It is a
recording fake, not a recording of a real MM12 and not its upstream simulator (the clone has none).  The gate checks
the fake on the fake backend only; nothing here talks to a device.
"""


class FakeBenningMM12:
    def __init__(self, **_options):
        self.calls = []
        self.closed = False
        # Each tuple is (label, value), the shape of the upstream getDeviceInfos reply.
        self._infos = {
            "model": ("Model name", "MM12"),              # placeholder test data
            "serial": ("Serial number", "00000000"),      # placeholder test data
            "id": ("Model ID", 0),                        # placeholder test data
            "fw": ("FW version", 1.00),                   # placeholder test data
        }
        # The two queries read the same display frame; the values are consistent (1.2345 V = 1234.5 mV).
        self._base = {"function": "DC V", "value": 1.2345, "unit": "V"}       # placeholder test data
        self._human = {"value": 1234.5, "unit": "mV"}                          # placeholder test data

    def getDeviceInfos(self):
        self.calls.append("getDeviceInfos")
        return {name: tuple(reply) for name, reply in self._infos.items()}

    def getMeasurement_baseUnits(self):
        self.calls.append("getMeasurement_baseUnits")
        return dict(self._base)

    def getMeasurement_humanUnits(self):
        self.calls.append("getMeasurement_humanUnits")
        return dict(self._human)

    def closeConnection(self):
        self.calls.append("closeConnection")
        self.closed = True
