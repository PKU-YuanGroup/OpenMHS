"""Hardware backend: open the pinned upstream RunzeSyringePump over pyserial.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json.  The acceptance gate runs the fake backend and never imports this module.

The upstream constructor has two behaviours a hardware factory must not inherit silently:

* ``max_volume`` is a constructor option (runze_backbone.py:81-85).  It is the syringe volume the position and
  velocity conversions use, so this factory requires ``max_volume_ml`` instead of taking the upstream's 25.0
  default as if it were the installed syringe.
* the constructor catches ``OSError``/``SerialException`` and stores the port string in ``hardware_interface``
  instead of raising (runze_backbone.py:94-106).  This factory checks for a serial-like object and fails instead
  of returning a pump whose first command would fail on a string.

Required options: ``port`` (the serial device), ``address`` (the pump address on that line) and ``max_volume_ml``
(the installed syringe volume in mL).  The factory does not home or initialize the pump: ``initialize()`` sends
``Z`` and moves the mechanism (runze_backbone.py:166-175), so that motion stays an operator decision outside the
MHS envelope.
"""


def connect(port, address, max_volume_ml, **options):
    """Open one addressed Runze pump; no initialization or motion happens here."""
    del options
    if not port:
        raise ValueError("the hardware backend needs port")
    if not address:
        raise ValueError("the hardware backend needs address")
    if max_volume_ml is None:
        raise ValueError("the hardware backend needs max_volume_ml (the installed syringe volume in mL)")

    from unilabos.devices.pump_and_valve.runze_backbone import RunzeSyringePump

    pump = RunzeSyringePump(str(port), str(address), float(max_volume_ml))
    if not hasattr(pump.hardware_interface, "read_until") or not hasattr(pump.hardware_interface, "write"):
        raise RuntimeError(
            "RunzeSyringePump stored a non-serial object in hardware_interface; "
            "the serial line did not open (runze_backbone.py:94-106)")
    return pump
