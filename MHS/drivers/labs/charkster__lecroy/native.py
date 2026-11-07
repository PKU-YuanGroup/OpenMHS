"""Hardware backend: opens a LeCroy oscilloscope through the upstream ``lecroy`` class.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The factory imports the
pinned upstream module and pyvisa inside the call, so the fake backend of this package and the acceptance gate
never import or run the clone.  The upstream class expects a pyvisa instrument object (lecroy.py:7-10); this
factory opens that resource with pyvisa and passes it in.  ``resource_name`` is the VISA address of the instrument,
for example ``TCPIP0::192.0.2.10::INSTR``.

This package is model-authored and unreviewed.  It is R1, so the loader does not gate its hardware backend on a
``reviewed_by`` signature; nothing in this package ran on an instrument.
"""


def connect(resource_name=None, pyvisa_instr=None, num_channels=8, debug=False, **options):
    from lecroy import lecroy

    if pyvisa_instr is None:
        if not resource_name:
            raise ValueError("resource_name (a VISA address) or pyvisa_instr is required")
        import pyvisa

        pyvisa_instr = pyvisa.ResourceManager().open_resource(str(resource_name))
    return lecroy(pyvisa_instr, num_channels=int(num_channels), debug=bool(debug))
