"""Fake backend for the PyLabRobot Incubator front end (gate G7 checks it against Incubator).

The fake implements only the public methods the upstream ``Incubator`` class has: ``setup``, ``stop``,
``get_num_free_sites``, ``fetch_plate_to_loading_tray``, ``take_in_plate``, ``set_temperature``, ``get_temperature``,
``open_door``/``close_door``, ``start_shaking`` and ``stop_shaking``.  It is an in-memory stand-in, not a recording,
and it never imports PyLabRobot or the clone.

Every number below is test data, not a fact or a device bound.  The temperatures, plate names, site counts and the
loading-tray list are placeholders chosen so the gate's single-endpoint conformance run can move a plate out and
back; the real deck, plate names, site count and temperature range are deployment data.
"""


class _FakePlate:
    """Minimal stand-in for the Plate object returned by Incubator.fetch_plate_to_loading_tray."""

    def __init__(self, name: str):
        self.name = name


class FakeIncubator:
    def __init__(self, **_options):
        self._setup_finished = False
        self._temperature = 37.0  # placeholder: a nominal incubator reading
        self._shaking = False
        self._frequency = 0.0  # placeholder: no shaker running
        self._door_open = False
        self._safe_stop_calls = 0  # placeholder: a counter, never a hardware fact
        self._sites = {"plate_1": "site_1", "plate_2": "site_2"}  # placeholder: two named plates
        self._free_sites = 2  # placeholder: two other sites are free
        self._tray: list[str] = []

    def _need_setup(self) -> None:
        if not self._setup_finished:
            raise RuntimeError("The setup has not finished. See `setup`.")

    async def setup(self, **_backend_kwargs) -> None:
        if self._setup_finished:
            raise RuntimeError("The setup has already finished. See `stop`.")
        self._setup_finished = True

    async def stop(self) -> None:
        self._need_setup()
        self._shaking = False
        self._frequency = 0.0  # placeholder: shaker off
        self._door_open = False
        self._setup_finished = False

    async def get_temperature(self) -> float:
        self._need_setup()
        return self._temperature

    async def set_temperature(self, temperature: float) -> None:
        self._need_setup()
        self._temperature = float(temperature)

    async def start_shaking(self, frequency: float) -> None:
        self._need_setup()
        self._shaking = True
        self._frequency = float(frequency)

    async def stop_shaking(self) -> None:
        self._need_setup()
        self._shaking = False
        self._frequency = 0.0  # placeholder: shaker off
        self._safe_stop_calls += 1  # placeholder: diagnostic counter only

    async def open_door(self) -> None:
        self._need_setup()
        self._door_open = True

    async def close_door(self) -> None:
        self._need_setup()
        self._door_open = False

    async def fetch_plate_to_loading_tray(self, plate_name: str) -> _FakePlate:
        self._need_setup()
        if plate_name in self._tray:
            return _FakePlate(plate_name)
        site = self._sites.pop(plate_name, None)
        if site is None:
            raise KeyError(f"no plate named {plate_name!r} on a site")
        self._tray.append(plate_name)
        self._free_sites += 1
        return _FakePlate(plate_name)

    async def take_in_plate(self, site: str) -> None:
        self._need_setup()
        if site not in ("random", "smallest"):
            raise ValueError(f"site must be 'random' or 'smallest', got {site!r}")
        if not self._tray:
            # A fresh gate endpoint has no preceding fetch; model the loading tray as presenting one site plate.
            plate_name = next(iter(self._sites), None)
            if plate_name is None:
                raise RuntimeError("no plate on the loading tray and no plate on a site")
            self._sites.pop(plate_name)
            self._tray.append(plate_name)
            self._free_sites += 1
        plate_name = self._tray.pop()
        self._sites[plate_name] = f"site_{len(self._sites) + 1}"  # placeholder: a synthetic site name
        self._free_sites -= 1

    def get_num_free_sites(self) -> int:
        self._need_setup()
        return self._free_sites
