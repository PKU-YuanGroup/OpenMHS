"""Hardware backend: opens one Ocean Optics spectrometer through the upstream python-seabreeze package.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, so nothing here was run: the acceptance gate uses the fake backend and never imports
this module or the seabreeze package.

``serial_number`` (optional) selects the spectrometer to open with ``Spectrometer.from_serial_number``
(src/seabreeze/spectrometers.py:155); without it the first available unopened device is opened with
``Spectrometer.from_first_available`` (src/seabreeze/spectrometers.py:140).  ``backend`` (optional) selects the
SeaBreeze backend by name before the import, for example ``"pyseabreeze"`` (the upstream README shows
``seabreeze.use('pyseabreeze')``); the default is the package's own default backend.  Opening a spectrometer also
opens the device: the upstream constructor calls ``self.open()`` and caches the wavelengths and the dark-pixel
indices, so a device that is already open is not shared by two Spectrometer objects.
"""


def connect(serial_number=None, backend=None):
    """Open one spectrometer and return the upstream Spectrometer object."""
    if backend is not None:
        import seabreeze

        seabreeze.use(str(backend))
    from seabreeze.spectrometers import Spectrometer

    if serial_number is None:
        return Spectrometer.from_first_available()
    return Spectrometer.from_serial_number(str(serial_number))
