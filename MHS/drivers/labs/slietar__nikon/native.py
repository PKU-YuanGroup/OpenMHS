"""Hardware backend: opens a Nikon Ti2-E microscope through the upstream PyUSB device list.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed.  It is R1, so the loader's review gate, which refuses a model-written hardware backend only at R2 and R3,
does not refuse this one; real hardware use is still an operator decision.  The acceptance gate runs the fake backend
and never imports this module or the nikon package; nothing here ran on a microscope.

Options of the backend:

``index``
    which device of ``MicroscopeDevice.list()`` to open (default 0).
``backend``
    the optional PyUSB backend object ``MicroscopeDevice.list(backend=...)`` accepts
    (nikon/microscope.py:465-474); ``None`` lets PyUSB choose.

The upstream constructor takes the ``usb.core.Device`` that ``list()`` yields, and the driver's methods are async
coroutines on the SDK's persistent event loop.
"""


def connect(*, index=0, backend=None):
    from itertools import islice

    from nikon.microscope import MicroscopeDevice

    devices = islice(MicroscopeDevice.list(backend=backend), index, None)
    try:
        return next(devices)
    except StopIteration:
        raise RuntimeError("no Nikon Ti2-E microscope was found on the USB bus") from None
