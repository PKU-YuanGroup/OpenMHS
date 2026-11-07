"""Hardware backend: opens a Cryo-con Model 34 through the upstream Cryocon34Backend.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the pica package.

``address`` is a PyVISA resource string, for example the manual's ``GPIB1::23::INSTR`` (docs/User_Manual.md:958).
The upstream ``connect`` opens one paced session, checks that the instrument identifies itself as a Cryo-con, and
probes the loop-prefix and heater read-back forms of this firmware before returning
(pica/cryocon/T_Control_CC34_DirectControl_GUI.py:643-672).  The driver's setup hook then refuses a controller whose
channel A or loop 1 source is not displaying Kelvin.  Nothing here selects a setpoint, engages a loop or changes a
heater setting.
"""


def connect(address, **options):
    """Open the VISA session and return the upstream backend object."""
    from pica.cryocon.T_Control_CC34_DirectControl_GUI import Cryocon34Backend

    device = Cryocon34Backend(**options)      # the upstream constructor takes log=...
    device.connect(address)
    return device
