"""Hardware backend: opens one TCD1304 linear CCD through the PSLab serial handler.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream class imports the
external pslab SDK (TCD1304.py:15-18) and, without a device, creates SerialHandler() itself (TCD1304.py:38); this
factory creates the handler with the options the operator passes and hands it to TCD1304.  The PSLab serial port
and the pslab SDK are host dependencies: the card lists no install command, the clone vendors neither, and this
package never installed, imported or ran them.  The acceptance gate runs the fake backend and never imports this
module.

Options: ``integration_time`` and ``master_clock_frequency`` go to the upstream constructor; every other option
goes to SerialHandler.  The two defaults are the upstream constructor defaults (TCD1304.py:35-36).  Put the pinned
clone root on PYTHONPATH so that the root module TCD1304 is importable.
"""


def connect(integration_time=10e-6, master_clock_frequency=2e6, **options):
    from pslab.serial_handler import SerialHandler
    from TCD1304 import TCD1304

    device = SerialHandler(**options)
    return TCD1304(device=device, integration_time=integration_time,
                   master_clock_frequency=master_clock_frequency)
