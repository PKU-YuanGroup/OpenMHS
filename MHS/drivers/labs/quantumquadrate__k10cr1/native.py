"""Hardware backend: opens a Thorlabs K10CR1 stage through the upstream class.

Used only with backend="hardware" and allow_hardware=True, which is an operator decision.  This package is
model-authored and unreviewed (driver.lock.json ``reviewed_by`` is null); nothing in it ever ran against a device.

Options of the backend:

* ``ser_num`` (required): the serial number of the stage, the single argument of ``K10CR1.__init__``
  (K10CR1/k10cr1.py:9-11).  The constructor calls ``connect()``, which scans every serial port and opens the one
  whose description ends with the serial number at 115200 baud with a 0.1 s timeout (K10CR1/k10cr1.py:20-33), then
  zeroes the backlash (K10CR1/k10cr1.py:18).  Constructing the object is the connection; the class has no close.

The class has no stop, abort or disable method (K10CR1/k10cr1.py:9-189), so a hardware user must keep the lab's own
emergency stop authoritative.  This module imports the upstream package, which the acceptance gate never instals nor
imports.
"""


def connect(ser_num):
    from K10CR1.k10cr1 import K10CR1

    return K10CR1(ser_num)
