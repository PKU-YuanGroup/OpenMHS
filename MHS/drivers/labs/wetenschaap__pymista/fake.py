"""Fake backend of the pymista driver: an in-memory stand-in for pymista.zaber:ZaberStage.

Gate G7: every public method defined here exists on ZaberStage or on the UniversalStage it inherits
(pymista/zaber.py:35-48, pymista/universal.py:13-31, 84-96).  G7's AST reader does not follow the star import of
pymista/universal.py from pymista/zaber.py, so the inherited names are reported as ``MAYBE_ABSENT`` warnings, never
as missing: every one of them occurs in the clone.

The fake models two axes because the ZaberStage builds one axis per detected device and the README says a stage
typically has 2 or 3 axes (README.md:68).  The values are test data, never facts: the start position, the homed
flags and the two-axis count are marked ``# placeholder`` and are not copied into a Fact, a Limit or the reference.
Moves complete instantly, so reading the state twice gives the same state.  Nothing here talks to a device.
"""


class FakeZaberStage:
    def __init__(self, **_options):
        # placeholder: two axes at power-up, at zero and not homed
        self._positions = [0.0, 0.0]
        self._homed = [False, False]    # placeholder: a stage that has not been homed yet
        self._moving = False
        self._closed = False

    # -- state the driver reads ---------------------------------------------------------------------------------
    def get_position(self):
        return list(self._positions)

    def is_moving(self):
        return self._moving

    def is_homed(self):
        return list(self._homed)

    # -- commands the driver sends ------------------------------------------------------------------------------
    def move_absolute(self, position, wait_until_idle=True):
        for index, value in enumerate(position):
            if index < len(self._positions):
                self._positions[index] = float(value)
        self._moving = False

    def move_relative(self, move, wait_until_idle=True):
        for index, value in enumerate(move):
            if index < len(self._positions):
                self._positions[index] += float(value)
        self._moving = False

    def home(self, force=False):
        # force=True is what the driver sends, so the fake always homes both axes and zeroes their positions.
        self._homed = [True] * len(self._homed)
        self._positions = [0.0] * len(self._positions)
        self._moving = False

    def stop(self):
        self._moving = False

    def close(self):
        self._closed = True
