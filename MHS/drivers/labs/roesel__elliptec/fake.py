"""Fake backend of the Elliptec shutter driver: an in-memory stand-in for elliptec.shutter:Shutter.

Gate G7: every public method defined here exists on the upstream class elliptec.shutter:Shutter (a Motor, so the
surface includes src/elliptec/shutter.py and src/elliptec/motor.py), and their signatures follow the upstream ones:
get_slot() and is_open()/is_closed() read the slot, set_slot(slot) moves to slot 1 or slot 2 and answers None for
another value (src/elliptec/shutter.py:26-38), open()/close() move the slider between the two slots of the class
(src/elliptec/shutter.py:50-68), home(clockwise=True) runs the homing move (src/elliptec/motor.py:93-98) and
close_connection() closes the controller (src/elliptec/motor.py:125-127).  The upstream class reads the motor info
from the device when it is created (src/elliptec/motor.py:31-43); the fake needs none of that to answer a move.

The starting slot and the slot the homing move selects are test data, not facts of the device: they are marked
``# placeholder``.  The slot stays where the last move put it, so reading the state twice without a move gives the
same state.  Nothing here talks to a device.
"""


class FakeShutter:
    """An in-memory Elliptec shutter: a slider between slot 1 (closed) and slot 2 (open)."""

    def __init__(self, **_options):
        self._slot = 1                  # placeholder: the slider starts in the closed slot
        self._connected = True          # placeholder: the controller connection is open

    def get_slot(self):
        """The slot the slider is in, like Shutter.get_slot (src/elliptec/shutter.py:20-24)."""
        return self._slot

    def set_slot(self, slot):
        """Move to slot 1 or slot 2 and report it, like Shutter.set_slot (src/elliptec/shutter.py:26-38)."""
        if slot not in (1, 2):
            return None
        self._slot = int(slot)
        return self._slot

    def open(self):
        """Move to the open slot, like Shutter.open (src/elliptec/shutter.py:50-54)."""
        self._slot = 2
        return self._slot

    def close(self):
        """Move to the closed slot, like Shutter.close (src/elliptec/shutter.py:56-60)."""
        self._slot = 1
        return self._slot

    def is_open(self):
        """True while the slider is in the open slot, like Shutter.is_open (src/elliptec/shutter.py:62-64)."""
        return self._slot == 2

    def is_closed(self):
        """True while the slider is in the closed slot, like Shutter.is_closed (src/elliptec/shutter.py:66-68)."""
        return self._slot == 1

    def home(self, clockwise=True):
        """Run the homing move, like Shutter.home (src/elliptec/motor.py:93-98)."""
        self._slot = 1                  # placeholder: the home position of the stand-in is slot 1
        return self._slot

    def close_connection(self):
        """Close the controller connection, like Shutter.close_connection (src/elliptec/motor.py:125-127)."""
        self._connected = False
