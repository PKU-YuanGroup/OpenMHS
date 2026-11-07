"""Hardware backend: opens an ISEG high-voltage supply through the upstream ``basil`` package.

Used only with backend="hardware" after an operator arms the device; the acceptance gate runs the fake backend and
never imports this module.  The ``basil`` import happens inside :func:`connect` because the pinned clone is not a
dependency of the package; the host that drives the supply installs it at the pinned commit.

The keyword arguments are the operator's configuration, not facts of the clone:

* ``port`` and the other serial settings (``baud_rate``, ``read_termination``, ``write_termination``,
  ``timeout``) go to ``basil.TL.Serial.Serial``; the clone states no baud rate or termination for this class, so
  nothing is defaulted here;
* ``init`` is the hardware layer's init mapping (``channel``, ``n_channel``, ``high_voltage``, ``v_lim``,
  ``autostart``; see the upstream constructor).
"""


def connect(**options):
    """Open the serial line and return an initialised ``basil.HL.iseg_hv:IsegHV``."""
    from basil.HL.iseg_hv import IsegHV
    from basil.TL.Serial import Serial

    init = dict(options.pop("init", {}) or {})
    interface = Serial(dict(options))
    interface.init()
    device = IsegHV(interface, {"init": init})
    device.init()
    return device
