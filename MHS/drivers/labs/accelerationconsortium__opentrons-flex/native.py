"""Hardware backend: opens the Opentrons Flex through the upstream FlexMotionController.

Used only with backend="hardware" and allow_hardware=True (an operator decision).
This package is model-authored and unreviewed, and it is R2: the loader refuses
its hardware backend until a human signs ``reviewed_by`` in driver.lock.json (the
loader does this at R2 and R3 only).  The acceptance gate runs the fake backend
and never imports this module or the Opentrons stack.

``connect()`` builds the real controller with
``FlexMotionController.build(simulate=False)`` (flex_motion.py:130-153), which
calls ``OT3API.build_hardware_controller()`` and owns the CAN connection.  It
then wraps it in a small adapter so the driver can use plain mount names and
``[x, y, z]`` lists, the same contract the package fake implements:

* mount ``"left"`` -> ``OT3Mount.LEFT``, ``"right"`` -> ``OT3Mount.RIGHT``,
  ``"gripper"`` -> ``OT3Mount.GRIPPER``;
* ``point`` -> ``opentrons.types.Point(x, y, z)`` in deck millimetres.

The adapter is the production conversion layer; the fake does not duplicate it
and the driver never imports the Opentrons types.

Deployment (review note): this factory runs where the Flex CAN bus is, with the
Opentrons 8.8.1 stack on Python 3.10 (pyproject.toml:20-23).  It builds its own
OT3API and lock (``build()``, flex_motion.py:130-153); it has no shared-lock mode
(``from_api``) and starts no HTTP robot-server.  The README says one shared OT3API
avoids the "hardware already initialised" error of two processes and that the
connector service owns the hardware (README.md:16-20, 32-33), so the
``sila2-connector`` and ``opentrons-robot-server`` services must both be stopped
before this backend opens.  ``lock_timeout_s`` stays None: a light read or write
waits for a running move's lock until the request deadline.  The driver's
``teardown`` calls ``disconnect()`` (OT3API ``clean_up()``, flex_motion.py:726-729).
"""

#: Mount names accepted by the adapter and the package fake.
_MOUNTS = ("left", "right", "gripper")


def _mount(name):
    """Convert a driver mount name to the upstream OT3Mount enum."""
    from opentrons.hardware_control.types import OT3Mount

    if not isinstance(name, str) or name.lower() not in _MOUNTS:
        raise ValueError(f"mount must be one of {list(_MOUNTS)}, got {name!r}")
    return {
        "left": OT3Mount.LEFT,
        "right": OT3Mount.RIGHT,
        "gripper": OT3Mount.GRIPPER,
    }[name.lower()]


class _FlexAdapter:
    """The subset of FlexMotionController the driver binds, with plain-value arguments."""

    def __init__(self, controller):
        self._controller = controller

    @property
    def is_simulating(self):
        return bool(self._controller.is_simulating)

    def machine_status(self):
        return self._controller.machine_status()

    async def home(self, axes=None):
        await self._controller.home(axes=axes)

    async def move_to(self, mount, point, speed=None):
        from opentrons.types import Point

        target = Point(float(point[0]), float(point[1]), float(point[2]))
        return await self._controller.move_to(_mount(mount), target, speed=speed)

    async def set_lights(self, button=None, rails=None):
        await self._controller.set_lights(button=button, rails=rails)

    async def get_lights(self):
        return await self._controller.get_lights()

    async def stop(self):
        await self._controller.stop()

    async def disconnect(self):
        await self._controller.disconnect()


async def connect(**_options):
    """Build the real Flex controller and wrap it for the driver."""
    from unitelabs.opentrons_flex.io.flex_motion import FlexMotionController

    controller = await FlexMotionController.build(simulate=False)
    return _FlexAdapter(controller)
