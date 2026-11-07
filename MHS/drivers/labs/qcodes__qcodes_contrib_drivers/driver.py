"""OpenMHS driver for gh.qcodes/qcodes_contrib_drivers: the Thorlabs PM100D optical power meter.

The QcodesDriver exemplar.  A config-only ``QcodesDriver`` over the QCoDeS VisaInstrument
``qcodes_contrib_drivers.drivers.Thorlabs.PM100D:Thorlab_PM100D`` (src/qcodes_contrib_drivers/drivers/Thorlabs/
PM100D.py:20), the driver pack's class for the PM100D handheld optical power and energy meter console.

* Every field is one explicit ``parameter_bindings`` entry naming a Parameter that ``__init__`` constructs as
  ``self.<name> = Parameter(..., instrument=self)`` with an explicit ``get_cmd`` (and ``set_cmd`` for a write).  Gate
  G7 proves each assignment, cited at its exact lines (``source_ref``), in the pinned source; nothing is discovered at
  run time and nothing reads a Parameter cache.
* Reads call ``Parameter.get()``.  ``power`` is a measurement: ``_get_power()`` re-applies the power configuration
  (CONF:POW, ABOR, INIT), writes MEAS:POW, waits 0.2 s and returns ``float(FETC?)`` (PM100D.py:164-179).  Every power
  read therefore aborts a measurement in progress and puts the meter back into power mode: it is not a
  side-effect-free observation.
* Writes (``cap.device.configure.v1``) call ``Parameter.set(value)`` and wait for the whole setter: ``power_range``
  (no source states its bounds, so ``Limit.operator_required``) and ``auto_range`` (on/off).  The upstream writes
  without reading the SCPI error queue, so a setting the meter or its sensor head rejects is visible only as the
  unchanged value of the fresh read that follows every command.
* The native stop is ``write("ABOR")``: the SCPI abort that ``_set_conf_power()`` sends (as the first command of
  ``ABOR;:STAT:OPER?``) before it re-initializes a measurement (PM100D.py:168).  It is sent without a query so that no
  reply can be mistaken for the reply of a power read that may be running on the same VISA session.  The stop is not
  synchronised with such a read: when ABOR lands between the read's own ABOR and INIT, the read re-arms a measurement
  (INIT, MEAS:POW) after the stop (PM100D.py:167-176).  The meter is a passive detector: this package drives no output,
  light source or motion, and the latch refuses every later command.

NOT COVERED, each for a reason in the source:

* ``wavelength`` and ``beam_diameter``: both declare ``scale`` but no ``get_parser`` (PM100D.py:50-59, 142-151), so the
  QCoDeS get divides the raw reply string by the scale; their reads, and therefore their writes' readback, are not
  served.
* ``averaging`` writes: ``set_cmd='AVER'`` has no value placeholder (PM100D.py:45), so a set would not transmit the
  value.  Its read (the raw ``AVER?`` reply, no parser) is served as a string.
* ``attenuation`` writes: its unit is dB (PM100D.py:73), which is not an OpenMHS unit; the read is served without a
  unit and the description names dB.
* ``current`` and ``frequency``: their ``MEAS:CURR?`` / ``MEAS:FREQ?`` queries (PM100D.py:104-121) are SCPI measure
  queries that would switch the meter out of the power mode every served field assumes, until the next power read
  re-applies it (PM100D.py:164-179).

Every Fact and every ``source_ref`` cites the clone at the pinned commit 187164d608ed3a281fccdf3f68693d29b2d46a62.  The
package is model-authored and unreviewed (``reviewed_by`` is null); it is checked on the fake backend only and has
never opened a VISA session.
"""

from mhs.driver import Fact, Field, Limit, QcodesDriver

#: The module of the selected upstream class, relative to the clone root.
SOURCE = "src/qcodes_contrib_drivers/drivers/Thorlabs/PM100D.py"

POWER_RANGE_LIMIT = Limit.operator_required(
    "no source states the PM100D power ranges; they depend on the connected sensor head")


def _binding(parameter: str, lines: str, *, settable: bool = False, timeout_ms: int = 5000) -> dict:
    """One explicit Parameter binding: the ``self.<parameter> = Parameter(...)`` assignment at ``SOURCE:lines``."""
    return {"parameter": parameter, "get": True, "set": settable, "timeout_ms": timeout_ms,
            "source_ref": f"{SOURCE}:{lines}"}


class ThorlabsPM100D(QcodesDriver):
    device_id = "thorlabs-pm100d"
    device_kind = "sensor.optical"
    mode = "hardware"
    risk = "R1"
    native = "qcodes_contrib_drivers.drivers.Thorlabs.PM100D:Thorlab_PM100D"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeThorlabPM100D"}
    vendor, model = "Thorlabs", "PM100D"
    display_name = "Thorlabs PM100D optical power meter (QCoDeS contrib driver)"
    tags = ["qcodes", "visa", "scpi", "optical-power-meter", "photodiode"]
    safe_state = ("measurement aborted by the SCPI abort command (ABOR); a power read already running on the same "
                  "VISA session is not cancelled and may re-arm a measurement (INIT) after it; the power meter is a "
                  "passive detector and this package drives no output")
    native_close = "close"

    parameters = {
        "power": Field("number", unit="W", description="Measured optical power; every read re-applies power mode "
                                                       "(CONF:POW, ABOR, INIT), aborting a running measurement, then "
                                                       "MEAS:POW and FETC?"),
        "power_range": Field("number", unit="W", writable=True, limit=POWER_RANGE_LIMIT,
                             description="Upper end of the power range (SENS:POW:RANG:UPP); setting it selects the "
                                         "range of the meter"),
        "auto_range": Field("boolean", writable=True,
                            description="Power auto range on (true) or off (false), SENS:POW:RANG:AUTO"),
        "attenuation": Field("number", description="Attenuation correction in dB (CORR?); dB is the upstream unit "
                                                   "and not an OpenMHS unit, so the field carries none"),
        "averaging": Field("string", description="Raw reply of AVER?, the averaging setting (the upstream declares "
                                                 "no parser)"),
        "zero_value": Field("number", unit="W", description="Dark zero value (CORR:COLL:ZERO:MAGN?)"),
        "current_range": Field("number", unit="A", description="Upper end of the current range (SENS:CURR:RANG:UPP?)"),
    }
    parameter_bindings = {
        "power": _binding("power", "61-68", timeout_ms=10000),
        "power_range": _binding("power_range", "82-92", settable=True),
        "auto_range": _binding("auto_range", "94-102", settable=True),
        "attenuation": _binding("attenuation", "70-80"),
        "averaging": _binding("averaging", "41-48"),
        "zero_value": _binding("zero_value", "133-140"),
        "current_range": _binding("current_range", "123-131"),
    }
    safety_bindings = {"estop": {"native": "write", "invoke": "write", "command": "ABOR", "timeout_ms": 1000}}
    facts = [
        Fact("Thorlab_PM100D is a QCoDeS VisaInstrument that represents a Thorlab PM100D optical powermeter, status "
             "beta-version", source="upstream_code", ref=f"{SOURCE}:20-24"),
        Fact("The constructor takes a VISA resource address, terminator default '\\n' and timeout default 20",
             source="upstream_code", ref=f"{SOURCE}:32-39"),
        Fact("The module imports Parameter from qcodes.parameters and VisaInstrument from qcodes.instrument",
             source="upstream_code", ref=f"{SOURCE}:13-14"),
        Fact("power is a Parameter with unit W whose get_cmd is self._get_power", source="upstream_code",
             ref=f"{SOURCE}:61-68"),
        Fact("_get_power() calls _set_conf_power(), writes MEAS:POW, sleeps .2 and returns float of the FETC? reply",
             source="upstream_code", ref=f"{SOURCE}:172-179"),
        Fact("_set_conf_power() writes CONF:POW, asks ABOR;:STAT:OPER? and writes INIT", source="upstream_code",
             ref=f"{SOURCE}:164-170"),
        Fact("power_range has unit W, get_cmd SENS:POW:RANG:UPP?, set_cmd SENS:POW:RANG:UPP {}, float parsers and "
             "the unbounded validator Numbers()", source="upstream_code", ref=f"{SOURCE}:82-92"),
        Fact("auto_range has get_cmd SENS:POW:RANG:AUTO?, set_cmd SENS:POW:RANG:AUTO {} and an on/off mapping to '1' "
             "and '0'", source="upstream_code", ref=f"{SOURCE}:94-102"),
        Fact("attenuation has unit dB, get_cmd CORR?, set_cmd CORR {} and validator Numbers(-60, 60)",
             source="upstream_code", ref=f"{SOURCE}:70-80"),
        Fact("averaging has get_cmd AVER? and set_cmd AVER, which has no value placeholder", source="upstream_code",
             ref=f"{SOURCE}:41-48"),
        Fact("zero_value has unit W and get_cmd CORR:COLL:ZERO:MAGN?", source="upstream_code",
             ref=f"{SOURCE}:133-140"),
        Fact("current_range has unit A and get_cmd SENS:CURR:RANG:UPP?", source="upstream_code",
             ref=f"{SOURCE}:123-131"),
        Fact("wavelength has unit m, get_cmd SENS:CORR:WAV?, scale=1e9, validator Numbers(185e-9, 25e-6) and no "
             "get_parser", source="upstream_code", ref=f"{SOURCE}:50-59"),
        Fact("beam_diameter has unit m, get_cmd CORR:BEAM?, scale=1e3 and no get_parser", source="upstream_code",
             ref=f"{SOURCE}:142-151"),
        Fact("frequency and current get MEAS:FREQ? and MEAS:CURR?", source="upstream_code", ref=f"{SOURCE}:104-121"),
        Fact("The constructor applies the transition filter (512, 0), calls averaging(300), applies the power "
             "configuration and calls connect_message()", source="upstream_code", ref=f"{SOURCE}:153-157"),
        Fact("_set_transition_filter() writes STAT:OPER:PTR and STAT:OPER:NTR and sleeps .2, 5 and .2",
             source="upstream_code", ref=f"{SOURCE}:181-189"),
        Fact("_check_error() asks SYST:ERR? and raises RuntimeError unless the reply starts with +0",
             source="upstream_code", ref=f"{SOURCE}:159-162"),
    ]
