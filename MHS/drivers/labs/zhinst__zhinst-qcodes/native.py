"""Hardware backend of the PQSC driver: the upstream zhinst-qcodes instrument over LabOne.

The gate never imports this module.  ``connect`` runs only when an operator loads the
hardware backend (``mhs.adapter.load_driver(..., backend="hardware",
allow_hardware=True, ...)``); it is then the only code that imports zhinst-qcodes,
zhinst-toolkit, qcodes and the LabOne client.  The serial and the data-server host are
deployment data and are never guessed.

The selected native class is the card's entry symbol
``zhinst.qcodes.driver.devices.pqsc:PQSC``.  That class has no session-opening
constructor of its own; the upstream subclass
``zhinst.qcodes.device_creator:PQSC`` creates the ``ZISession`` and calls
``connect_device(serial, interface=interface)`` before it hands the toolkit object to
the base class (src/zhinst/qcodes/device_creator.py:255-276).  The factory therefore
constructs that subclass; the returned object is a ``pqsc:PQSC`` instance.

Nothing here was run: the package has never opened a LabOne session.
"""


def connect(serial, host="localhost", port=8004, *, interface=None, name=None, raw=False,
            new_session=False, allow_version_mismatch=False):
    if not isinstance(serial, str) or not serial.strip():
        raise ValueError("serial must be the serial number of the PQSC (for example dev12000)")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be the LabOne data-server host name or address")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536:
        raise ValueError("port must be a TCP port number of the LabOne data server")
    from zhinst.qcodes.device_creator import PQSC

    return PQSC(serial, host, port=port, interface=interface, name=name, raw=raw,
                new_session=new_session, allow_version_mismatch=allow_version_mismatch)
