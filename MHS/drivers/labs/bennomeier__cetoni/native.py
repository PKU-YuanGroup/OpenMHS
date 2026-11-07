"""Hardware backend: open a Cetoni Nemesys syringe pump through the upstream ``cetoniSerial`` module.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2, so the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream package.

The upstream module is the single file ``cetoniSerial.py`` at the root of the clone; it is not a package, so the
clone root has to be importable (or the module installed) before this factory is called.  The upstream module also
imports ``pyserial`` and the standard-library ``telnetlib`` (README.md:6-9, cetoniSerial.py:15-19).

Options of the backend:

* ``port`` (required): the serial device, e.g. "/dev/ttyUSB0";
* ``volume`` (required): the installed syringe volume in uL (the upstream constructor default is not used here);
* ``node`` (required): the node id configured for this syringe in Cetoni Elements;
* ``baudrate``, ``timeout``: serial options, passed to ``Syringe``;
* ``ser``: the serial object of a master syringe for a second syringe on the same line (cetoniSerial.py:45-50);
* any other keyword is passed to ``Syringe``.
"""


def connect(port, volume, node, baudrate=115200, timeout=0.2, ser=None, **options):
    from cetoniSerial import Syringe

    return Syringe(port, baudrate=baudrate, timeout=timeout, volume=volume, ser=ser, node=node, **options)
