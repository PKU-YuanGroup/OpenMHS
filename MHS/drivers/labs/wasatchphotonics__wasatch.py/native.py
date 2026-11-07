"""Hardware backend: open a Wasatch FID spectrometer through the upstream library.

Used only with backend="hardware" and allow_hardware=True (an operator
decision).  This package is model-authored and unreviewed, and it is R2: the
loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package
must not claim it).  The acceptance gate runs the fake backend and never imports
this module or the wasatch package.

Options of the backend:

* ``device_id``: a ``wasatch.DeviceID.DeviceID`` label, for example
  ``MOCK:name:directory`` for the upstream's mock bus (DeviceID parses that
  form at wasatch/DeviceID.py:164-171);
* ``serial_number``: select the USB device with this serial number from
  ``DeviceFinderUSB.find_usb_devices`` (wasatch/DeviceFinderUSB.py:171);
* ``index``: select the n-th device the finder returns (default 0).

Without a label the first discovered USB device is opened.  The FID constructor
takes a DeviceID (wasatch/FeatureIdentificationDevice.py:57-62); ``connect``
returns a SpectrometerResponse whose data is the connection result
(wasatch/FeatureIdentificationDevice.py:445-447).  The wavelength axis is
generated from the EEPROM wavecal coefficients after the connection
(wasatch/SpectrometerSettings.py:325).
"""


def connect(device_id=None, serial_number=None, index=0, **_options):
    from wasatch.DeviceFinderUSB import DeviceFinderUSB
    from wasatch.DeviceID import DeviceID
    from wasatch.FeatureIdentificationDevice import FeatureIdentificationDevice

    if device_id is not None:
        target = DeviceID(label=str(device_id))
    else:
        found = DeviceFinderUSB().find_usb_devices()
        if serial_number is not None:
            found = [item for item in found if getattr(item, "serial_number", None) == serial_number]
        if not found:
            raise RuntimeError("no Wasatch USB spectrometer found" if serial_number is None else
                               f"no Wasatch USB spectrometer with serial number {serial_number!r}")
        target = found[int(index)]

    device = FeatureIdentificationDevice(device_id=target)
    response = device.connect()
    if response is None or not getattr(response, "data", False):
        raise RuntimeError(f"FeatureIdentificationDevice.connect failed for {target!r}")
    device.settings.update_wavecal()
    return device
