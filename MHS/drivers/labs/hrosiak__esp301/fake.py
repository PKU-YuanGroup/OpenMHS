"""Fake backend of the Newport ESP 301 driver: an in-memory stand-in for the upstream ``esp:esp`` class.

Gate G7: every public method defined here exists on ``esp:esp`` -- ``reset``, ``check_errors``, ``getpos`` and
``setpos`` (esp.py:22-42).  The fake keeps the upstream calling conventions: positions travel as bare floats, the
axis is optional in ``getpos``/``setpos`` and required in ``reset``, and the default axis is the ``defaxis``
attribute the driver reads.  ``setpos`` rounds to four decimals because the upstream formats the PA argument with
four decimals (esp.py:41); this is fake behaviour, not a statement about a real controller.

Every number below is test data, not a fact about a controller or a stage.  Nothing here talks to a device.
"""


class FakeEsp301:
    def __init__(self, **options):
        # placeholder served axis; the hardware factory supplies the configured axis instead
        self.defaxis = int(options.get("axis", 1))
        self.inuse = [self.defaxis]
        # placeholder start position in the controller's own position units
        self._position = 0.0
        # placeholder controller error number (0 = no error)
        self._error = 0
        # placeholder counter of reset calls, kept observable for a fake inspection
        self._resets = 0

    def reset(self, axis):
        self._resets += 1

    def check_errors(self):
        return float(self._error)

    def getpos(self, axis=None):
        return float(self._position)

    def setpos(self, pos, axis=None):
        self._position = round(float(pos), 4)
        return float(self._position)
