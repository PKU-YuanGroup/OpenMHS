"""Fake backend of the Lake Shore Model 218 driver: an in-memory stand-in for devices.ls218:DeviceConnection.

Gate G7: the only public member the driver reaches is ``read_all``, and that member exists on
``devices.ls218:DeviceConnection`` (devices/ls218.py:29).  Its signature takes no argument, as upstream.  The
upstream class also stores ``host``, ``port``, ``timeout``, ``read_regex`` and ``tn`` (devices/ls218.py:25-27,
devices/telnet_base.py:30-36), but the driver never touches them, so the fake does not need them.

The eight readings below are placeholder test data, not facts, limits or measurements of a unit; the real values
come from the instrument.  A real reply can contain a different number of channels (the query asks for all of them),
so the fake fixes eight only as an example array.  ``read_all`` never changes the values, so reading the state twice
gives the same state.  Nothing here talks to a device or opens a socket.
"""

#: Placeholder channel readings; every number is test data, never a Fact or a Limit.
_TEMPERATURES = [300.001, 300.002, 300.003, 300.004, 300.005, 300.006, 300.007, 300.008]  # placeholder


class FakeLs218:
    def __init__(self, **_options):
        self._temperatures = list(_TEMPERATURES)  # placeholder

    def read_all(self):
        """Return the placeholder channel readings of one KRDG? 0 reply."""
        return list(self._temperatures)
