"""SCPI socket reads honour an e-stop interrupt that lands before the read (MERGE-B fix round).

WP-05 round-3 verification (minor): ``SocketTransport.read()`` cleared the
interrupt flag when it started.  Since round 3 a query is written (under the
wire lock) and read (outside it) as two steps, so an e-stop ``interrupt()``
landing between the two was lost and the pending read waited for its full
timeout.  The flag is now cleared when a request begins (``begin_query``), so
the read that follows ends at once with ``InterruptedError``.
"""

from __future__ import annotations

import socket
import threading
import time
import unittest

from mhs.bridge.scpi import SocketTransport


class _SilentServer:
    """A TCP peer that accepts one connection, reads and never answers."""

    def __init__(self) -> None:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.received = bytearray()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        self.listener.settimeout(5.0)
        try:
            conn, _addr = self.listener.accept()
        except OSError:
            return
        conn.settimeout(0.05)
        with conn:
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    return
                if not chunk:
                    return
                self.received.extend(chunk)

    def close(self) -> None:
        self._stop.set()
        self.listener.close()
        self._thread.join(timeout=2.0)


class SocketInterruptWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = _SilentServer()
        self.transport = SocketTransport("127.0.0.1", self.server.port, timeout_s=3.0)

    def tearDown(self) -> None:
        self.transport.close()
        self.server.close()

    def test_an_interrupt_between_write_and_read_ends_the_read(self) -> None:
        self.transport.begin_query()
        self.transport.write("DOOR?")
        self.transport.interrupt()          # the e-stop lands in the write/read window
        started = time.monotonic()
        with self.assertRaises(InterruptedError):
            self.transport.read(timeout_s=3.0)
        self.assertLess(time.monotonic() - started, 1.0)

    def test_an_old_interrupt_does_not_end_the_next_request(self) -> None:
        self.transport.interrupt()          # an earlier e-stop, no read pending
        self.transport.begin_query()        # a new request starts afterwards
        self.transport.write("DOOR?")
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.transport.read(timeout_s=0.3)
        self.assertGreaterEqual(time.monotonic() - started, 0.25)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
