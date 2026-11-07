"""Hardware backend of the TwinCAT NC axis telemetry driver: the upstream ``NcAxis`` Device over ADS.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that
imports ``ophyd_ads``, and through it ophyd and pyads.  The package is model-authored and unreviewed.  The loader
refuses the hardware backend of an unsigned model-written package at R2 and R3; this package is R0, so that refusal
is not claimed here.  Nothing in this package has ever run the hardware backend, and no human reviewed it.

Deployment data, not an upstream fact: ``prefix`` is the ADS address up to the symbol prefix, in the form
``ads://<host>[:<port>][/@<poll_rate>]/<symbol-prefix>``, for example ``ads://10.0.0.1:851/@10/MAIN.``.  ``NcAxis``
appends each Component suffix to it (ophyd_ads/devices.py:8-18), so the prefix must end where the suffix starts (with
the dot in this example).  ``AdsSignal`` parses the address from the resulting read_pv and obtains the IP address,
AMS id, port, poll rate and symbol from it (ophyd_ads/signal.py:40-63); it requires the address to contain an IP
address and raises ``ValueError`` otherwise.  There is no unit, scale or bound in the clone to supply.

``NcAxis`` declares 22 ``Component(AdsSignal, ...)`` objects, including the five ``set_*`` setpoints and the six
telemetry channels this package does not read; ophyd constructs a Component when the Device is built or the attribute
is first used.  Each constructed ``AdsSignal`` registers a ``Symbol`` with the process-wide ``Plc`` connection cache
and opens the ADS connection if it is closed (ophyd_ads/signal.py:62-64, ophyd_ads/ads.py:340-348); the driver reads
the eleven bound channels with ``Symbol.read``.  This factory does not write, subscribe, start a notification or call
``Plc.stop``: there is no stop of the axis in the clone, and ``Plc.stop`` only ends the client's queue thread
(ophyd_ads/ads.py:298-300).  A missing PLC or symbol may surface while the Device is built (the ADS connection is
opened there) or on the first read; a read failure is reported by the calling read, never hidden here.
"""


def connect(*, name="axis", prefix):
    """Build the upstream ``NcAxis`` Device for the deployment's ADS address prefix.

    ``name`` names the ophyd Device; ``prefix`` is the ADS address prefix described in the module docstring.  The
    function does not call a read, a write, a subscription or a stop.  It was never run in this package.
    """
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    if not isinstance(prefix, str) or not prefix.startswith("ads://") or len(prefix) <= len("ads://") \
            or "/" not in prefix[len("ads://"):]:
        raise ValueError("prefix must be an ADS address 'ads://<host>[:<port>][/@<poll_rate>]/<symbol-prefix>'")

    from ophyd_ads.devices import NcAxis

    return NcAxis(prefix=prefix, name=name)
