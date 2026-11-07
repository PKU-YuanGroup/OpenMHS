"""OpenMHS driver for gh.mclim9/rssd: the Rohde & Schwarz FSWP phase noise analyzer over SCPI (a family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The commands are the raw commands of the upstream
phase noise analyzer class ``rssd/PNA/Common.py:PNA`` (its constructor sets ``Model = "FSWP"``); the upstream opens
the instrument through ``rssd.yaVISA`` (pyvisa), which this driver does not use: the bridge opens the instrument
itself (``host``/``port`` or a VISA resource, options of the hardware backend), so only the commands are shared.

* reads: the mechanical input attenuation, the channel list, the center frequency, the number of sweep points, the
  sweep time, the sweep type and the reference level;
* writes: attenuation, center frequency and number of sweep points.  No text file of the clone states a range for
  any of them, so all three are ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET``
  until the site supplies the bounds of its instrument (``site-limits.example.json`` shows that overlay);
* the e-stop writes ``INIT:CONT OFF`` (single sweep, so the continuous acquisition stops) and ``:INP:ATT:AUTO ON``
  (the input attenuation returns to automatic, which protects the receiver front end from an overload).

Every Limit and Fact cites a line of the clone at the pinned commit (7b040ee12841e721953a1f737297586135c0c110).  This
package is model-authored and unreviewed, and its command lines were not tried on an instrument (RESULT.json notes).
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

PNA = "rssd/PNA/Common.py"
VISA = "rssd/yaVISA.py"
VNA = "rssd/VNA/Common.py"


class Fswp(ScpiDriver):
    device_id = "fswp"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "rssd.PNA.Common:PNA"
    backends = {"fake": ".fake:FakeRssd"}
    vendor, model = "Rohde & Schwarz", "FSWP phase noise analyzer"
    display_name = "Rohde & Schwarz FSWP phase noise analyzer (rssd PNA class)"
    tags = ["phase noise analyzer", "signal analyzer", "fswp", "scpi", "rohde-schwarz"]
    facts = [
        Fact("The PNA class is the phase noise analyzer object of the repository; its constructor sets Model to "
             "'FSWP'", source="upstream_code", ref=f"{PNA}:1-8"),
        Fact("INP:ATT? reads the mechanical input attenuation", source="upstream_code", ref=f"{PNA}:13-15"),
        Fact("INP:ATT <dB> sets the mechanical input attenuation, formatted without decimals", source="upstream_code",
             ref=f"{PNA}:133-135"),
        Fact("INST:LIST? returns the measurement channels as one comma-separated reply", source="upstream_code",
             ref=f"{PNA}:17-19"),
        Fact("A channel name in the INST:LIST? reply is quoted, so Set_Channel compares each entry with a quoted "
             "name", source="upstream_code", ref=f"{PNA}:151-157"),
        Fact("The channel names the clone knows are SAN, IQ, NR5G, LTE, WLAN, PNOISE, NOISE, SPUR, ADEM, DDEM, "
             "V5GT and AMPL", source="upstream_code", ref=f"{PNA}:148"),
        Fact(":SENS:FREQ:CENT? reads the center frequency of the measurement", source="upstream_code",
             ref=f"{PNA}:22"),
        Fact("The center frequency is written as ':SENS:FREQ:CENT <value> HZ'", source="upstream_code",
             ref=f"{PNA}:163"),
        Fact(":SENS:SWE:POIN? reads the number of trace points of a sweep", source="upstream_code", ref=f"{PNA}:91"),
        Fact("The number of sweep points is written as ':SENS:SWE:POIN <value>' with six decimals",
             source="upstream_code", ref=f"{PNA}:240"),
        Fact("SENS:SWE:TIME? reads the sweep or capture time", source="upstream_code", ref=f"{PNA}:95"),
        Fact("The sweep time is written in seconds and 0 selects the automatic sweep time", source="upstream_code",
             ref=f"{VNA}:177-179"),
        Fact(":SENS:SWE:TYPE? reads the sweep type, one of AUTO, SWE and FFT", source="upstream_code",
             ref=f"{PNA}:99-101"),
        Fact("DISP:TRAC:Y:RLEV? reads the reference level of the trace", source="upstream_code", ref=f"{PNA}:78"),
        Fact("The reference level is written as 'DISP:WIND:TRAC:Y:SCAL:RLEV <value> dBm'", source="upstream_code",
             ref=f"{PNA}:210"),
        Fact("INIT:CONT OFF selects a single sweep and INIT:CONT ON a continuous sweep", source="upstream_code",
             ref=f"{PNA}:232-237"),
        Fact(":INP:ATT:AUTO ON returns the input attenuation to automatic", source="upstream_code",
             ref=f"{PNA}:137-138"),
        Fact("The upstream wrapper queries *IDN? and splits the reply on ', ' into make, model, device and version",
             source="upstream_code", ref=f"{VISA}:75-85"),
    ]
    safe_state = ("continuous acquisition stopped (INIT:CONT OFF) and input attenuation returned to automatic "
                  "(:INP:ATT:AUTO ON)")

    parameters = {
        "attenuation_db": Field(
            "integer", unit="1", writable=True,
            description="Mechanical attenuation of the RF input, in dB (INP:ATT)",
            limit=Limit.operator_required(
                "no text file of the clone states the attenuation range of the instrument; the site states the "
                "attenuation range of the front end it attaches")),
        "channels": Field("string", description="Measurement channels the instrument lists (INST:LIST? reply, a "
                                                "comma-separated list of quoted channel names)"),
        "center_freq_hz": Field(
            "number", unit="Hz", writable=True,
            description="Center frequency of the measurement (:SENS:FREQ:CENT)",
            limit=Limit.operator_required(
                "no text file of the clone states the frequency range of the instrument; the site states the "
                "frequency range of its own instrument")),
        "sweep_points": Field(
            "integer", unit="1", writable=True,
            description="Number of sweep points (trace points) per sweep (:SENS:SWE:POIN)",
            limit=Limit.operator_required(
                "no text file of the clone states how many sweep points the instrument accepts; the site states "
                "the number of points its measurements use")),
        "sweep_time_s": Field("number", unit="s", description="Sweep or capture time of the measurement "
                                                              "(SENS:SWE:TIME?)"),
        "sweep_type": Field("string", description="Sweep type of the measurement: AUTO, SWE or FFT "
                                                  "(:SENS:SWE:TYPE?)"),
        "reference_level_db": Field("number", description="Reference level of the trace in dBm "
                                                          "(DISP:TRAC:Y:RLEV?)"),
    }
    reads = {
        "attenuation_db": {"query": "INP:ATT?", "parse": {"kind": "int"}},
        "channels": {"query": "INST:LIST?", "parse": {"kind": "str"}},
        "center_freq_hz": {"query": ":SENS:FREQ:CENT?", "parse": {"kind": "float"}},
        "sweep_points": {"query": ":SENS:SWE:POIN?", "parse": {"kind": "int"}},
        "sweep_time_s": {"query": "SENS:SWE:TIME?", "parse": {"kind": "float"}},
        "sweep_type": {"query": ":SENS:SWE:TYPE?", "parse": {"kind": "str"}},
        "reference_level_db": {"query": "DISP:TRAC:Y:RLEV?", "parse": {"kind": "float"}},
    }
    writes = {
        "attenuation_db": {"write": "INP:ATT {value:d}", "type": "integer"},
        "center_freq_hz": {"write": ":SENS:FREQ:CENT {value:.0f} HZ", "type": "number"},
        "sweep_points": {"write": ":SENS:SWE:POIN {value:.6f}", "type": "integer"},
    }
    safety_bindings = {"estop": {"write": ["INIT:CONT OFF", ":INP:ATT:AUTO ON"]}}
