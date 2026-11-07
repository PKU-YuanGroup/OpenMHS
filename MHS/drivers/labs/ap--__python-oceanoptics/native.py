"""Hardware backend: opens an Ocean Optics QE65000/QE65Pro TEC controller through the upstream pyusb class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The package is checked on the fake backend only; this module was never run against a device and
the acceptance gate never imports it.

``OceanOpticsTEC(model)`` takes the model name from ``OceanOpticsModelConfig`` (oceanoptics/defines.py:16), for
example "QE65000" or "QE65pro", and its inherited ``OceanOpticsUSBComm.__init__`` opens the first USB device that
matches the vendor and product ids (oceanoptics/base.py:58-101).  Constructing ``OceanOpticsTEC`` does not call
``initialize_TEC``; the QE65000/QE65pro instrument classes do that in their own __init__ (oceanoptics/spectrometers/
QE65xxx.py:48, 58), so this factory leaves the TEC off until a setpoint call arrives.  The model is required: the
driver must not guess which spectrometer is attached.
"""


def connect(model, **options):
    if options:
        raise TypeError(f"unsupported backend options: {', '.join(sorted(options))}")
    from oceanoptics.base import OceanOpticsTEC

    return OceanOpticsTEC(model)
