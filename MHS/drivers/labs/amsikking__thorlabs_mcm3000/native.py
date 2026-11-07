"""Hardware backend: opens the upstream Thorlabs MCM3000 serial controller.

Used only with backend="hardware" and allow_hardware=True (an operator decision); the acceptance gate runs the fake
backend and never imports this module or the upstream package, so the path below was never executed and no hardware
run is claimed.

Options follow ``thorlabs_MCM3000.Controller.__init__`` (thorlabs_MCM3000.py:12-18):

* ``which_port`` (required): the serial port of the controller, for example ``/dev/ttyUSB0`` or ``COM21``;
* ``stages`` (required): a three-entry tuple naming the stage on each channel, e.g.
  ``(None, None, "ZFM2020")``; a ``None`` entry leaves that channel unavailable (thorlabs_MCM3000.py:15, 45-54);
* ``reverse``: a three-entry tuple of booleans reversing the encoder sign per channel (thorlabs_MCM3000.py:16);
* ``name``: the label the upstream prints; ``verbose`` turns the upstream's serial logging on or off.

The controller is opened at 460800 baud with a 5 s read timeout, as the upstream constructor does
(thorlabs_MCM3000.py:26-27).
"""


def connect(which_port, stages, reverse=(False, False, False), name="MCM3000", verbose=False):
    from thorlabs_MCM3000 import Controller

    return Controller(which_port=which_port, name=name, stages=tuple(stages), reverse=tuple(reverse),
                      verbose=bool(verbose))
