"""Hardware backend: opens a PicoScope 5000A/B oscilloscope through the upstream class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The factory imports the pinned
upstream package inside the call, so the fake backend of this package and the acceptance gate never import or run
the clone.  ``resolution_bits`` is the ADC resolution the upstream ``Scope.connect`` accepts: 8, 12, 14, 15 or 16
(src/pico_mcp/scope.py:41-42, 115-143); without it the upstream default of 12 bits applies.  The upstream connect
opens the first available USB unit and raises ``ScopeError`` when the unit is busy or absent (scope.py:123-133).

This package is model-authored and unreviewed.  It is R1, so the loader does not gate its hardware backend on a
``reviewed_by`` signature; nothing in this package ran on an instrument.
"""


def connect(resolution_bits=12):
    from pico_mcp.scope import Scope

    scope = Scope()
    scope.connect(int(resolution_bits))
    return scope
