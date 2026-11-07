"""A deterministic, in-memory model of the PyLabRobot ``LiquidHandler`` front end, for package fakes.

PyLabRobot ships a chatterbox backend that prints operations, while its front end (``LiquidHandler``) enforces tip
and volume bookkeeping.  A package fake composes this model to stand in for that front end without importing
PyLabRobot; the package's own fake class provides the upstream object around it (for example a digital twin that
holds the handler at ``env.lh``).  Every number a package passes here (well and tip capacities, starting liquid)
is test data: mark it ``# placeholder`` in ``fake.py`` and never copy it into a Fact or a Limit.

Behaviour follows the front-end checks of PyLabRobot's ``liquid_handling/liquid_handler.py`` (a vendored copy is
pinned in the corpus at ``labs/aicell-lab/hamilton-control``): operations need ``setup()`` first
(``machines/machine.py`` ``need_setup_finished``); ``setup()`` twice is refused; a pick-up onto a channel that holds a
tip, or from a spot without a tip, fails; aspirating needs a tip on the channel and enough tracked liquid in the
well and room in the tip; dispensing needs liquid in the tip and room in the well; ``discard_tips()`` without
``use_channels`` discards every tip the head tracks and fails when there is none.  Error names mirror PyLabRobot's
(``NoTipError``, ``HasTipError``, ``TooLittleLiquidError``, ``TooLittleVolumeError``); they are local classes, not
PyLabRobot's.  Nothing here models motion, timing, liquid classes, offsets or a 96-head.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

__all__ = ["FakeDeck", "FakeLiquidHandler", "FakePlate", "FakeTipRack", "HasTipError", "NoTipError",
           "ResourceNotFoundError", "TooLittleLiquidError", "TooLittleVolumeError", "well_names"]


class NoTipError(RuntimeError):
    """A channel or tip spot has no tip (PyLabRobot ``NoTipError``)."""


class HasTipError(RuntimeError):
    """A channel already holds a tip (PyLabRobot ``HasTipError``)."""


class TooLittleLiquidError(RuntimeError):
    """Less tracked liquid than requested (PyLabRobot ``TooLittleLiquidError``)."""


class TooLittleVolumeError(RuntimeError):
    """Less free volume than requested (PyLabRobot ``TooLittleVolumeError``)."""


class ResourceNotFoundError(KeyError):
    """No resource of that name on the deck (PyLabRobot ``ResourceNotFoundError``)."""


def well_names(rows: int, columns: int) -> list[str]:
    """``A1``.. identifiers of an itemized resource, row letter first, column-major like PyLabRobot."""
    if not (1 <= rows <= 16 and 1 <= columns <= 24):
        raise ValueError("rows must be 1-16 and columns 1-24")
    return [f"{chr(ord('A') + row)}{column}" for column in range(1, columns + 1) for row in range(rows)]


class _VolumeTracker:
    """``get_used_volume()`` and ``get_free_volume()`` of one well or tip (PyLabRobot ``VolumeTracker``)."""

    def __init__(self, max_volume: float, volume: float = 0.0):
        self.max_volume = float(max_volume)
        self.volume = float(volume)

    def get_used_volume(self) -> float:
        return self.volume

    def get_free_volume(self) -> float:
        return self.max_volume - self.volume

    def remove_liquid(self, volume: float) -> None:
        if volume > self.volume:
            raise TooLittleLiquidError(f"there is {self.volume} uL, {volume} uL was requested")
        self.volume -= volume

    def add_liquid(self, volume: float) -> None:
        if volume > self.get_free_volume():
            raise TooLittleVolumeError(f"there is room for {self.get_free_volume()} uL, {volume} uL was requested")
        self.volume += volume


class _Well:
    def __init__(self, name: str, max_volume: float, volume: float):
        self.name = name
        self.tracker = _VolumeTracker(max_volume, volume)


class _TipTracker:
    """``has_tip`` of a tip spot or a channel (PyLabRobot ``TipTracker``)."""

    def __init__(self, has_tip: bool):
        self.has_tip = bool(has_tip)


class _TipSpot:
    def __init__(self, name: str, tip_volume: float, has_tip: bool):
        self.name = name
        self.tip_volume = float(tip_volume)
        self.tracker = _TipTracker(has_tip)


class _Itemized:
    def __init__(self, name: str, items: dict[str, Any], rows: int, columns: int):
        self.name = name
        self._items = items
        self.num_items_y = rows       # PyLabRobot ItemizedResource rows
        self.num_items_x = columns    # PyLabRobot ItemizedResource columns

    def get_item(self, identifier: str) -> Any:
        try:
            return self._items[identifier]
        except KeyError:
            raise IndexError(f"{self.name} has no item {identifier!r}") from None

    def item_names(self) -> list[str]:
        return list(self._items)


class FakePlate(_Itemized):
    """A plate whose wells track liquid; ``volumes`` sets placeholder starting volumes per well."""

    def __init__(self, name: str, *, rows: int, columns: int, max_volume: float,
                 volumes: dict[str, float] | None = None):
        start = dict(volumes or {})
        wells = {well: _Well(f"{name}_{well}", max_volume, start.pop(well, 0.0)) for well in well_names(rows, columns)}
        if start:
            raise ValueError(f"{name}: no wells {sorted(start)}")
        super().__init__(name, wells, rows, columns)


class FakeTipRack(_Itemized):
    """A tip rack whose spots start full unless ``empty`` lists spots without a tip."""

    def __init__(self, name: str, *, rows: int, columns: int, tip_volume: float, empty: Iterable[str] = ()):
        missing = set(empty)
        spots = {spot: _TipSpot(f"{name}_{spot}", tip_volume, spot not in missing)
                 for spot in well_names(rows, columns)}
        super().__init__(name, spots, rows, columns)


class FakeDeck:
    """``get_resource(name)`` over the resources a package places, plus a trash area."""

    def __init__(self, resources: Sequence[Any]):
        self._resources: dict[str, Any] = {}
        for resource in resources:
            if resource.name in self._resources:
                raise ValueError(f"duplicate resource {resource.name!r}")
            self._resources[resource.name] = resource

    def get_resource(self, name: str) -> Any:
        try:
            return self._resources[name]
        except KeyError:
            raise ResourceNotFoundError(f"resource {name!r} is not on the deck") from None


class _Tip:
    def __init__(self, max_volume: float):
        self.tracker = _VolumeTracker(max_volume)


class _ChannelTracker:
    def __init__(self):
        self.tip: _Tip | None = None

    @property
    def has_tip(self) -> bool:
        return self.tip is not None

    def get_tip(self) -> _Tip:
        if self.tip is None:
            raise NoTipError("channel has no tip")
        return self.tip


class FakeLiquidHandler:
    """The front-end calls the PyLabRobot helper makes, with PyLabRobot's bookkeeping checks.

    ``calls`` lists every completed operation as ``(name, detail)``; a package test reads it.
    """

    def __init__(self, deck: FakeDeck, *, num_channels: int):
        if not 1 <= int(num_channels) <= 96:
            raise ValueError("num_channels must be 1-96")
        self.deck = deck
        self.num_channels = int(num_channels)
        self.head = {channel: _ChannelTracker() for channel in range(self.num_channels)}
        self.setup_finished = False
        self.calls: list[tuple[str, Any]] = []

    # -- lifecycle (Machine.setup / Machine.stop) ------------------------------------------------------------
    async def setup(self, **_backend_kwargs: Any) -> None:
        if self.setup_finished:
            raise RuntimeError("The setup has already finished. See `LiquidHandler.stop`.")
        self.setup_finished = True
        self.calls.append(("setup", None))

    async def stop(self) -> None:
        self._need_setup()
        self.setup_finished = False
        self.calls.append(("stop", None))

    # -- operations -----------------------------------------------------------------------------------------
    def _need_setup(self) -> None:
        if not self.setup_finished:
            raise RuntimeError("The setup has not finished. See `setup`.")

    def _channels(self, use_channels: Sequence[int] | None, count: int) -> list[int]:
        channels = list(range(count)) if use_channels is None else [int(item) for item in use_channels]
        if len(channels) != count:
            raise ValueError("use_channels and the resources must have the same length")
        for channel in channels:
            if channel not in self.head:
                raise ValueError(f"channel {channel} does not exist")
        if len(set(channels)) != len(channels):
            raise ValueError("a channel is used twice")
        return channels

    async def pick_up_tips(self, tip_spots: Sequence[Any], use_channels: Sequence[int] | None = None,
                           **_backend_kwargs: Any) -> None:
        self._need_setup()
        channels = self._channels(use_channels, len(tip_spots))
        for channel, spot in zip(channels, tip_spots):
            if self.head[channel].has_tip:
                raise HasTipError(f"channel {channel} already has a tip")
            if not spot.tracker.has_tip:
                raise NoTipError(f"tip spot {spot.name} has no tip")
        for channel, spot in zip(channels, tip_spots):
            spot.tracker.has_tip = False
            self.head[channel].tip = _Tip(spot.tip_volume)
        self.calls.append(("pick_up_tips", [spot.name for spot in tip_spots]))

    async def aspirate(self, resources: Sequence[Any], vols: Sequence[float],
                       use_channels: Sequence[int] | None = None, flow_rates: Any = None,
                       **_backend_kwargs: Any) -> None:
        self._need_setup()
        channels = self._channels(use_channels, len(resources))
        volumes = [float(item) for item in vols]
        if len(volumes) != len(resources):
            raise ValueError("vols and resources must have the same length")
        tips = [self.head[channel].get_tip() for channel in channels]
        for well, tip, volume in zip(resources, tips, volumes):
            if volume > well.tracker.get_used_volume():
                raise TooLittleLiquidError(f"{well.name} holds {well.tracker.get_used_volume()} uL, {volume} uL "
                                           "was requested")
            if volume > tip.tracker.get_free_volume():
                raise TooLittleVolumeError(f"the tip has room for {tip.tracker.get_free_volume()} uL")
        for well, tip, volume in zip(resources, tips, volumes):
            well.tracker.remove_liquid(volume)
            tip.tracker.add_liquid(volume)
        self.calls.append(("aspirate", [well.name for well in resources]))

    async def dispense(self, resources: Sequence[Any], vols: Sequence[float],
                       use_channels: Sequence[int] | None = None, flow_rates: Any = None,
                       **_backend_kwargs: Any) -> None:
        self._need_setup()
        channels = self._channels(use_channels, len(resources))
        volumes = [float(item) for item in vols]
        if len(volumes) != len(resources):
            raise ValueError("vols and resources must have the same length")
        tips = [self.head[channel].get_tip() for channel in channels]
        for well, tip, volume in zip(resources, tips, volumes):
            if volume > tip.tracker.get_used_volume():
                raise TooLittleLiquidError(f"the tip holds {tip.tracker.get_used_volume()} uL")
            if volume > well.tracker.get_free_volume():
                raise TooLittleVolumeError(f"{well.name} has room for {well.tracker.get_free_volume()} uL")
        for well, tip, volume in zip(resources, tips, volumes):
            tip.tracker.remove_liquid(volume)
            well.tracker.add_liquid(volume)
        self.calls.append(("dispense", [well.name for well in resources]))

    async def discard_tips(self, use_channels: Sequence[int] | None = None, allow_nonzero_volume: bool = True,
                           **_backend_kwargs: Any) -> None:
        self._need_setup()
        if use_channels is None:
            channels = [channel for channel, tracker in self.head.items() if tracker.has_tip]
        else:
            channels = self._channels(use_channels, len(use_channels))
        if not channels:
            raise RuntimeError("No tips have been picked up and no channels were specified.")
        for channel in channels:
            tip = self.head[channel].get_tip()
            if not allow_nonzero_volume and tip.tracker.get_used_volume() > 0:
                raise RuntimeError(f"the tip on channel {channel} still holds liquid")
        for channel in channels:
            self.head[channel].tip = None
        self.calls.append(("discard_tips", channels))
