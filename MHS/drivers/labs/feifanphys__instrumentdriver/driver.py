"""OpenMHS driver for gh.feifanphys/instrumentdriver: a Keysight N5182B signal generator over SCPI.

The upstream package wraps the N5182B in a small Python class whose methods write SCPI lines through a transport
(``drivers/SignalGenerator/KeysightN5182B.py``).  A ScpiDriver expresses that same text protocol as a command map;
the bridge opens the instrument itself (``host``/``port`` or a VISA resource), so only the commands are shared.

* reads: RF frequency (``FREQ?``), RF power (``POW?``) and output state (``OUTP?``);
* writes: frequency (``FREQ {value}``), power (``POW {value}DBM``) and output state (``OUTP ON`` / ``OUTP OFF``);
* the e-stop writes ``OUTP OFF``: the RF output, the one output this driver sets, goes off.

The clone states no numeric frequency or power range, so both are ``Limit.operator_required``: the site supplies its
own envelope in ``site-limits.json``.  ``site-limits.example.json`` is an example operator overlay, not a device
bound.  This package is model-authored and unreviewed; no hardware was used, and its evidence is the fake
backend only.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

SOURCE = "drivers/SignalGenerator/KeysightN5182B.py"
TRANSPORT = "transport/ScpiTransport.py"


class KeysightN5182B(ScpiDriver):
    device_id = "n5182b"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "drivers.SignalGenerator.KeysightN5182B:KeysightN5182B"
    backends = {"fake": ".fake:FakeN5182B"}
    vendor, model = "Keysight Technologies", "N5182B"
    display_name = "Keysight N5182B signal generator"
    tags = ["signal generator", "rf source", "keysight", "n5182b", "scpi"]
    facts = [
        Fact("The KeysightN5182B.reset method writes '*RST'", source="upstream_code",
             ref=f"{SOURCE}:9-10"),
        Fact("The KeysightN5182B.set_frequency method writes 'FREQ {hz}'", source="upstream_code",
             ref=f"{SOURCE}:12-13"),
        Fact("The KeysightN5182B.set_power method writes 'POW {dbm}DBM'", source="upstream_code",
             ref=f"{SOURCE}:15-16"),
        Fact("The KeysightN5182B.output_on and output_off methods write 'OUTP ON' and 'OUTP OFF'",
             source="upstream_code", ref=f"{SOURCE}:18-22"),
        Fact("The upstream mock answers '*IDN?', 'FREQ?', 'POW?' and 'OUTP?'", source="upstream_code",
             ref=f"{SOURCE}:75-86"),
        Fact("The upstream mock identity starts 'Keysight Technologies,N5182B,'", source="upstream_code",
             ref=f"{SOURCE}:31"),
        Fact("The upstream mock accepts 'FREQ ', 'POW ' with an optional DBM suffix, and 'OUTP ON'/'OUTP OFF'",
             source="upstream_code", ref=f"{SOURCE}:53-70"),
        Fact("The upstream README example resets the generator, sets frequency and power, and turns the output on",
             source="vendor_doc", ref="README.md:131-134"),
        Fact("ScpiTransport writes a command plus its terminator and the default terminator is a newline",
             source="upstream_code", ref=f"{TRANSPORT}:6-18"),
    ]
    safe_state = "RF output disabled (OUTP OFF)"
    idn = {"expect": "^Keysight Technologies,N5182B"}

    parameters = {
        "frequency": Field(
            "number", unit="Hz", writable=True, description="RF output frequency (SCPI FREQ)",
            limit=Limit.operator_required(
                "the clone states no frequency range; the site supplies the range of the installed source")),
        "power": Field(
            "number", unit="1", writable=True,
            description="RF output power in dBm (SCPI POW {value}DBM; the UCUM code '1' is the dimensionless "
                        "coding of the dBm value)",
            limit=Limit.operator_required(
                "the clone states no power range; the site supplies the level the load may receive")),
        "output": Field("boolean", writable=True, description="RF output state (SCPI OUTP ON/OFF)"),
    }
    reads = {
        "frequency": {"query": "FREQ?", "parse": {"kind": "float"}},
        "power": {"query": "POW?", "parse": {"kind": "float"}},
        "output": {"query": "OUTP?", "parse": {"kind": "bool"}},
    }
    writes = {
        "frequency": {"write": "FREQ {value}", "type": "number"},
        "power": {"write": "POW {value}DBM", "type": "number"},
        "output": {"write": "OUTP {value}", "type": "string", "map": {True: "ON", False: "OFF"}},
    }
    commands = {
        "x-cap.feifanphys.reset.v1": {"write": "*RST", "check_errors": False},
    }
    actions = {
        "x-cap.feifanphys.reset.v1": Action(
            name="reset", description="Reset the signal generator (SCPI *RST)"),
    }
    safety_bindings = {"estop": {"write": "OUTP OFF"}}
