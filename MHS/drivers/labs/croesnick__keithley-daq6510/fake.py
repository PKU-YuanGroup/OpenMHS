"""Fake SCPI transport of the DAQ6510 driver: it answers the clone's one instrument query.

The clone defines a single instrument operation, ``*IDN?`` (``src/keithley_daq6510/instrument.py:10``), and its
pyvisa-sim fixture records one reply for it (``tests/fixtures/devices.yml:9-10``).  This transport stands in for the
pyvisa connection behind the SCPI bridge: a write queues the reply of a query, a read returns it, and any other
command times out like an instrument that does not answer it.  The identity string is placeholder test data copied
from that fixture, not a measurement by this package.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Nothing
here talks to an instrument.
"""

# placeholder: test data from tests/fixtures/devices.yml:10, not a fact about an attached instrument
_IDENTITY = "Keithley Instruments Inc., Model DAQ 6510"


class FakeDaq6510:
    """A line-oriented SCPI transport that answers only ``*IDN?``."""

    def __init__(self, **_options):
        self.written = []
        self._pending = []
        self.closed = False

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        text = str(line).strip()
        # placeholder: the only recorded dialogue of the clone's pyvisa-sim fixture
        self._pending.append(_IDENTITY if text == "*IDN?" else None)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        reply = self._pending.pop(0)
        if reply is None:
            raise TimeoutError("the instrument does not answer this command")
        return reply

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        self.closed = True
