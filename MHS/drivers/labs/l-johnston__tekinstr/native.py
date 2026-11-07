"""Hardware backend: open a Tektronix MDO3000-series oscilloscope through the upstream ``tekinstr`` package.

Used only with ``backend="hardware"`` and ``allow_hardware=True``, which is an operator decision.  This package is
model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null) and nothing in it ever ran against an
instrument.  The loader refuses the hardware backend of an unreviewed model-written package at R2 and R3 only; this
package is R1, so that guard does not apply to it and must not be claimed here.

Options of the backend:

* ``address`` (required): the host name or IP address ``CommChannel`` accepts; it opens
  ``TCPIP::<address>`` (tekinstr/__init__.py:43-47).

``CommChannel.get_instrument`` identifies the instrument by ``*IDN?`` and returns the model class
(tekinstr/__init__.py:49-58); this factory serves the oscilloscope subsystem of an MDO3000 model and refuses any
other model, because the driver's reads and writes are the MDO3000 Oscilloscope interface.  The upstream Oscilloscope
has no ``close`` method, so the open CommChannel is kept and closed at interpreter exit; a long-running endpoint
therefore holds the VISA session open.  The upstream package is imported only inside this function; the acceptance
gate never imports this module.
"""

import atexit

#: CommChannels this process opened, closed at interpreter exit.
_CHANNELS = []


def connect(address, **_options):
    """Return the oscilloscope subsystem of the MDO3000 at ``address``."""
    from tekinstr import CommChannel

    channel = CommChannel(address)
    try:
        instrument = channel.get_instrument()
        if not str(instrument.model).startswith("MDO3"):
            raise ValueError(f"the oscilloscope at {address} reports model {instrument.model!r}, not an MDO3000 model")
    except BaseException:
        channel.close()
        raise
    _CHANNELS.append(channel)
    atexit.register(channel.close)
    return instrument.oscilloscope
