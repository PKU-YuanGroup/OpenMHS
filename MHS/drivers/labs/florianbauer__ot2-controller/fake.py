"""Synthetic F0 fake backend for the OT-2 SiLA 2 controller.

This is not a recording and not an upstream simulator: the clone ships no simulator for the feature and no
captured SSH transcript exists.  It stands in for
``ot2_controller.feature_implementations.ot2controller_impl:Ot2ControllerImpl`` and keeps the upstream method
names and keyword-only ``metadata`` argument, so the driver calls the same shape it would call on hardware.

Every value below is test data, marked ``# placeholder``; none of it is a device fact.  What the fake keeps from the
upstream: ``get_AvailableProtocols`` applies the upstream filter verbatim (ot2controller_impl.py:54) to ``ls`` lines
that end in a newline, as Paramiko's ``readlines`` returns them, so it reports an empty list; ``RunProtocol``
returns the exit status and raises ``ValueError`` only for a simulation whose status is not 0 (:127-133).  When the
fake SSH client is closed during a run, the run ends at once without an exit status (-1, what Paramiko's
``recv_exit_status`` gives when the channel closes first; Paramiko is outside the clone).  That models the driver's
side of the channel only: on an OT-2 the remote ``opentrons.execute`` process is not shown to stop, and nothing here
contacts a device.  Attributes starting with ``_`` are knobs of the tests, not upstream members.
"""

from __future__ import annotations

import threading
import time

_RUN_SECONDS = 0.05       # placeholder: models a short run, not a measured protocol duration
_STEP_SECONDS = 0.005     # placeholder: polling interval of the fake
_LS_LINES = ("demo_protocol.py\n",)   # placeholder: one remote ls line, with the newline readlines keeps


class _FakeSSH:
    """The nested Paramiko-like object the driver closes; only ``close`` is reached."""

    def __init__(self):
        self.closed = False
        self._lock = threading.Lock()

    def close(self):
        with self._lock:
            self.closed = True


class FakeOt2Controller:
    def __init__(self, **_options):
        self.ssh = _FakeSSH()
        self.device_ip = "127.0.0.1"                     # placeholder
        self.pkey = None                                 # placeholder: no key in the fake
        self._ls_lines = list(_LS_LINES)
        self._run_seconds = _RUN_SECONDS
        self._exit_status = 0                            # placeholder: the status of the fake remote command
        self._fail = None                                # placeholder: an exception RunProtocol raises once started
        self._runs = []                                  # (ProtocolFile, IsSimulating) of every RunProtocol call

    def _require_open(self):
        if self.ssh.closed:
            # The real client cannot open a channel once it is closed; the exception type is the fake's own.
            raise ConnectionError("the fake SSH client is closed")   # placeholder

    def get_Connection(self, *, metadata=None):
        return "Device IP: 127.0.0.1, SSH key fingerprint: fake"   # placeholder

    def get_AvailableProtocols(self, *, metadata=None):
        self._require_open()
        # The upstream filter verbatim (ot2controller_impl.py:54): the test runs before the newline is stripped.
        return [line.strip() for line in self._ls_lines if line.endswith(".py")]

    def RunProtocol(self, ProtocolFile, IsSimulating, *, metadata=None):
        self._require_open()
        self._runs.append((ProtocolFile, IsSimulating))
        if self._fail is not None:
            raise self._fail
        run_ret = self._exit_status
        deadline = time.monotonic() + self._run_seconds
        while time.monotonic() < deadline:
            if self.ssh.closed:
                run_ret = -1    # placeholder: the channel closed before an exit status arrived
                break
            time.sleep(_STEP_SECONDS)
        if IsSimulating and run_ret != 0:              # as the upstream, ot2controller_impl.py:130-131
            raise ValueError("The simulation of the protocol was not successful.")
        return run_ret
