"""Hardware backend: opens the GW Instek AFG-2225 through the upstream PyMeasure class.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The acceptance gate runs
the package's fake backend and never imports this module or the upstream clone, so nothing in this file has run here
and no hardware was attached.

``visa_resource`` is the VISA resource string the upstream constructor passes to PyMeasure
(src/test_engine/devices/afg2225.py:99-111), for example the clone's simulated ``ASRL5::INSTR`` entry in
``src/test_engine/pyvisa_sim.yaml``.  The upstream repository has no packaging file: deployment puts its
``src/test_engine`` directory on ``PYTHONPATH`` so ``devices.afg2225`` is importable, and supplies PyMeasure and a
VISA backend (``src/test_engine/requirements.txt:4``).  The upstream overrides ``write`` to sleep 0.5 s before
every command (afg2225.py:126-128), so configuration writes and both output-off commands are paced by that delay.
"""


def connect(visa_resource, **options):
    """Construct the upstream AFG2225 for one VISA resource; other options go to the PyMeasure constructor."""
    from devices.afg2225 import AFG2225

    return AFG2225(visa_resource, **options)
