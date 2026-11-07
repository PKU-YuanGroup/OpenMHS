"""Hardware backend: opens a Thorlabs TPZ001 piezo controller and its TSG001 strain gauge reader.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed: the acceptance gate runs the fake backend and never imports this module or the upstream package, and the
hardware path was never run here.

The upstream module imports pythonnet's ``clr`` and references the Thorlabs Kinesis .NET assemblies by relative path
(``./libs/kinesis/...``; piezo.py:5-18, libs/kinesis/info.txt:1-13).  The operator therefore has to provide the
Kinesis DLLs named by libs/kinesis/info.txt in the clone's ``libs/kinesis`` directory, make the clone root importable
as the module ``piezo``, and start the process with the clone root as its working directory so the relative assembly
references resolve.  This module does not change the process working directory or ``sys.path``.

Options of the backend: ``controller_serial`` (required) and ``reader_serial`` (required) are the serial numbers the
upstream constructor accepts (piezo.py:178-182); the driver reads the strain gauge position, so it needs the reader.
The remaining keyword options are accepted but not passed to the upstream constructor.
"""


def connect(controller_serial, reader_serial, **options):
    """Create and return a ``piezo.PiezoController`` for one controller and its reader."""
    from piezo import PiezoController

    controller = PiezoController(controller_serial, reader_serial)
    if controller.device is None:
        raise RuntimeError(f"the Kinesis API did not create a device for controller serial {controller_serial!r}")
    return controller
