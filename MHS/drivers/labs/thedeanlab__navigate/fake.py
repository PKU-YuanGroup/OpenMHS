"""Fake backend of the MS-2000 driver: an in-memory stand-in for MS2000Stage.

Gate G7: every public method defined here exists on navigate.model.devices.stage.asi:MS2000Stage or on one of
the bases the clone defines for it (get_axis_position, move_axis_absolute, stop_scan and stop come from
ASIStage; stage/asi.py:212-232, 257-305, 580-584, 380-383).  The signatures follow the upstream methods:
``get_axis_position(axis)`` returns the axis position (it returns inf for an axis without a mapping, as the
upstream does at stage/asi.py:227-231), ``move_axis_absolute(axis, abs_pos, wait_until_done=False)`` returns
True when the controller accepted the move and False for an axis it does not know, ``stop_scan()`` returns
None and ``stop()`` returns None.  The driver never opens a serial line, so no controller object is needed
here: this object *is* the stage the driver talks to.

The start positions are test data, not facts about a bench: they are marked ``# placeholder`` and never copied
into a Fact, a Limit or the reference.  Nothing here moves by itself, so reading the state twice gives the same
state; only a move changes it.  No hardware is contacted.
"""


class FakeMS2000Stage:
    """An in-memory MS2000Stage: the driver's reads, one move and the two stops."""

    def __init__(self, **_options):
        # The real stage takes microscope_name, device_connection and configuration; the fake needs none of
        # them, so it accepts and drops any option the loader passes.
        self._positions = {"x": 0.0, "y": 0.0, "z": 0.0}   # placeholder start positions in micrometres
        self._stop_calls = 0                                 # placeholder counter: the native stop is observable
        self._scan_stop_calls = 0                            # placeholder counter

    def get_axis_position(self, axis):
        if axis not in self._positions:
            return float("inf")                              # as the upstream does for an unknown axis
        return self._positions[axis]

    def move_axis_absolute(self, axis, abs_pos, wait_until_done=False):
        if axis not in self._positions:
            return False                                     # as the upstream does for an axis it cannot map
        self._positions[axis] = float(abs_pos)
        return True

    def stop_scan(self):
        self._scan_stop_calls += 1

    def stop(self):
        self._stop_calls += 1
