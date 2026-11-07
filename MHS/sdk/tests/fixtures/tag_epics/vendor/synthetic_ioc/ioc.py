"""Synthetic Channel Access IOC text for the OpenMHS tag-bridge SDK tests (original, never executed)."""
from caproto.server import PVGroup, pvproperty


class LampIOC(PVGroup):
    """A made-up lamp controller; the PV prefix is chosen by whoever runs it."""

    state = pvproperty(value=0, doc="lamp on (1) or off (0)")
    brightness = pvproperty(value=0.0, doc="measured brightness")
    label = pvproperty(value="idle", dtype=str, doc="status text")
