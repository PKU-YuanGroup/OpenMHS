"""Hardware backend: open a Rigol MSO5000-series oscilloscope through the upstream Scope class.

Used only with ``backend="hardware"`` and ``allow_hardware=True``, which is an operator decision.  This package is
model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null) and nothing in it ever ran against an
instrument.  The loader refuses the hardware backend of an unreviewed model-written package at R2 and R3 only; this
package is R1, so that loader guard does not apply to it and must not be claimed here.

Options of the backend:

* ``resource_name`` (required): a VISA resource name the upstream connection accepts, for example
  ``TCPIP::192.168.178.102::INSTR`` (scope.py:196-224 and README.md:9-11);
* ``timeout_ms`` (default 10000): the per-exchange timeout the upstream session stores
  (session.py:135-159) and applies when it opens the resource (mso5000_scpi.py:362-363).

The upstream package is imported only inside this function; the acceptance gate never imports this module.
"""


def connect(resource_name, *, timeout_ms=10000):
    from pymso5000 import Scope

    return Scope.connect(resource_name, timeout_ms=timeout_ms)
