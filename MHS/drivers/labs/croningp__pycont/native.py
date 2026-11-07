"""Hardware backend: opens one Tricontinent C3000 pump through the upstream pycont package.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2 (the pump dispenses liquid), so the loader refuses its hardware backend until a human signs
reviewed_by in driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the
pycont package.

The site must pass ``port``, ``address`` and ``total_volume`` (mL): the serial device, the pump's address character
and the syringe size are installation facts, not defaults of this factory.  The remaining options are the upstream
constructor's: ``name``, ``baudrate`` (9600), ``timeout`` (1 s), ``micro_step_mode`` (2), ``top_velocity`` (6000) and
``initialize_valve_position`` ('I').  The default baudrate is documented in the clone (README.md:26,
pycont/controller.py:75-78); the other defaults are the upstream constructor's and may be overridden per pump
(pycont/controller.py:363-388).
"""


def connect(port, address, total_volume, name="pump", baudrate=9600, timeout=1.0, micro_step_mode=2,
            top_velocity=6000, initialize_valve_position="I", **options):
    from pycont.controller import C3000Controller, PumpIO

    pump_io = PumpIO(port, baudrate=baudrate, timeout=timeout)
    return C3000Controller(pump_io, name=name, address=address, total_volume=total_volume,
                           micro_step_mode=micro_step_mode, top_velocity=top_velocity,
                           initialize_valve_position=initialize_valve_position, **options)
