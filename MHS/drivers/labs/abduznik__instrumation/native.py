"""Hardware backend of the Rigol DS1054Z driver: opens the upstream pyvisa session.

The gate never imports this module (it serves the fake backend), and no hardware is attached in this package's
acceptance run.  The operator passes the VISA resource of the instrument, for example
``USB0::0x1AB1::0x04CE::DS1054Z::INSTR`` (docs/experiments/rigol_ds1054z.md:23) or a LAN resource
(``TCPIP::<host>::INSTR``, docs/experiments/rigol_ds1054z.md:30), as ``resource=`` or ``visa_resource=``.
The upstream class imports pyvisa in its own module (src/instrumation/drivers/real.py:1); this factory imports the
upstream package lazily so the fake path never touches it.
"""


def connect(resource=None, rm=None, **options):
    """Open the instrument and return the upstream ``RigolDS1054Z`` object."""
    visa_resource = resource or options.pop("visa_resource", None)
    if not visa_resource:
        raise ValueError("connect needs a VISA resource string (resource= or visa_resource=)")
    from instrumation.drivers.rigol import RigolDS1054Z

    instrument = RigolDS1054Z(visa_resource, rm=rm)
    instrument.connect()
    return instrument
