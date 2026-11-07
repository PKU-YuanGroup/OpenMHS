"""Helpers for a driver package's ``test_driver.py`` (and for the acceptance gate itself).

::

    from mhs.testing import check_driver

    report = check_driver(HERE, backend="fake")     # gates G1-G8; G9 is the run of this very file
    assert report["failed"] == [], report

* :func:`check_driver` runs the acceptance gate (:mod:`mhs.driver.check`)
  in-process and returns the ``check-report.json`` document without writing
  it.  Inside the gate's own run of ``test_driver.py`` (gate G9) it skips G9,
  so the gate never recurses.
* :class:`Recorder` / :func:`log_of` -- a recording proxy around a backend
  object; unknown attributes raise :class:`AttributeError` (never invented).
* :class:`Transcript` -- strict record/replay of line exchanges
  (:mod:`mhs.bridge.transcript`).
* :class:`Loopback` -- the in-process JSON-RPC transport of the conformance
  harness (:mod:`mhs.conformance.inprocess`); :func:`client_for` builds an
  ``MHSClient`` over it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..bridge.transcript import Transcript, TranscriptDivergence
from ..conformance.inprocess import Loopback, client_for
from .recorder import PHASES, Call, RecordLog, Recorder, log_of

__all__ = [
    "Call",
    "Loopback",
    "PHASES",
    "RecordLog",
    "Recorder",
    "Transcript",
    "TranscriptDivergence",
    "check_driver",
    "client_for",
    "log_of",
]


def check_driver(directory: str | os.PathLike[str], backend: str = "fake", **options: Any) -> dict[str, Any]:
    """Run the acceptance gate on ``directory`` and return the check report (nothing is written).

    ``options`` are those of :func:`mhs.driver.check.run_check` (``root``,
    ``clone``, ``gates``, ``companions_root``).  ``report["failed"]`` lists the failing gate ids.
    """
    from ..driver.check import INNER_ENV, run_check

    options.setdefault("write_report", False)
    if os.environ.get(INNER_ENV):
        options["inner"] = True
    return run_check(Path(directory), backend=backend, **options)
