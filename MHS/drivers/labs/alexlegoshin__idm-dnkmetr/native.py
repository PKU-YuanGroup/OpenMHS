"""Hardware backend for the GPP-4323 driver: open the upstream ``drivers:PowerSupply`` class.

Used only with backend="hardware" and allow_hardware=True, an operator decision; the acceptance gate runs the fake
backend and never imports this module's upstream dependency.  The options are those of the upstream constructor:
``profile_path`` (a copy of instruments/gwinstek_psu_generic.json) and ``resource_name`` (the VISA resource).
The upstream profile's command table has no readback entry for the setpoints, although its notes confirm that
``VSET1?`` and ``ISET1?`` work; the factory adds those two names to the loaded command map so the driver's
``query_number`` reads reach the instrument.  The upstream clone root must be importable as ``drivers``.
"""


def connect(profile_path, resource_name, **_options):
    from drivers import PowerSupply

    supply = PowerSupply(profile_path, resource_name)
    supply._commands["set_voltage_readback"] = "VSET1?"
    supply._commands["current_limit_readback"] = "ISET1?"
    return supply
