"""Hardware backend: opens one channel of a Thorlabs Kinesis brushless DC motor controller.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream wrapper needs the
Thorlabs Kinesis .NET assemblies through pythonnet on Windows (kinesis.py:1-13; pyproject.toml:16-17), so this module
imports the upstream package inside the factory and the acceptance gate never imports it.

Options of the backend: ``serial`` (required) is the controller serial number from the Kinesis device list
(kinesis.py:40-52, 224-233), passed as a string like the PyMoDAQ plugin does; ``channel`` (default 1) selects the
controller channel through ``init_channel`` (kinesis.py:230-233).

This package is model-authored and unreviewed.  The loader refuses the hardware backend of an unreviewed model-written
package at R2 and R3 only; this package is R1, so that refusal does not apply and a human review is required before
hardware use.  The acceptance gate runs the fake backend only and no hardware was attached.
"""


def connect(serial, channel=1, **_options):
    from pymodaq_plugins_thorlabs.hardware.kinesis import BrushlessDCMotor

    controller = BrushlessDCMotor()
    controller.connect(str(serial))
    controller.init_channel(int(channel))
    return controller
