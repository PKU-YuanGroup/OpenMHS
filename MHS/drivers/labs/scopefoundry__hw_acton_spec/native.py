"""Hardware backend: opens the Acton serial interface class of the pinned upstream clone.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed and declares R1: the loader refuses the hardware backend of a model-authored package
only at R2 and R3, so it does not refuse this one.  Nothing here was run: the acceptance gate uses the fake backend
and never imports this module or the upstream package.

The upstream clone has no ``setup.py`` or ``pyproject.toml``; it is the content of the ScopeFoundryHW plug-in
directory ``ScopeFoundryHW/acton_spec`` (README.md:1-8, and ``__init__.py`` imports both modules relatively).  The
operator therefore either places the clone in that directory of an installed ScopeFoundry package or copies only
``acton_spec_interface.py`` onto ``PYTHONPATH``; the import below tries the canonical package path first.  The serial
interface imports pyserial (acton_spec_interface.py:1) and the ScopeFoundry component also imports ScopeFoundry and
numpy (acton_spec.py:9-15).

Options of this factory: ``port`` (required, the serial device or COM port), ``echo`` (default True, whether the
instrument echoes the command; the upstream comment says USB echo should be disabled, acton_spec.py:28) and
``debug`` (default False).  The upstream constructor's ``dummy`` mode is never used for hardware: it answers every
command with "0" instead of opening the port (acton_spec_interface.py:168-170).
"""


def connect(port, echo=True, debug=False, **_options):
    try:
        from ScopeFoundryHW.acton_spec.acton_spec_interface import ActonSpectrometer
    except ImportError:
        from acton_spec_interface import ActonSpectrometer
    return ActonSpectrometer(port=port, echo=echo, debug=debug, dummy=False)
