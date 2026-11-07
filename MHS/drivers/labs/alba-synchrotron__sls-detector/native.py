"""Hardware backend: constructs the upstream ``sls.client:Detector`` for one SLS detector.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed; it is R1, so the loader does not apply the R2/R3 reviewed-by refusal, but no hardware
run is claimed by this package and the acceptance gate never imports this module or the upstream package.

Options of the backend: ``host`` (required) is the detector host name or IP address the upstream constructor takes;
``ctrl_port`` and ``stop_port`` are optional and are passed to the upstream constructor unchanged, so the
constructor's own values apply when they are omitted (``sls/client.py:144-151`` and ``sls/protocol.py:14-15``).  The
upstream client is imported here at hardware time only.
"""


def connect(host, ctrl_port=None, stop_port=None):
    from sls.client import Detector

    options = {}
    if ctrl_port is not None:
        options["ctrl_port"] = int(ctrl_port)
    if stop_port is not None:
        options["stop_port"] = int(stop_port)
    return Detector(host, **options)
