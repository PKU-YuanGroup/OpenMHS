"""Hardware backend: open one OpenCyberGlove hand through the vendor SDK.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The acceptance gate runs
the fake backend and never imports this module or the ``open_cyber_glove`` package; nothing here ran on a glove.

Options of the backend: ``hand`` selects which glove this device serves (``left`` or ``right``, matching the
driver's option); ``left_port`` and ``right_port`` are the serial ports (for example ``/dev/ttyUSB0`` or ``COM3``).
Only the port of the selected hand is passed to ``OpenCyberGlove``, which otherwise creates and starts a reader for
each configured port (sdk.py:19-37).  The upstream constructor requires at least one of the two ports (sdk.py:17-18);
a missing port for the selected hand is refused here before the SDK is called.

The upstream ``open_cyber_glove`` package imports torch, open3d, onnxruntime and matplotlib at import time
(glove.py:14-17, visualizer.py:3-5, sdk.py:4-5), so the hardware host needs the dependencies of the card's
``pip install .`` step.  This factory imports the SDK only when a hardware backend is actually opened.
"""


def connect(hand="left", left_port=None, right_port=None, **options):
    if options:
        raise TypeError(f"unknown hardware backend option(s): {sorted(options)}")
    if hand not in ("left", "right"):
        raise ValueError(f"the 'hand' option must be 'left' or 'right', got {hand!r}")
    if hand == "left":
        if not left_port:
            raise RuntimeError("the selected left glove needs left_port (the SDK refuses a construction without "
                               "left_port or right_port)")
        right_port = None
    else:
        if not right_port:
            raise RuntimeError("the selected right glove needs right_port (the SDK refuses a construction without "
                               "left_port or right_port)")
        left_port = None

    from open_cyber_glove.sdk import OpenCyberGlove

    return OpenCyberGlove(left_port=left_port, right_port=right_port)
