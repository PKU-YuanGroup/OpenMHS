"""Hardware backend: constructs the upstream ThermoFisherVerios object for a Verios SEM.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed, and it is R3: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not
claim it).  The acceptance gate runs the fake backend and never imports this module or the smartem package.

The upstream constructor imports the proprietary ``autoscript_sdb_microscope_client`` vendor SDK and asserts
that ``ip`` is in its params and that the parent directory of ``tempfile`` (default ``./tempfile.bmp``,
smartem/online/microscope.py:183-199) exists.  The factory only constructs the object; the driver's ``setup``
hook calls ``initialize()``, which opens the vendor client and connects to ``ip``
(smartem/online/microscope.py:217-224).  The upstream ``get_image`` writes temporary bitmap and TIFF files
under that directory for the rescan path, so the operator supplies a writable directory.

Options of the backend: ``ip`` (required) is the microscope address passed to ``SdbMicroscopeClient.connect``;
``tempfile`` (optional) names the temporary bitmap path, and any other option is passed in the upstream
``params`` dictionary.
"""


def connect(ip, **options):
    from smartem.online.microscope import ThermoFisherVerios

    params = {"ip": ip}
    params.update(options)
    return ThermoFisherVerios(params=params)
