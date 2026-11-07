"""Hardware backend: opens a Runze ZSB-SY01B over the upstream serial class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream package.

Options of the backend:

* ``port`` (required): the serial device, for example ``/dev/ttyUSB0`` or ``COM3``;
* ``syringe_volume_ul`` (required): the volume of the syringe fitted to the pump, one of the values the upstream
  SY01B accepts (25, 50, 125, 500, 1250, 2500 or 5000 uL, ``multichannel_syringe_pump.py:87``).  It is a
  deployment setting, not a library default; the volume-based actions need it, so this factory does not open a
  connection without it;
* ``address``: the Runze bus address; ``None`` lets the upstream class discover it (``runze_device.py:170-178``);
* ``baudrate``: one of 9600, 19200, 38400, 57600 or 115200 bps; ``None`` tries the valid rates
  (``runze_device.py:43-47``);
* ``position_count`` and ``position_map``: the valve port count and optional port names, passed to SY01B as the
  upstream constructor defines them (``multichannel_syringe_pump.py:12-16``).

The constructor opens the serial line and verifies the link by reading the device address
(``runze_device.py:100-143``); it returns the connected SY01B object.
"""


def connect(port, syringe_volume_ul, address=None, baudrate=None, position_count=None, position_map=None):
    from runze_control.multichannel_syringe_pump import SY01B

    return SY01B(com_port=port, baudrate=baudrate, address=address,
                 syringe_volume_ul=syringe_volume_ul,
                 position_count=position_count, position_map=position_map)
