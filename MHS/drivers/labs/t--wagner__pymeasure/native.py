"""Hardware backend factory of the Keithley 2000 package: open the upstream class at a VISA address.

The gate never imports or runs this module.  On real hardware the upstream package must be installed; the
upstream class opens the instrument itself through PyVISA (``instruments/keithley2000_multimeter.py:639-642``).
The address is supplied as the ``address`` (or ``resource``/``visa_resource``) option of the hardware backend;
the remaining options are passed to the upstream constructor.  Nothing here was run on an instrument.
"""

from pymeasure.instruments.keithley2000_multimeter import Keithley2000Multimeter


def connect(**options):
    """Open the upstream multimeter at a VISA address from the backend options."""
    address = options.pop("address", None) or options.pop("resource", None) or options.pop("visa_resource", None)
    if not address:
        raise ValueError("the hardware backend needs a VISA address (the 'address' option)")
    return Keithley2000Multimeter(address, **options)
