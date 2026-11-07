"""Hardware backend: opens the clone's Ethernet oscilloscope backend.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream class is a stub:
its constructor logs that Ethernet hardware is not implemented and every method delegates to a
``SimulatedOscilloscope`` (ethernet_backend.py:18-55).  This factory therefore reaches the same simulation, not a
real network instrument; the backend option ``config`` is the mapping passed to ``initialize`` (for example
``{"sample_rate": ..., "buffer_size": ...}``, simulation.py:39-45).  The acceptance gate runs the fake backend and
never imports this module or the upstream package, so this package's hardware path has never been tried.

This package is model-authored and unreviewed; it is R1, so the loader's review gate for R2 and R3 does not apply
to it.  An operator must still decide to enable the hardware backend.
"""


async def connect(**options):
    from oscilloscope_mcp.hardware.ethernet_backend import EthernetOscilloscope

    device = EthernetOscilloscope()
    config = dict(options.get("config") or {})
    await device.initialize(config)
    return device
