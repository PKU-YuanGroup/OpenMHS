"""Fake backend of the Prior ProScan III driver: an in-memory stand-in for proscan.py:PriorStage.

The upstream class has one move and one shutdown: ``move_to(delta)`` builds the ``G x,y`` serial command and waits
for the reply (proscan.py:152-175), and ``close()`` closes the serial connection (proscan.py:180-186).  This fake
defines exactly those two public methods and the ``port`` and ``lock`` attributes BaseStage sets
(base_stage.py:18-20); all other state is private so gate G7 has no invented public surface.

It is not a recording and it models no stage physics.  A move takes a fixed placeholder time instead of the
controller's real travel time, and ``close()`` closes the link without stopping a move that is already in progress,
which is what the upstream ``close()`` does: it only closes the serial connection.  The target set and the close
count are placeholders for this stand-in, not facts about a device.  Nothing here talks to hardware.

Two failure paths follow the upstream's shape (model review, 2026-11-05).  A reply other than ``R`` (the private
``_reply``, ``R`` by default) raises RuntimeError after the move was counted as written, as validate_response does
after writing the command (proscan.py:79-115).  A move after ``close()`` raises OSError before anything is
counted: a placeholder for the serial library's own error on a closed port (pyserial, outside the clone), and
deliberately not RuntimeError, which the upstream raises only after a reply.
"""

import threading
import time

_EXPECTED = b"R\r"                             # the reply move_to expects (proscan.py:175)


class FakePriorStage:
    def __init__(self, port="COM1", **_options):
        self.port = port                      # placeholder port, not a device fact
        self.lock = threading.RLock()
        self._closed = False
        self._moving = False
        self._moves = 0
        self._last_target = None
        self._close_calls = 0
        self._move_seconds = 0.01              # placeholder pacing, not the stage's timing
        self._reply = _EXPECTED                # tests may set another reply to take the failure path

    def move_to(self, delta):
        """Record an absolute target; raise after close(), as writing to the closed port would."""
        if self._closed:
            raise OSError("serial port is closed")   # placeholder for the serial library's error
        x = delta["x"]
        y = delta["y"]
        if x is None or y is None:
            return
        self._moving = True
        self._moves += 1
        self._last_target = {"x": float(x), "y": float(y)}
        try:
            time.sleep(self._move_seconds)
            if self._reply != _EXPECTED:
                raise RuntimeError(f"Command failed: expected {_EXPECTED!r}, got {self._reply!r}")
        finally:
            self._moving = False

    def close(self):
        """Close the serial connection; an in-flight move is deliberately not stopped."""
        self._close_calls += 1
        self._closed = True
