"""Hardware backend: opens a JDS6600 over its USB-CDC serial port and adapts the typed upstream configs.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed: the acceptance gate runs the fake backend and never imports this module or the upstream package.
At R1 the loader does not gate the hardware backend on reviewed_by, so starting it is an operator decision, not a
protection this package provides.

The upstream class (:class:`hwtools.drivers.joyit.jds6600.JDS6600`) takes typed pydantic configs and the
``SigGenChannel`` enum.  The driver passes plain values so the same code runs against the in-memory fake without
installing the upstream; this adapter converts at the hardware boundary.  The serial settings are the upstream
constructor defaults (jds6600.py:121-124); the port is a deployment choice, not a device Fact.
"""

from types import SimpleNamespace


def _channel(value):
    from hwtools.model.siggen import SigGenChannel

    return SigGenChannel(int(value))


class _Adapter:
    """The upstream JDS6600 with the same public methods over plain channel configurations."""

    def __init__(self, device):
        self._device = device

    # -- connection -----------------------------------------------------------
    def connect(self):
        self._device.connect()

    def disconnect(self):
        self._device.disconnect()

    def idn(self):
        return self._device.idn()

    # -- configuration --------------------------------------------------------
    def configure_channel(self, setup):
        from hwtools.model.siggen import SignalGeneratorConfig

        self._device.configure_channel(SignalGeneratorConfig(
            channel=_channel(setup.channel),
            waveform=setup.waveform,
            frequency_hz=setup.frequency_hz,
            amplitude_vpp=setup.amplitude_vpp,
            offset_v=setup.offset_v,
            duty_pct=setup.duty_pct,
            enabled=setup.enabled,
            arb_slot=setup.arb_slot,
        ))

    def enable_output(self, channel, on):
        self._device.enable_output(_channel(channel), on)

    def set_phase_deg(self, degrees):
        self._device.set_phase_deg(degrees)

    # -- readback -------------------------------------------------------------
    def read_channel(self, channel):
        config = self._device.read_channel(_channel(channel))
        return SimpleNamespace(
            channel=int(config.channel),
            waveform=str(config.waveform),
            frequency_hz=float(config.frequency_hz),
            amplitude_vpp=float(config.amplitude_vpp),
            offset_v=float(config.offset_v),
            duty_pct=float(config.duty_pct),
            enabled=bool(config.enabled),
            arb_slot=config.arb_slot,
        )

    def output_enabled(self, channel):
        return self._device.output_enabled(_channel(channel))


def connect(port=None, baud=115200, timeout_s=1.0, **options):
    """Open the serial link and return the adapter around the upstream JDS6600."""
    from hwtools.drivers.joyit.jds6600 import JDS6600, find_jds6600_port

    if options:
        raise TypeError(f"unknown backend option(s): {', '.join(sorted(options))}")
    if port is None:
        port = find_jds6600_port()
        if port is None:
            raise RuntimeError("no JDS6600 CH340 serial port found; pass port=/dev/... as a backend option")
    device = JDS6600(port, baud=baud, timeout_s=timeout_s)
    device.connect()
    return _Adapter(device)
