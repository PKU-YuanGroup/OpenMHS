"""Hardware backend factory for gh.antercreeper/keyscope-mcp.

The upstream import is confined to connect().  The factory forwards the operator's VISA options and uses the
upstream connection and command methods.  Its one lifecycle override omits the :RUN that upstream close() sends
before closing the VISA handle (keyscope_mcp/scope.py:76-86), so ending an endpoint does not restart acquisition.
"""


class StopPreservingClose:
    """Close the upstream VISA handle without a command that resumes acquisition."""

    def close(self):
        if self._inst is not None:
            self._inst.close()
            self._inst = None


def connect(**_options):
    """Open the upstream ``Oscilloscope`` with the operator's options.

    The options are forwarded to the upstream constructor: ``address`` (the VISA resource string), ``timeout``
    (the VISA timeout in milliseconds) and ``auto_reconnect``.
    """
    from keyscope_mcp.scope import Oscilloscope

    class ControlledScope(StopPreservingClose, Oscilloscope):
        pass

    scope = ControlledScope(**_options)
    if not scope.connected:
        scope.connect()
    return scope
