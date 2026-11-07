"""OpenMHS driver for gh.samdejong86/tektronix-serial-daq-python: a Tektronix TDS 3052 over SCPI.

The upstream clone is a DAQ script, not a library: it has no device class and keeps the open VISA resource in the
module-level name ``tds`` (``tekdaq.py:70``), which is the task card's entry symbol.  It sends SCPI text lines over
the resource (``tekdaq.py:87-90``, ``111``, ``130-138``) and reads settings back with ``CH1:SCALE?`` and
``CH2:SCALE?`` (``tekdaq.py:153-156``).  A ScpiDriver is configuration only: the class attributes below are the
command map of the SCPI bridge, and the runtime enforces every limit before a command reaches the wire.  The bridge
opens the transport itself (``host``/``port`` or a ``visa_resource``), so the upstream script is not imported.

* reads: the channel 1 and channel 2 vertical scales, the two settings the clone reads back;
* writes: the vertical scale, coupling and impedance of both channels, the trigger level, edge source and slope,
  the horizontal scale and trigger position, and the record length.  The clone states the allowed tokens for the
  enumerated settings (``tekdaq.py:41``, ``46``, ``49-52``, ``132-135``) and states no range for the numeric ones,
  so those are ``Limit.operator_required`` and every write is refused until an operator supplies the bound in
  ``site-limits.json``;
* the e-stop writes ``ACQ:STOPA SEQ`` and ``LOC NONE``: the clone sets the acquisition stop condition to sequence
  and releases its front-panel lock when it finishes (``tekdaq.py:221-222``, ``321``).

The waveform array itself (the ``WFMPRE?`` preamble and the binary ``CURVE?`` block, ``tekdaq.py:205`` and
``402``) is not carried: the SCPI bridge moves text lines, and the array is not exposed here.  This package is
model-authored and unreviewed; no hardware backend was run.  Every Limit and Fact cites a line of the clone at
commit e7728bc44030b530d76ea3dbd66904237c12e180.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

TEKDAQ = "tekdaq.py"


class Tds3052(ScpiDriver):
    device_id = "tds3052"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    #: The clone has no class; this is the module-level VISA resource the card names as its entry symbol.
    native = "tekdaq:tds"
    backends = {"fake": ".fake:FakeTds3052"}
    vendor, model = "Tektronix", "TDS 3052"
    display_name = "Tektronix TDS 3052 oscilloscope"
    tags = ["oscilloscope", "tds 3052", "tektronix", "serial", "scpi"]
    facts = [
        Fact("The clone is DAQ software for a Tektronix TDS 3052 oscilloscope over an RS-232 connection",
             source="vendor_doc", ref="README.md:5"),
        Fact("The clone opens the scope into the module-level VISA resource tds", source="upstream_code",
             ref=f"{TEKDAQ}:70"),
        Fact("The script asks the instrument for its identity with *IDN? and reads the reply", source="upstream_code",
             ref=f"{TEKDAQ}:85-90"),
        Fact("A setting is sent as a command word, a space and its value, for example 'CH1:SCA ' + value",
             source="upstream_code", ref=f"{TEKDAQ}:111"),
        Fact("The channel vertical scales are read back with CH1:SCALE? and CH2:SCALE?", source="upstream_code",
             ref=f"{TEKDAQ}:153-156"),
        Fact("The record length is restricted to the tokens 5.E2 and 1.E4", source="upstream_code",
             ref=f"{TEKDAQ}:41"),
        Fact("The coupling choices are AC and DC, and the input impedance choices are FIF and MEG",
             source="upstream_code", ref=f"{TEKDAQ}:49-52"),
        Fact("The trigger source is written as EXT or CH<n>", source="upstream_code", ref=f"{TEKDAQ}:132-135"),
        Fact("The trigger slope choices are RISE and FALL", source="upstream_code", ref=f"{TEKDAQ}:46"),
        Fact("The clone locks the front panel with LOC All and sets the acquisition stop condition to SEQ",
             source="upstream_code", ref=f"{TEKDAQ}:221-222"),
        Fact("The clone releases the front-panel lock with LOC NONE when it finishes", source="upstream_code",
             ref=f"{TEKDAQ}:321"),
        Fact("The module's only top-level definitions are the plotting callbacks init, finished, writeEvent and "
             "animate", source="upstream_code", ref=f"{TEKDAQ}:307-375"),
    ]
    safe_state = "acquisition set to stop after the current sequence and the front-panel remote lock released"
    idn = True

    parameters = {
        "ch1_scale": Field(
            "number", unit="V", writable=True, description="Channel 1 scale (V)",
            limit=Limit.operator_required(
                "The clone passes --vsca1 through to CH1:SCA but states no vertical-scale range; the operator "
                "supplies the bound of this scope.")),
        "ch2_scale": Field(
            "number", unit="V", writable=True, description="Channel 2 scale (V)",
            limit=Limit.operator_required(
                "The clone passes --vsca2 through to CH2:SCA but states no vertical-scale range; the operator "
                "supplies the bound of this scope.")),
        "coupling_ch1": Field(
            "string", writable=True, description="Channel 1 coupling",
            limit=Limit(allowed=["AC", "DC"], source="upstream_code", ref=f"{TEKDAQ}:49")),
        "coupling_ch2": Field(
            "string", writable=True, description="Channel 2 coupling",
            limit=Limit(allowed=["AC", "DC"], source="upstream_code", ref=f"{TEKDAQ}:50")),
        "horizontal_scale": Field(
            "number", unit="s", writable=True, description="Horizontal scale (s)",
            limit=Limit.operator_required(
                "The clone passes --hsamp through to HOR:SCA but states no time-per-division range; the operator "
                "supplies the bound of this scope.")),
        "impedance_ch1": Field(
            "string", writable=True, description="Channel 1 impedance",
            limit=Limit(allowed=["FIF", "MEG"], source="upstream_code", ref=f"{TEKDAQ}:51")),
        "impedance_ch2": Field(
            "string", writable=True, description="Channel 2 impedance",
            limit=Limit(allowed=["FIF", "MEG"], source="upstream_code", ref=f"{TEKDAQ}:52")),
        "record_length": Field(
            "string", writable=True, description="Record length token",
            limit=Limit(allowed=["5.E2", "1.E4"], source="upstream_code", ref=f"{TEKDAQ}:41")),
        "trigger_level": Field(
            "number", unit="V", writable=True, description="Trigger level (V)",
            limit=Limit.operator_required(
                "The clone passes --trlevel through to TRIGGER:A:LEVEL but states no level range; the operator "
                "supplies the bound of this scope.")),
        "trigger_position": Field(
            "number", unit="%", writable=True, description="Trigger position (%)",
            limit=Limit.operator_required(
                "The clone passes --pretrigger through to HOR:TRIG:POS but states no percentage range; the operator "
                "supplies the bound of this scope.")),
        "trigger_source": Field(
            "string", writable=True, description="Trigger edge source",
            limit=Limit(allowed=["CH1", "CH2", "EXT"], source="upstream_code", ref=f"{TEKDAQ}:132-135")),
        "trigger_slope": Field(
            "string", writable=True, description="Trigger edge slope",
            limit=Limit(allowed=["RISE", "FALL"], source="upstream_code", ref=f"{TEKDAQ}:46")),
    }
    reads = {
        "ch1_scale": {"query": "CH1:SCALE?", "parse": {"kind": "float"}},
        "ch2_scale": {"query": "CH2:SCALE?", "parse": {"kind": "float"}},
    }
    writes = {
        "ch1_scale": {"write": "CH1:SCA {value:.10g}", "type": "number"},
        "ch2_scale": {"write": "CH2:SCA {value:.10g}", "type": "number"},
        "coupling_ch1": {"write": "CH1:COUPL {value}", "type": "string"},
        "coupling_ch2": {"write": "CH2:COUPL {value}", "type": "string"},
        "horizontal_scale": {"write": "HOR:SCA {value:.10g}", "type": "number"},
        "impedance_ch1": {"write": "CH1:IMPED {value}", "type": "string"},
        "impedance_ch2": {"write": "CH2:IMPED {value}", "type": "string"},
        "record_length": {"write": "HOR:RECORDLENGTH {value}", "type": "string"},
        "trigger_level": {"write": "TRIGGER:A:LEVEL {value:.10g}", "type": "number"},
        "trigger_position": {"write": "HOR:TRIG:POS {value:.10g}", "type": "number"},
        "trigger_source": {"write": "TRIG:A:EDGE:SOU {value}", "type": "string"},
        "trigger_slope": {"write": "TRIG:A:EDGE:SLO {value}", "type": "string"},
    }
    safety_bindings = {
        "estop": {"write": ["ACQ:STOPA SEQ", "LOC NONE"],
                  "description": "stop after the current sequence and release the front-panel lock"},
    }
