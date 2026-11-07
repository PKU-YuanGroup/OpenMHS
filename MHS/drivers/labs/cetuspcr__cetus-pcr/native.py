"""Hardware backend: opens the upstream Cetus PCR controller functions:ArduinoPCR.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream
package.

The clone is a script bundle, not an installed package: ``functions`` imports ``constants``, which opens
``settings.json`` relative to the current working directory (constants.py:8), and ``functions`` opens the serial
port of the Arduino through pyserial (functions.py:241-243).  Start the endpoint from the clone root (or set that
directory as the working directory) and keep it on ``sys.path`` before calling this factory.  The application's own
call uses baudrate 9600 and timeout 1 (interface.py:872).

Options: ``baudrate`` (default 9600, the firmware's Serial.begin value at
arduino/cetuspcr/cetuspcr.ino:4) and ``timeout`` (default 1, the application's serial timeout at
interface.py:872).  ``experiment`` is the optional ExperimentPCR object of the upstream constructor; the driver
sets the experiment on the controller for each protocol call, so it is normally omitted.
"""


def connect(**options):
    import functions

    baudrate = int(options.pop("baudrate", 9600))
    timeout = float(options.pop("timeout", 1))
    experiment = options.pop("experiment", None)
    if options:
        raise TypeError(f"unknown Cetus PCR hardware options: {sorted(options)}")
    return functions.ArduinoPCR(baudrate=baudrate, timeout=timeout, experiment=experiment)
