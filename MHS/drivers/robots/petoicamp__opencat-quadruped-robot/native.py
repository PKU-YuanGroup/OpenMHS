"""Hardware backend of the OpenCat driver: open the clone's serial transport.

The gate never imports this module and the hardware backend is never started by a model-authored package until a
human sets ``reviewed_by``.  At deployment the upstream clone must be importable (``serialMaster`` is a namespace
package of the clone) and the serial device must be passed as ``port``.

``baudrate`` defaults to 115200, the rate the firmware README sets for the serial monitor (README.md:149); the
Python API opens the same rate with a one-second timeout (serialMaster/ardSerial.py:725).
"""


def connect(**options):
    from serialMaster.SerialCommunication import Communication

    port = options.get("port")
    if not port:
        raise ValueError("the OpenCat hardware backend needs a serial port (options['port'])")
    baudrate = int(options.get("baudrate", 115200))
    timeout_s = float(options.get("timeout_s", 1.0))
    return Communication(port, baudrate, timeout_s)
