"""Hardware backend: opens a VISA resource and wraps it in the upstream ``pyinstrument.instrument:PSupply``.

Used only with ``backend="hardware"`` and ``--allow-hardware`` (an operator decision).  The upstream constructor
takes an already-open VISA resource and stores it as ``self.PS`` (pyinstrument/instrument.py:61-62); this factory
opens that resource through ``pyvisa`` (the upstream requirements.txt lists pyvisa) and returns the ``PSupply`` the
driver calls.  The package is model-authored and unreviewed, but it is R1: the loader refuses the hardware backend
of an unreviewed model-written package only at R2 and R3, so this note does not claim such a refusal for R1.  A
human must review the package before hardware use; the acceptance gate runs the fake backend and never imports this
module, pyvisa or the upstream package.

The factory passes the backend options through: ``visa_resource`` names the resource (for example
``"TCPIP0::192.0.2.1::inst0::INSTR"``), ``visa_backend`` selects a pyvisa backend, and ``timeout_s`` sets the
resource timeout when given.  No timeout or range is invented here.
"""


def connect(**options):
    import pyvisa

    resource_name = options.get("visa_resource") or options.get("resource")
    if not resource_name:
        raise ValueError("the pyinstrument PSupply hardware backend needs a 'visa_resource' option")
    backend = options.get("visa_backend") or None
    manager = pyvisa.ResourceManager(backend) if backend else pyvisa.ResourceManager()
    resource = manager.open_resource(str(resource_name))
    timeout_s = options.get("timeout_s")
    if timeout_s is not None:
        resource.timeout = max(1, int(float(timeout_s) * 1000.0))
    from pyinstrument.instrument import PSupply

    return PSupply(resource)
