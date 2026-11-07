"""Hardware backend: opens the LPX 200 through the pyvisa resource the upstream clone uses.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R3: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).

The clone opens ``ASRL4::INSTR`` and sets CR as both terminators (LPX200.py:266-270).  The resource is an option so
the port of the installed instrument can be chosen; its default is the clone's resource.  ``evaluate`` is the
command sink the upstream ``Control`` holds: it stores the module-level ``commRes`` as ``self.evaluate`` and calls it
with the command text (LPX200.py:92, 98 and 283).  A line ending in ``?`` is a query whose reply is returned, any
other line is written without a reply, as ``commRes`` calls ``query`` for both (LPX200.py:251-258).  The gate never
imports this module and nothing here ran on hardware.
"""


class _Lpx200Link:
    """The pyvisa resource behind the driver's ``self.native.evaluate`` calls."""

    def __init__(self, instrument):
        self._instrument = instrument

    def evaluate(self, line):
        text = str(line).strip()
        if text.endswith("?"):
            return str(self._instrument.query(text)).strip()
        self._instrument.write(text)
        return None

    def close(self):
        self._instrument.close()


def connect(resource="ASRL4::INSTR", **options):
    """Open ``resource`` with the CR terminators of the clone; ``timeout_ms`` overrides the VISA timeout."""
    import pyvisa

    manager = pyvisa.ResourceManager()
    instrument = manager.open_resource(resource)
    instrument.write_termination = "\r"
    instrument.read_termination = "\r"
    if "timeout_ms" in options:
        instrument.timeout = int(options["timeout_ms"])
    return _Lpx200Link(instrument)
