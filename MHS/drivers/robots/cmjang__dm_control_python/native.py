"""Hardware backend: opens the serial-to-CAN adapter and the ``DM_CAN.MotorControl`` on it.

Used only with backend="hardware" and allow_hardware=True (an operator decision); the acceptance gate runs the fake
backend and never imports this module or DM_CAN.  The clone is not a dependency of the package: the host installs
DM_CAN.py and pyserial.

Options (the keyword arguments of the backend factory, ``Driver(options=...)``):

* ``port`` and any other serial setting (``baudrate``, ``timeout``, ``parity``, ...) go to ``serial.Serial``.  The
  README opens the adapter with 921600 baud and a 0.5 s timeout (README.md:67); that is the example's setting, so
  nothing is defaulted here;
* ``slave_id``, ``master_id`` and ``motor_type`` are the identity the driver registers with ``addMotor``.  They are
  required: a missing identity would address the wrong motor on a shared CAN bus, so the factory refuses to open.
  The driver's own defaults for them (the README example motor) exist for the fake backend only.
"""


def connect(port=None, slave_id=None, master_id=None, motor_type=None, **serial_options):
    """Open the adapter and return a ``MotorControl`` that speaks to the configured motor."""
    from DM_CAN import MotorControl
    from serial import Serial

    missing = [name for name, value in (("port", port), ("slave_id", slave_id), ("master_id", master_id),
                                        ("motor_type", motor_type)) if value is None]
    if missing:
        raise RuntimeError(f"the backend option(s) {missing} are required: port names the serial adapter, the other "
                           "three name the motor on the CAN bus")
    return MotorControl(Serial(port=port, **serial_options))
