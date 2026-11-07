"""Fake backend of the Nikon driver: an in-memory stand-in for nikon.microscope:MicroscopeDevice.

Gate G7: every public method defined here exists on the upstream class at the pinned commit
d53b4e261ae487f237a65048cf1931a40e39794b, with the upstream call shape (positional-only value arguments,
keyword-only ``idle_duration`` and async coroutines).  The driver only reaches these methods; the state lives in
plain attributes.

What it does not do: no USB, no timing, no 4.096 s firmware delay and no stage motion.  Every value below is test
data (marked ``# placeholder``), not a fact about a microscope; a real device reports its own position, labels and
firmware.  ``set_light`` and ``set_shutter`` change the state immediately, which is what the e-stop reaches.  Nothing
here talks to a device.
"""


class _StatusEvent:
    """The fields ``nikon.microscope.StatusEvent`` carries (microscope.py:28-61)."""

    def __init__(self, *, condenser, dia, filter, light, objective, optical_path, shutter, x, y, z, zoom):
        self.condenser = condenser
        self.dia = dia
        self.filter = filter
        self.light = light
        self.objective = objective
        self.optical_path = optical_path
        self.shutter = shutter
        self.x = x
        self.y = y
        self.z = z
        self.zoom = zoom


class FakeMicroscopeDevice:
    def __init__(self, **_options):
        # placeholder: the initial state of the model; a microscope reports its own
        self._condenser = 2
        self._dia = 0.5
        self._filter = 1
        self._light = False
        self._objective = 3
        self._optical_path = 0
        self._shutter = False
        self._x = 12345              # placeholder: 0.1 um counts
        self._y = 6789               # placeholder: 0.1 um counts
        self._z = 345678             # placeholder: 0.01 um counts
        self._zoom = 1
        self._firmware = "1.2.3"     # placeholder: five ASCII characters

    # -- events --------------------------------------------------------------------------------------------------
    async def get_event(self):
        return self._event()

    async def get_status(self):
        return self._event()

    async def get_stable_status(self, *, idle_duration=0.5):
        return self._event()

    def _event(self):
        return _StatusEvent(
            condenser=self._condenser,
            dia=self._dia,
            filter=self._filter,
            light=self._light,
            objective=self._objective,
            optical_path=self._optical_path,
            shutter=self._shutter,
            x=self._x,
            y=self._y,
            z=self._z,
            zoom=self._zoom,
        )

    # -- identity -------------------------------------------------------------------------------------------------
    async def get_firmware_cpu_version(self):
        return self._firmware

    # -- stage ----------------------------------------------------------------------------------------------------
    async def set_x(self, value, /):
        self._x = int(value)

    async def set_y(self, value, /):
        self._y = int(value)

    async def set_z(self, value, /):
        self._z = int(value)

    # -- optics ---------------------------------------------------------------------------------------------------
    async def set_condenser(self, value, /):
        self._condenser = int(value)

    async def set_dia(self, value, /):
        self._dia = float(value)

    async def set_filter(self, value, /):
        self._filter = int(value)

    async def set_light(self, value, /):
        self._light = bool(value)

    async def set_objective(self, value, /):
        self._objective = int(value)

    async def set_optical_path(self, value, /):
        self._optical_path = int(value)

    async def set_shutter(self, value, /):
        self._shutter = bool(value)
