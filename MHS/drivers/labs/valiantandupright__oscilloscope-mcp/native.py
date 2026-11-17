"""Hardware backend: open the pinned upstream ``osc.scope:Scope`` over NI-VISA USBTMC.

Used only with backend="hardware" (an operator decision); the acceptance gate runs the fake backend and never
imports this module or the upstream package.  The clone has no setup.py/pyproject, so there is no installable
distribution: the operator must make the clone's ``osc`` package importable (for example ``PYTHONPATH=<clone>``)
and install the two dependencies of the clone's requirements.txt (pyvisa and mcp) plus NI-VISA or a compatible VISA
library.  ``address`` is the VISA resource string (empty means "first USB resource", the upstream
``Scope._resolve_address`` scan) and ``library`` overrides the VISA library path (the upstream defaults to
``C:\\Windows\\System32\\visa32.dll`` and honours SCOPE_VISA_LIBRARY, osc/config.py:19-21 and scope.py:122-127).

This package is model-authored and unreviewed; no hardware backend, instrument or VISA library was ever opened.
"""


def connect(address=None, library=None):
    from osc.scope import Scope

    return Scope(address=address, library=library)
