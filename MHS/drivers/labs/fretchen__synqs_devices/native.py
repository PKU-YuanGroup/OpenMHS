"""Hardware backend: open the Andor Solis camera through the upstream SynQS labscript worker.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream class
``AndorSolis.blacs_workers:AndorCamera`` imports the Andor SDK binding, which loads the proprietary
``atmcd64d.dll`` or ``atmcd32d.dll`` and is Windows-only (AndorSolis/andor_sdk/andor_solis.py:21-44).  The clone is a
labscript user-device package: the operator places it on the labscript ``userlib/user_devices`` path, and this module
imports it from there.  The acceptance gate runs the fake backend and never imports this module, the upstream package
or the Andor SDK.
"""


def connect(**_options):
    from AndorSolis.blacs_workers import AndorCamera

    return AndorCamera()
