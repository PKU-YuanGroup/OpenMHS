"""Fake backend of the Opentrons Flex driver: an in-memory stand-in for the FlexMotionController adapter.

Gate G7: every public member defined on the fake class exists on
``unitelabs.opentrons_flex.io.flex_motion:FlexMotionController`` (is_simulating,
machine_status, home, move_to, set_lights, get_lights, stop, disconnect).  The
async members are coroutine functions like the upstream ones; ``machine_status``
is sync and ``is_simulating`` is a property, as upstream.  ``set_lights(button=None,
rails=None)`` changes only the named light, matching the upstream "and/or"
docstring, and ``get_lights`` returns a fresh mapping so two reads give the same
state.

The connector's recovery gate is modelled as the clone defines it: ``stop()``
requires a full home (``mark_halted``, recovery_state.py:47-54); while that is
required ``move_to`` and a partial ``home`` raise ``NotHomedError`` with the
upstream message (flex_motion.py:242-243, 260, 496-499; recovery_state.py:34-45),
and only a full ``home()`` clears it (flex_motion.py:247-248).  The gate starts
clear, as ``HardwareRecoveryState`` does (recovery_state.py:19).  ``move_to``
refuses a non-finite target as ``_validate_tip_location`` does (flex_motion.py:506-510).

This is not a recording and not the upstream simulator: the clone's simulator
is ``FlexMotionController.build(simulate=True)``, which imports the uninstalled
Opentrons 8.8.1 stack and needs Python 3.10.  The fake does not model the OT3API
machine-axis bounds, an unknown position before the first home, the E-stop or
door state changing, a move that takes time (so a stop never meets a running
move here), or the operation lock that makes light reads wait for a running move.
Every starting value below is test data (# placeholder), not a fact, a limit or a
device default.  Nothing here talks to a device.
"""

import math


class NotHomedError(Exception):
    """Stand-in for unitelabs.opentrons_flex.io._errors.NotHomedError (_errors.py:177-184), matched by name."""


#: The upstream refusal text with the guidance of a required full home (flex_motion.py:498, recovery_state.py:39).
_RECOVERY_GATED = "The robot is recovery-gated. Fully re-home all robot axes before retrying."


class _Point:
    """The x/y/z result of ``move_to``; the upstream returns ``opentrons.types.Point``."""

    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


class _MachineState:
    """The fields of the upstream MachineState dataclass that the driver reads."""

    __slots__ = ("estop", "door_open", "is_error_state", "message")

    def __init__(self, estop, door_open, is_error_state, message=""):
        self.estop = estop
        self.door_open = door_open
        self.is_error_state = is_error_state
        self.message = message


class FakeOpentronsFlex:
    """An in-memory, stationary Flex gantry with the connector's halt recovery gate; no motion is simulated."""

    def __init__(self, **_options):
        self._lights = {"button": False, "rails": False}   # placeholder
        self._position = _Point(0.0, 0.0, 0.0)              # placeholder
        self._estop = "DISENGAGED"                          # placeholder
        self._door_open = False                             # placeholder
        self._rehome_required = False                       # recovery_state.py:19 (the gate starts clear)
        self._stops = 0
        self._homes = 0

    @property
    def is_simulating(self):
        """True: the fake is a simulated backend, never CAN hardware."""
        return True

    def machine_status(self):
        """Cached safety state, as the upstream reads it without I/O."""
        return _MachineState(self._estop, self._door_open, self._estop in ("PHYSICALLY_ENGAGED", "LOGICALLY_ENGAGED"))

    async def home(self, axes=None):
        """A full home (axes=None) clears the recovery gate; a partial home is refused while it is set."""
        if axes is not None and self._rehome_required:
            raise NotHomedError(_RECOVERY_GATED)
        self._homes += 1
        if axes is None:
            self._rehome_required = False

    async def move_to(self, mount, point, speed=None):
        """Refuse while recovery-gated or for a non-finite target; else remember and return the target."""
        if self._rehome_required:
            raise NotHomedError(_RECOVERY_GATED)
        target = (float(point[0]), float(point[1]), float(point[2]))
        if not all(math.isfinite(value) for value in target):
            raise ValueError("tip operation location coordinates must all be finite")
        self._position = _Point(*target)
        return self._position

    async def set_lights(self, button=None, rails=None):
        """Set the status-bar (button) and/or deck (rails) lights; None leaves that light unchanged."""
        if button is not None:
            self._lights["button"] = bool(button)
        if rails is not None:
            self._lights["rails"] = bool(rails)

    async def get_lights(self):
        """The current status-bar and deck light state."""
        return dict(self._lights)

    async def stop(self):
        """The native stop: record a halt and require a full home; the halt does not engage the hardware E-stop."""
        self._stops += 1
        self._rehome_required = True

    async def disconnect(self):
        """Release the stand-in (the upstream calls OT3API clean_up(), flex_motion.py:726-729)."""
