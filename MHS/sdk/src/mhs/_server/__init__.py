"""Internal helpers of :mod:`mhs.server` (not a public API).

The endpoint runtime stays in ``mhs/server.py``; modules here hold pieces that
are easier to read and test on their own (WP-04: the full split of the server
is post-pilot).

* :mod:`mhs._server.strict` -- the strict-mode resolver: catalogue checks of a
  device at construction, the compatibility-mode warnings, and the principal
  helpers used by the session and reset rules.
* :mod:`mhs._server.limits_plan` -- the per-binding limit plans: which sources
  :mod:`mhs.limits` intersects (class, binding, envelope, operator overlay),
  the two-pass validation schemas, ``LIMITS_UNSET`` candidates, cumulative
  budgets and the ``site-limits.json`` loader.
* :mod:`mhs._server.state` -- ``MHSServer(state_dir=...)``: the directory
  lock, the atomically written e-stop latch file, and the journal that holds
  the idempotency index, the write-ahead records of commands in flight and
  the cumulative budget draws (rebuilt against the evidence chain on start).
"""
