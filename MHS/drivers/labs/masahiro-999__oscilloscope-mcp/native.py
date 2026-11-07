"""Hardware backend: opens a RIGOL DS1000Z-series scope through the upstream package.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The
upstream ``open_scope`` builds a ``ScpiLan`` transport and a ``RigolDs1000z`` over the
model profile; the profile is resolved from ``model`` or auto-detected from *IDN?.

This package is model-authored and unreviewed.  It is R1, so the loader does not refuse
its hardware backend (that refusal applies to a model-authored package at R2 and R3);
nothing here was run, and a human review is required before any hardware use.

Options of the backend: ``host`` (required) is the scope's IP address or hostname,
``port`` is the raw SCPI TCP port (the profile default is 5555), ``model`` is a
``MODEL_REGISTRY`` key such as ``RIGOL_DS1104Z`` (auto-detected when omitted) and
``timeout_s`` is the socket timeout.  The upstream package must be installed for this
module to import; the acceptance gate never imports it.
"""


def connect(host, port=5555, model=None, timeout_s=3.0):
    from oscilloscope_mcp.instruments import open_scope

    return open_scope(host=host, port=port, model=model, timeout_s=timeout_s)
