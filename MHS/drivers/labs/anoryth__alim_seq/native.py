"""Hardware backend: opens the upstream ``alim_seq.psu:HMP4040`` SCPI driver over a VISA resource.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision); the acceptance gate
runs the fake backend and never imports this module or the upstream package.  This package is model-authored
and unreviewed and it declares R2: the loader refuses its hardware backend until a human signs ``reviewed_by``
in driver.lock.json (the loader does this at R2 and R3 only).

The clone has no setup.py or pyproject.toml (only requirements.txt), so ``alim_seq`` is importable when the
clone root is on ``PYTHONPATH`` (for example ``PYTHONPATH=/path/to/labs/anoryth/alim_seq``) or the endpoint
runs from that root.  That is a deployment assumption, not an upstream Fact.

Options of the backend: ``resource`` (required) is the pyvisa resource string the upstream passes to
``pyvisa.ResourceManager.open_resource`` (for example a ``TCPIP0::...::5025::SOCKET`` raw socket or an
``...::INSTR`` VXI-11/USB-TMC resource; alim_seq/psu.py:199-219).  ``timeout_ms``, ``use_opc``,
``visa_backend``, ``use_cc_status``, ``query_delay_s`` and ``log`` are the remaining keyword arguments of
``HMP4040.__init__`` (alim_seq/psu.py:162-164); ``connect()`` is called here because it opens the session,
probes ``*IDN?`` and switches every channel output off before enabling the general output
(alim_seq/psu.py:190-255).
"""


def connect(resource, timeout_ms=5000, use_opc=True, visa_backend="", use_cc_status=False,
            query_delay_s=0.0, log=None):
    from alim_seq.psu import HMP4040

    device = HMP4040(resource=resource, timeout_ms=timeout_ms, use_opc=use_opc,
                     visa_backend=visa_backend, use_cc_status=use_cc_status,
                     query_delay_s=query_delay_s, log=log)
    device.connect()
    return device
