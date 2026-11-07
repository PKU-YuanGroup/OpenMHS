"""Hardware backend of the PSI simple positioner: the upstream ophyd Device over EPICS Channel Access.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that
imports ``ophyd_devices.devices.simple_positioner`` and, through it, ophyd and pyepics.  The package was never run:
it has not connected to an IOC.

The device's four Components (user_readback R, user_setpoint S, velocity V and motor_done_move D) are created under
the operator's prefix and name, and ``connect`` waits for the Device's Signals for at most ``connection_timeout_s``.
The construction options are the upstream ones: an optional native soft ``limits`` pair, an optional ``deadband``
and ``override_suffixes``.  ``override_suffixes`` only re-points Signals the class implements (user_readback,
user_setpoint, velocity, motor_done_move); for ``motor_stop``, which PSISimplePositioner does not implement, the
upstream only logs a warning (psi_positioner_base.py:133-146), so no suffix can give this class a stop Signal.  The
upstream stop therefore always reads ``user_readback`` and writes that value into ``user_setpoint`` (a new target,
not a hardware stop).  Model review (2026-11-05): the author's text said a ``motor_stop`` suffix could be added here;
that is not what the pinned source does.  The package does not invent a suffix or a travel range.
"""

import math


def _number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{what} must be a finite number")
    return float(value)


def connect(*, prefix="", name="psi_simple_positioner", connection_timeout_s=5.0,
            limits=None, deadband=None, override_suffixes=None):
    if not isinstance(prefix, str):
        raise ValueError("prefix must be a string (the PV prefix of the axis)")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    timeout = _number(connection_timeout_s, "connection_timeout_s")
    if timeout <= 0:
        raise ValueError("connection_timeout_s must be greater than zero")

    kwargs = {}
    if limits is not None:
        pair = tuple(_number(value, "limits member") for value in limits)
        if len(pair) != 2:
            raise ValueError("limits must be a two-element sequence (low, high)")
        if pair[0] > pair[1]:
            raise ValueError("limits must be ordered low <= high")
        kwargs["limits"] = pair
    if deadband is not None:
        band = _number(deadband, "deadband")
        if band <= 0:
            raise ValueError("deadband must be greater than zero")
        kwargs["deadband"] = band
    if override_suffixes is not None:
        if not isinstance(override_suffixes, dict):
            raise ValueError("override_suffixes must be a mapping of signal name to PV suffix")
        suffixes = {}
        for signal_name, suffix in override_suffixes.items():
            if not isinstance(signal_name, str) or not isinstance(suffix, str):
                raise ValueError("override_suffixes keys and values must be strings")
            suffixes[signal_name] = suffix
        kwargs["override_suffixes"] = suffixes

    from ophyd_devices.devices.simple_positioner import PSISimplePositioner

    device = PSISimplePositioner(prefix=prefix, name=name, **kwargs)
    device.wait_for_connection(timeout=timeout)
    return device
