"""Hardware backend: a bounded socket opener for ``pf400_driver.pf400_driver.tcp_driver:PF400``.

The gate never imports this module. ``connect`` runs only when an operator loads the hardware backend. The package
is R2 and model-authored, so the loader refuses that backend until a human signs ``reviewed_by`` in driver.lock.json.
Nothing here was run against a robot.

The driver does not call ``send_command`` or ``stop_robot``. ``send_command`` (tcp_driver.py:129-174) receives with
no timeout and returns the string ``failed`` on ``socket.error``. ``stop_robot`` (399-409) sends ``halt`` through
that path, which is the robot port. The client says a second motion command will not reply until the first
motion is complete (tcp_driver.py:19). The mailbox wait until the handler returns is Main.gpl:203-209. The
status-port halt lives in driver.py, where the tests can see each exchange. This module only opens and closes the socket, which is what ``connect_robot`` (103-119) and
``disconnect_robot`` (125-127) do, with three differences the e-stop needs:

* a connect timeout capped by the 15 s e-stop latency (``latency_ms=15000``), so one connect cannot
  outlive the declared stop;
* ``OSError`` is raised, and the socket is closed, instead of falling off the end of ``connect_robot`` (that path
  returns ``None``);
* the constructor does not read ``robot_data.json``, does not call ``check_robot_state``, and does not open the
  import-time log file under ``pf400_logs``.

``host`` is required and is deployment data. The README examples are 192.168.50.50 (README.md:8) and
146.137.240.35 (README.md:31); neither is a pin. ``robot_port`` is the port stored on ``self.port``. The driver
assigns ``port`` before each ``connect_robot``, including the status port. ``status_port``, ``connect_timeout_s``
and ``read_timeout_s`` are connection settings of this package, not controller facts. ``stop_confirm_s`` is a
driver option. The SDK passes every option into this factory (``Driver.open_native``), so the factory accepts it
and does not open a socket with it. The driver reads it in ``setup``.
"""

from __future__ import annotations

import errno
import select
import socket
import threading
import time

DEFAULT_CONNECT_TIMEOUT_S = 1.0
DEFAULT_READ_TIMEOUT_S = 1.0
#: Matches ``PF400Arm`` ``@estop(latency_ms=15000)``. A configured connect or read must fit in that stop.
ESTOP_LATENCY_S = 15.0


def connect(*, host, robot_port=10100, status_port=10000, connect_timeout_s=DEFAULT_CONNECT_TIMEOUT_S,
            read_timeout_s=DEFAULT_READ_TIMEOUT_S, stop_confirm_s=None):
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host is required and is the operator's PF400 address, not a fact from the clone")
    for name, value in (("robot_port", robot_port), ("status_port", status_port)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 65536:
            raise ValueError(f"{name} must be a TCP port number")
    if robot_port == status_port:
        raise ValueError("robot_port and status_port must differ")
    for name, value in (("connect_timeout_s", connect_timeout_s), ("read_timeout_s", read_timeout_s)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < float(value) <= ESTOP_LATENCY_S:
            raise ValueError(f"{name} must be a number of seconds in (0, {ESTOP_LATENCY_S:g}]")
    if stop_confirm_s is not None and (isinstance(stop_confirm_s, bool) or not isinstance(stop_confirm_s, (int, float))
                                       or not 0 < float(stop_confirm_s) <= ESTOP_LATENCY_S):
        raise ValueError("stop_confirm_s must be a number of seconds in (0, 15]")
    return BoundedPF400(host.strip(), int(robot_port), connect_timeout_s=float(connect_timeout_s),
                        read_timeout_s=float(read_timeout_s))


class BoundedPF400:
    """``connect_robot`` / ``disconnect_robot`` with a timeout. No command is sent here."""

    def __init__(self, host, port, *, connect_timeout_s, read_timeout_s):
        self.host = host
        self._connect_timeout_s = connect_timeout_s
        self._read_timeout_s = read_timeout_s
        self.port = port

    @property
    def port(self):
        """Port bound by the calling thread. ``connect_robot`` reads it (tcp_driver.py:117)."""
        ports = getattr(self, "_thread_ports", None)
        if ports:
            bound = ports.get(threading.get_ident())
            if bound is not None:
                return bound
        return getattr(self, "_port_value", 10100)

    @port.setter
    def port(self, value):
        self._port_value = value
        ports = getattr(self, "_thread_ports", None)
        if ports is None:
            ports = {}
            self._thread_ports = ports
        ports[threading.get_ident()] = value

    def connect_robot(self):
        """Open one TCP socket to ``(host, port)``. A failure raises; it does not return ``None``.

        The port is the value bound on this thread, copied before the handshake. A cancel flag on this
        thread (``pf400_connect_cancel``) or the connect budget closes the socket instead of leaving it
        in progress. The budget is still at most the configured timeout, which setup caps at 15 s.
        """
        port = int(self.port)
        host = self.host
        cancel = getattr(threading.current_thread(), "pf400_connect_cancel", None)
        deadline = time.monotonic() + float(self._connect_timeout_s)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        try:
            err = sock.connect_ex((host, port))
            while err in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK, errno.EAGAIN):
                if cancel is not None and cancel.is_set():
                    raise TimeoutError("connect exceeded the deadline")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("connect exceeded the deadline")
                _, writable, _ = select.select([], [sock], [], min(0.05, remaining))
                if not writable:
                    continue
                err = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err != 0:
                raise ConnectionError(f"connect {host}:{port} failed (errno {err})")
            sock.setblocking(True)
            sock.settimeout(self._read_timeout_s)
            return sock
        except OSError as exc:
            sock.close()
            raise ConnectionError(f"connect {host}:{port} failed ({type(exc).__name__})") from exc
        except Exception:
            sock.close()
            raise

    def disconnect_robot(self, sock):
        """Close the socket ``connect_robot`` returned (tcp_driver.py:125-127)."""
        sock.close()
