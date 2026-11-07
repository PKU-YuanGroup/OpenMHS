"""Fake backend of the Ismatec pump driver: an in-memory stand-in for the upstream class.

Gate G7: every public method defined here exists on
``instruments.ismatec.ismatec:Ismatec`` (``connect``, ``start``, ``stop``,
``set_flowrate`` and ``get_flowrate``).  The instance data ``written``,
``pending`` and ``worker_alive`` are test hooks the driver never reaches.

What the fake keeps from the clone (``src/instruments/ismatec/ismatec.py:44-84``,
``src/instruments/instrument.py:42-63``):

* each public method only hands a request to the worker and returns
  normally; the worker writes the command text the upstream writes (``1H``,
  ``1I``, ``1S`` plus ``str(int(val)).zfill(5)``, ``1S``, each followed by a
  carriage return) and calls the callback with ``True`` or, for
  ``get_flowrate``, with the reply parsed as the upstream parses it
  (split at ``\\r``, stripped of ``*``, ``float()``);
* an exception in a request ends the worker, as it ends the upstream's
  ``_process_queue`` thread: that callback is never called, and every later
  request stays queued and is never written.

What it does not model: it is synchronous (the worker step runs inside the
method call, not on a thread), has no 0.3 s sleeps, no read timeout and no
serial port.  The clone does not say what the pump answers to ``1S``:
unless a ``reply`` is given, the fake answers with the last speed it was
set to (a placeholder model), and a stop does not change that answer, so a
read is no evidence of a stop.  The starting speed is a placeholder, not a
fact.
"""


class FakeIsmatec:
    """An in-memory Ismatec controller with the upstream method signatures."""

    def __init__(self, reply=None, **_options):
        self._port = "fake"                # placeholder
        self._ser = None                   # no serial line: nothing is opened
        self._rate = 0.0                   # placeholder: the clone names no startup speed
        self._reply = reply                # None: answer 1S with the stored speed; else this raw reply text
        self.written = []                  # test hook: the command text the worker wrote, in order
        self.pending = []                  # test hook: requests queued after the worker ended (never written)
        self.worker_alive = True           # test hook: False once a request raised in the worker
        self.worker_error = None           # test hook: the exception that ended the worker

    def connect(self):
        """The upstream connect() opens the serial line and writes '@1' and '1M' (ismatec.py:39-42)."""
        self._ser = None
        self.written.extend(["@1\r", "1M\r"])

    def _work(self, command, callback, **kwargs):
        """One request of the upstream worker (_process_queue calling _process_request), run synchronously."""
        if not self.worker_alive:
            self.pending.append(dict(kwargs, command=command))
            return
        try:
            response = True
            if command == "start":
                self.written.append("1H\r")
            elif command == "stop":
                self.written.append("1I\r")
            elif command == "set_flowrate":
                self.written.append("1S" + str(int(kwargs["flowrate"])).zfill(5) + "\r")
                self._rate = float(int(kwargs["flowrate"]))       # placeholder model of the speed setting
            elif command == "get_flowrate":
                self.written.append("1S\r")
                text = f"{self._rate}\r\n" if self._reply is None else self._reply
                response = float(text.split("\r")[0].strip("*"))
            if callback is not None:
                callback(response)
        except Exception as exc:  # noqa: BLE001 - the upstream worker thread ends on any exception
            self.worker_alive = False
            self.worker_error = f"{type(exc).__name__}: {exc}"

    def start(self, callback=None):
        self._work("start", callback)

    def stop(self, callback=None):
        self._work("stop", callback)

    def set_flowrate(self, val, callback=None):
        self._work("set_flowrate", callback, flowrate=val)

    def get_flowrate(self, callback=None):
        self._work("get_flowrate", callback)
