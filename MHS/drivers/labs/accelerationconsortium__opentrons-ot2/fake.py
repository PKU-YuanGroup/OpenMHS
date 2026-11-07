"""Fake backend of the OT-2 driver: an in-memory stand-in for OT2MotionController.

Gate G7: every public method defined here exists on
``unitelabs.opentrons_ot2.io.motion:OT2MotionController`` (``get_position``,
``get_firmware_version``, ``get_serial_number``, ``read_pipette_model``,
``read_pipette_id``, ``get_button_light``, ``set_button_light``,
``get_rail_lights``, ``set_rail_lights``, ``read_button``,
``read_door_switch``, ``home``, ``move``, ``aspirate``, ``dispense``,
``stop``, ``reset_from_error`` and ``disconnect``), and ``is_simulating`` is a
property like the upstream one.  The coroutine methods are ``async def`` as
upstream; the GPIO methods are synchronous as upstream.

Like the upstream controller (motion.py:223-226), the coroutines that reach
the Smoothie hold one asyncio lock for their whole call, ``stop`` included
(motion.py:775-778): a stop waits until a running move or home has released
the lock.  ``stop`` records the halt and marks the axes un-homed; it does not
claim that a physical Smoothie stopped.  Two test-only knobs model a running
move: ``_move_s`` keeps a move or home waiting for its reply for that many
seconds (0, the default, answers at once), and ``_hold_lock_on_cancel`` keeps
the lock through a cancellation until that time has passed (a dependency that
does not end its wait when the task is cancelled; the clone does not show
which the Opentrons stack does).  ``_smoothie_log`` lists every call that
would reach the Smoothie, in order, for the package tests.

This is not a recording and not the upstream simulator: the clone's
``OT2MotionController.build(simulate=True)`` constructs an Opentrons
``SmoothieDriver`` and needs the uninstalled Opentrons stack (opentrons 8.8.1
below Python 3.12, 9.0.0 from 3.12), which the gate cannot import.  The card's
``mock_strategy.preferred`` is ``fake``.  Apart from the requested position
bookkeeping the fake is stationary: no timing beyond the knobs, acceleration,
planner queue, alarm state or physical stop is simulated.  Every starting
value and canned reply below is test data (``# placeholder``), never a fact, a
limit or a device default.  Nothing here talks to a device.
"""

import asyncio

#: Where a full home books the axes: the homed position the upstream simulation test records as the Smoothie
#: firmware defaults (tests/features/test_motion_simulation.py:36-37).  Test data only.
_HOMED = {"X": 418.0, "Y": 353.0, "Z": 218.0, "A": 218.0, "B": 19.0, "C": 19.0}   # placeholder


class FakeOT2MotionController:
    """An in-memory, stationary OT-2 motion controller; no physical motion is simulated."""

    def __init__(self, **_options):
        self._position = {axis: 0.0 for axis in "XYZABC"}   # placeholder
        self._firmware = "fake-smoothie"                    # placeholder
        self._serial = "fake-ot2"                           # placeholder
        self._pipette_models = {"left": "p300_single_gen2", "right": ""}   # placeholder
        self._pipette_ids = {"left": "fake-left", "right": ""}            # placeholder
        self._button_light = (True, True, True)             # placeholder
        self._rail_lights = True                            # placeholder
        self._button_pressed = False                        # placeholder
        self._door_closed = True                            # placeholder
        self._homed = False                                 # placeholder
        self._alarm = False                                 # placeholder
        self._stops = 0
        self._resets = 0
        self._disconnects = 0
        self._lock = asyncio.Lock()     # one hardware lock, as motion.py:225
        self._move_s = 0.0              # test knob: seconds a move or home waits for its reply
        self._hold_lock_on_cancel = False   # test knob: keep the lock through a cancellation
        self._smoothie_log = []

    async def _wait_for_reply(self, what):
        """Stand-in for the SmoothieDriver's wait for the Smoothie's reply to a move or home."""
        if self._move_s <= 0:
            return
        loop = asyncio.get_running_loop()
        end = loop.time() + self._move_s
        if not self._hold_lock_on_cancel:
            try:
                await asyncio.sleep(self._move_s)
            except asyncio.CancelledError:
                self._smoothie_log.append(what + ":cancelled")
                raise
            return
        cancelled = False
        while loop.time() < end:
            try:
                await asyncio.sleep(max(0.0, end - loop.time()))
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            self._smoothie_log.append(what + ":cancelled-late")
            raise asyncio.CancelledError()

    @property
    def is_simulating(self):
        """True: this is a simulated backend, never Smoothie hardware."""
        return True

    async def get_position(self):
        """Return a copy of the cached axis-to-millimetre position."""
        async with self._lock:
            self._smoothie_log.append("get_position")
            return dict(self._position)

    async def get_firmware_version(self):
        """Return the canned firmware string."""
        async with self._lock:
            self._smoothie_log.append("get_firmware_version")
            return self._firmware

    async def get_serial_number(self):
        """Return the canned serial number (a file on the robot, not the Smoothie)."""
        return self._serial

    async def read_pipette_model(self, mount):
        """Return the canned model for the requested mount (empty when absent)."""
        async with self._lock:
            self._smoothie_log.append("read_pipette_model")
            return self._pipette_models.get(str(mount).lower(), "")

    async def read_pipette_id(self, mount):
        """Return the canned id for the requested mount (empty when absent)."""
        async with self._lock:
            self._smoothie_log.append("read_pipette_id")
            return self._pipette_ids.get(str(mount).lower(), "")

    def get_button_light(self):
        """Return the current (red, green, blue) button-LED tuple."""
        return tuple(self._button_light)

    def set_button_light(self, red=False, green=False, blue=False):
        """Set the three button-LED channels; no hardware is touched."""
        self._button_light = (bool(red), bool(green), bool(blue))

    def get_rail_lights(self):
        """Return the current rail-lights state."""
        return bool(self._rail_lights)

    def set_rail_lights(self, on):
        """Set the rail-lights state; no hardware is touched."""
        self._rail_lights = bool(on)

    def read_button(self):
        """Return the canned front-button state."""
        return bool(self._button_pressed)

    def read_door_switch(self):
        """Return the canned door-switch state."""
        return bool(self._door_closed)

    async def home(self, axes="XYZABC"):
        """Book the named axes at the placeholder homed position; no physical homing happens."""
        async with self._lock:
            self._smoothie_log.append("home")
            await self._wait_for_reply("home")
            for axis in str(axes).upper():
                if axis in self._position:
                    self._position[axis] = _HOMED[axis]
            self._homed = True

    async def move(self, target, speed=None):
        """Book the requested absolute axis positions; no physical move happens."""
        async with self._lock:
            self._smoothie_log.append("move")
            await self._wait_for_reply("move")
            for axis, value in dict(target).items():
                if str(axis).upper() in self._position:
                    self._position[str(axis).upper()] = float(value)

    async def aspirate(self, axis, volume_ul, ul_per_mm, flow_rate_ul_s):
        """Book the plunger travel of an aspirate; no liquid and no motion are simulated."""
        async with self._lock:
            self._smoothie_log.append("aspirate")
            axis = str(axis).upper()
            if axis in self._position:
                self._position[axis] = self._position[axis] + float(volume_ul) / float(ul_per_mm)

    async def dispense(self, axis, volume_ul, ul_per_mm, flow_rate_ul_s):
        """Book the plunger travel of a dispense; no liquid and no motion are simulated."""
        async with self._lock:
            self._smoothie_log.append("dispense")
            axis = str(axis).upper()
            if axis in self._position:
                self._position[axis] = self._position[axis] - float(volume_ul) / float(ul_per_mm)

    async def stop(self):
        """The native stop path: wait for the lock, then record a halt; no physical halt is proven."""
        async with self._lock:
            self._smoothie_log.append("stop")
            self._stops += 1
            self._homed = False

    async def reset_from_error(self):
        """The native M999 path: clear the fake alarm flag and un-home the axes."""
        async with self._lock:
            self._smoothie_log.append("reset_from_error")
            self._alarm = False
            self._homed = False
            self._resets += 1

    async def disconnect(self):
        """Close the fake connection object; no serial port is held."""
        self._disconnects += 1
