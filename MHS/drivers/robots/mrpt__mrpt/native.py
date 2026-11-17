"""Hardware backend: opens one Taobotics IMU through MRPT's own pybind11 Python binding.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The acceptance gate runs
the fake backend and never imports this module, MRPT or the serial device; nothing here ran on an IMU.  This package
is model-authored and unreviewed; it is R0, so the loader does not add the human-review refusal that applies at R2
and R3, but no real session has been tried.

The clone is a C++ source tree: the hardware backend needs a built and installed MRPT Python binding for this exact
pin (``mrpt.hwdrivers``, ``mrpt.obs`` and ``mrpt.core``), which the card's empty install block does not provide.
``port`` is required because the operator has to name the serial device; the upstream default ``/dev/ttyUSB0``
(``CTaoboticsIMU.h:115-121``) is not assumed.  ``baudrate`` is optional: when it is omitted the upstream default
921600 is used (the same lines).  ``initialize()`` records a port error in ``ssError`` without raising
(``CTaoboticsIMU.cpp:111-128``), so the factory reads the state and refuses a sensor that did not open.

The sensor model stays the upstream default hfi-a9 (``CTaoboticsIMU.h:130``).  Configuring hfi-b6 is not useful with
this driver: that parser stores no measurement (``CTaoboticsIMU.cpp:144-246``).  A deployment that changed the model
through a configuration file would produce observations the driver skips.
"""


def connect(port=None, baudrate=None, **options):
    if not port or not isinstance(port, str):
        raise RuntimeError("the hardware backend needs port='<serial device>' (for example /dev/ttyUSB0)")
    if baudrate is not None:
        if isinstance(baudrate, bool) or not isinstance(baudrate, int) or baudrate <= 0:
            raise RuntimeError("baudrate must be a positive integer")
    if options:
        raise RuntimeError(f"unknown backend options: {', '.join(sorted(options))}")

    from mrpt.hwdrivers import CGenericSensor, CTaoboticsIMU

    imu = CTaoboticsIMU()
    imu.setSerialPort(port)
    if baudrate is not None:
        imu.setSerialBaudRate(baudrate)
    imu.initialize()
    if imu.getState() == CGenericSensor.ssError:
        raise RuntimeError(f"MRPT could not open the IMU serial device {port!r} (getState() is ssError)")
    return imu
