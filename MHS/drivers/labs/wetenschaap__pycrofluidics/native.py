"""Hardware backend: opens an Elveflow OB1 through the upstream pycrofluidics class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the pycrofluidics package.

Options of the backend: ``device_name`` is the NI MAX name of the OB1 and ``device_id`` selects an ``ob1_<id>_name``
entry of the upstream config file (``pycrofluidics/elveob.py:69-91``); ``dll`` and ``sdk`` are the Elveflow DLL and
Python-SDK directories (``pycrofluidics/elveob.py:106-116``); ``regulators`` is the four-entry regulator list the OB1
constructor takes (``pycrofluidics/elveob.py:34-37``); ``calibration`` is the JSON calibration file, and when it is
left None ``loadCallibration()`` reads the configured default (``pycrofluidics/elveob.py:118-139``).  The pressure
functions pass the calibration array to the DLL, so the factory loads it before returning the device
(``pycrofluidics/elveob.py:197``, ``:213``).
"""


def connect(*, device_name=None, device_id=None, dll=None, sdk=None, regulators=None, calibration=None):
    from pycrofluidics.elveob import OB1elve

    options = {}
    if regulators is not None:
        options["deviceRegulators"] = list(regulators)
    device = OB1elve(elveflowDLL=dll, elveflowSDK=sdk, deviceName=device_name, deviceID=device_id, **options)
    device.open()
    try:
        device.loadCallibration(calibration)
    except BaseException:
        device.close()
        raise
    return device
