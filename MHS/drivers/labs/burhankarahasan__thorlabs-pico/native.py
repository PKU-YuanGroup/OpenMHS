"""Hardware backend: open the Pi Pico W stepper controller through the upstream serial class.

Used only with backend="hardware" and allow_hardware=True, an operator decision.  This package is model-authored and
unreviewed, and it is R1: the loader's refusal of an unreviewed model-written package's hardware backend applies at
R2 and R3 only, so this R1 factory is not protected by it and must not be run without an operator's review.  No
hardware was run for this package; the acceptance gate uses the fake backend and never imports this module.

The upstream clone has no packaging metadata: stepper_controller.py is a standalone module that imports pyserial
(stepper_controller.py:1) and opens a serial port in its constructor (stepper_controller.py:29).  The clone root
must therefore be importable (for example on PYTHONPATH); driver.lock.json install.notes records this.

Options of the backend: ``port`` (required) is the serial port the Pico W appears on, for example "COM3" or
"/dev/ttyACM0" (stepper_controller.py:20); ``baudrate`` and ``timeout`` are passed to the upstream constructor
(stepper_controller.py:15).
"""


def connect(port, baudrate=115200, timeout=1.0):
    from stepper_controller import PicoStepperController

    return PicoStepperController(port=port, baudrate=baudrate, timeout=timeout)
