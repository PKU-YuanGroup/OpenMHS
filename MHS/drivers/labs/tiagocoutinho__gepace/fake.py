"""Fake backend of the gepace driver: an in-memory stand-in for gepace.pace:Pace.

The upstream Pace object owns one Module per pressure channel (gepace/pace.py:329-336) and
``pace[module]`` returns it (gepace/pace.py:339-340).  This fake reproduces that shape: every
public method of FakeGepace is a method of Pace (idn, version, mac, task, world_area, hw_test,
error, startup_mode, serial_numbers, close and __call__; the dunder methods are not public
attributes checked by G7), and the private _FakeModule carries the public methods of
gepace.pace:Module (pressure, barometric_pressure, pressure_control, unit, pressure_range,
pressure_in_limits, start and stop).  Like the upstream class on an asyncio connection, all of
them are coroutine functions.

Every literal value in this file is placeholder test data, not a Fact, a Limit or a citation.
Nothing here talks to a device.
"""


class _Mode:
    """The ``name`` member of the upstream Mode enum (gepace/pace.py:207-219)."""

    def __init__(self, name):
        self.name = name


class _FakeModule:
    """One pressure module; the methods mirror gepace.pace:Module."""

    def __init__(self, module):
        self.id = module                         # placeholder module number
        self._pressure = 34.567                  # placeholder
        self._barometric = 1.013                 # placeholder
        self._control = False                    # placeholder: pressure control starts disabled
        self._unit = "BAR"                       # placeholder
        self._range = "0 to 100"                 # placeholder
        self._in_limits = True                   # placeholder

    async def pressure(self):
        return self._pressure

    async def barometric_pressure(self):
        return self._barometric

    async def pressure_control(self, value=None):
        if value is None:
            return self._control
        self._control = bool(value)
        return self._control

    async def unit(self, value=None):
        if value is None:
            return self._unit
        self._unit = str(value)
        return self._unit

    async def pressure_range(self):
        return self._range

    async def pressure_in_limits(self):
        return self._pressure, self._in_limits

    async def start(self):
        return await self.pressure_control(True)

    async def stop(self):
        return await self.pressure_control(False)


class FakeGepace:
    """In-memory Pace with two modules; the driver serves module 1."""

    def __init__(self, **options):
        modules = options.get("modules", (1, 2))  # placeholder: the upstream constructor default
        self.modules = {module: _FakeModule(module) for module in modules}
        self._closed = False
        self._idn = "GE Druck,PACE5000,00000000,FAKE"  # placeholder
        self._version = "FAKE 0.0"                      # placeholder
        self._mac = "00:00:00:00:00:00"                 # placeholder
        self._task = "IDLE"                             # placeholder
        self._world_area = "WORLD"                      # placeholder
        self._startup = (_Mode("CONT"), 12.464)         # placeholder
        self._serial_numbers = {                        # placeholder
            "ui": 0,
            "ctrl1": 0,
            "ctrl2": 0,
            "ao1": 0,
            "ao2": 0,
            "vfc1": 0,
            "vfc2": 0,
        }

    def __getitem__(self, key):
        return self.modules[key]

    async def idn(self):
        return self._idn

    async def version(self):
        return self._version

    async def mac(self):
        return self._mac

    async def task(self):
        return self._task

    async def world_area(self):
        return self._world_area

    async def hw_test(self):
        return True  # placeholder

    async def error(self):
        return 0, "No error"  # placeholder

    async def startup_mode(self):
        return self._startup

    async def serial_numbers(self):
        return dict(self._serial_numbers)

    async def close(self):
        self._closed = True

    async def __call__(self, request):
        """Answer the pressure-control setter+readback the driver sends through Pace.__call__."""

        head = request.split(";", 1)[0]
        for module in self.modules.values():
            prefix = ":OUTP{}:STAT".format(module.id)
            if head.startswith(prefix + " "):
                state = head.rsplit(" ", 1)[1].strip()
                if state not in ("0", "1"):  # placeholder: the two SCPI boolean tokens
                    raise ValueError("unsupported pressure-control state")
                await module.pressure_control(state == "1")
                return "OUTP{}:STAT {}".format(module.id, state)
        raise ValueError("unsupported request")
