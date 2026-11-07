"""Hardware backend: opens a Tricontinent C3000 syringe pump through PyLabware.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the PyLabware package.

The upstream constructor takes the device name, the connection mode, the address, the port, the switch address and
the valve type (PyLabware/devices/tricontinent_c3000.py:295-296); PyLabware itself fixes the serial line at 9600 baud,
8 data bits and no parity (PyLabware/devices/tricontinent_c3000.py:315-317).  ``switch_address`` selects the pump on a
shared serial line (PyLabware/devices/tricontinent_c3000.py:321-328).  Give ``port`` for a serial line or ``address``
and ``port`` for a TCP/IP line (docs/usage.rst:23-32 and 37-41).
"""


def connect(port, device_name="c3000", connection_mode="serial", address=None, switch_address=None,
            valve_type="3PORT_DISTR_IOBE", **options):
    from PyLabware.devices.tricontinent_c3000 import C3000SyringePump

    device = C3000SyringePump(device_name, connection_mode, address, port, switch_address, valve_type)
    device.connect()
    return device
