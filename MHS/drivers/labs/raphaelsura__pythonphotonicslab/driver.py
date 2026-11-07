"""OpenMHS driver for gh.raphaelsura/pythonphotonicslab: the SRS DG645 digital delay generator.

The upstream repository is a lab-script collection with several instrument classes.  This package binds one of its
entry symbols, ``LowLevelModules.Instruments:DG645`` (Instruments.py:96), a text-SCPI instrument: the class sends
lines such as ``LPOL 1,0``, ``DLAY 2,0,1e-06`` and ``LAMP 1,1.5`` through a VISA resource.  A ScpiDriver is therefore
configuration only: the bridge opens the instrument itself (host/port or a VISA resource, options of the hardware
backend) and sends the templates below, so only the text lines are shared with the upstream class.

What this package covers:

* reads: the output 1 amplitude, offset and polarity; the channel 1 delay from T0; holdoff; trigger level and rate;
  burst count, delay, mode, period and configuration; timebase; trigger source; the ``LERR?`` error string;
* writes: the same settings, each with a fixed output 1 or channel 1 index because the OpenMHS state schema has one
  field per name.  Outputs 2-4, delay channels 2-9 and the indexed variants of the other methods are not covered;
* the e-stop writes ``LPOL b,1`` for the four BNC outputs the clone's notebook uses (b = 1..4), which puts them at
  positive polarity, the notebook's "default LOW" state for its laser channels.

The clone states no numeric bound for any DG645 setting.  Every numeric write is therefore
``Limit.operator_required``: the deployment operator supplies the bound in site-limits.json, and until then every write
is refused with ``MHS.SAFETY.LIMITS_UNSET``.  This is not a claim that the device lacks a range; it is a claim that this
clone does not state one.

This package is model-authored and unreviewed (driver.lock.json ``reviewed_by`` is null).  It is checked on the fake
backend only; nothing here ran on an instrument and no hardware run is claimed.  The fake's values are test data,
marked as placeholders in fake.py, not device facts.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

INSTRUMENTS = "LowLevelModules/Instruments.py"
NOTEBOOK = "ControlHardware/Obsolete/PLEScan-Copy1.ipynb"

#: Why every numeric setting is deferred to the operator overlay.  The clone writes the argument unchanged and states
#: no accepted range anywhere in the DG645 class (Instruments.py:109-188).
_NO_BOUND = "the clone's DG645 class writes this value unchanged and states no accepted range"


class Dg645(ScpiDriver):
    device_id = "dg645"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "LowLevelModules.Instruments:DG645"
    backends = {"fake": ".fake:FakeDg645"}
    vendor, model = "Stanford Research Systems", "DG645 digital delay generator"
    display_name = "SRS DG645 digital delay generator"
    tags = ["delay generator", "dg645", "srs", "scpi", "instrument"]
    facts = [
        Fact("DG645 is the digital delay generator class of the clone and opens a VISA resource",
             source="upstream_code", ref=f"{INSTRUMENTS}:96-101"),
        Fact("set_polarity writes 'LPOL <output>,<index>' and get_polarity queries 'LPOL? <output>'",
             source="upstream_code", ref=f"{INSTRUMENTS}:109-113"),
        Fact("set_delay writes 'DLAY <channel>,<reference>,<time>' and get_delay queries 'DLAY? <channel>'",
             source="upstream_code", ref=f"{INSTRUMENTS}:172-176"),
        Fact("set_amplitude writes 'LAMP <output>,<value>' and get_amplitude queries 'LAMP? <output>'",
             source="upstream_code", ref=f"{INSTRUMENTS}:178-182"),
        Fact("set_offset writes 'LOFF <output>,<value>' and get_offset queries 'LOFF? <output>'",
             source="upstream_code", ref=f"{INSTRUMENTS}:184-188"),
        Fact("The burst settings are BURC count, BURD delay, BURM mode, BURP period and BURT configuration",
             source="upstream_code", ref=f"{INSTRUMENTS}:142-170"),
        Fact("The clone's notebook uses four BNC outputs numbered 1 to 4", source="upstream_code",
             ref=f"{NOTEBOOK}:8647-8659"),
        Fact("Polarity index 0 is 'negative polarity, default HIGH'", source="upstream_code",
             ref=f"{NOTEBOOK}:8707"),
        Fact("Polarity index 1 is 'positive polarity, default LOW', the notebook's off state for a laser channel",
             source="upstream_code", ref=f"{NOTEBOOK}:8709"),
        Fact("The notebook's DG645 timing constants are seconds (init_time = 1e-6 # sec, PLE_time = 5e-6 # sec)",
             source="upstream_code", ref=f"{NOTEBOOK}:8632-8633"),
        Fact("The notebook sets burst mode 1 and writes the burst period, delay and count", source="upstream_code",
             ref=f"{NOTEBOOK}:8727-8730"),
    ]
    safe_state = ("all four BNC outputs at positive polarity (LPOL 1-4,1), the clone notebook's default LOW state "
                  "for its laser channels")
    idn = True

    parameters = {
        "amplitude": Field(
            "number", unit="1", writable=True, description="Output 1 amplitude (LAMP)",
            limit=Limit.operator_required(_NO_BOUND)),
        "offset": Field(
            "number", unit="1", writable=True, description="Output 1 offset (LOFF)",
            limit=Limit.operator_required(_NO_BOUND)),
        "polarity": Field(
            "integer", unit="1", writable=True, description="Output 1 polarity index (LPOL)",
            limit=Limit.operator_required(_NO_BOUND)),
        "delay": Field(
            "number", unit="s", writable=True, description="Channel 1 delay (DLAY)",
            limit=Limit.operator_required(_NO_BOUND)),
        "holdoff": Field(
            "number", unit="s", writable=True, description="Trigger holdoff (HOLD)",
            limit=Limit.operator_required(_NO_BOUND)),
        "trigger_level": Field(
            "number", unit="1", writable=True, description="Trigger level (TLVL)",
            limit=Limit.operator_required(_NO_BOUND)),
        "trigger_rate": Field(
            "number", unit="Hz", writable=True, description="Trigger rate (TRAT)",
            limit=Limit.operator_required(_NO_BOUND)),
        "burst_count": Field(
            "integer", unit="1", writable=True, description="Burst count (BURC)",
            limit=Limit.operator_required(_NO_BOUND)),
        "burst_delay": Field(
            "number", unit="s", writable=True, description="Burst delay (BURD)",
            limit=Limit.operator_required(_NO_BOUND)),
        "burst_mode": Field(
            "integer", unit="1", writable=True, description="Burst mode (BURM)",
            limit=Limit.operator_required(_NO_BOUND)),
        "burst_period": Field(
            "number", unit="s", writable=True, description="Burst period (BURP)",
            limit=Limit.operator_required(_NO_BOUND)),
        "burst_config": Field(
            "integer", unit="1", writable=True, description="Burst configuration (BURT)",
            limit=Limit.operator_required(_NO_BOUND)),
        "timebase": Field("integer", unit="1", description="Timebase index (TIMB)"),
        "trigger_source": Field("integer", unit="1", description="Trigger source index (TSRC)"),
        "last_error": Field("string", description="Last error string (LERR)"),
    }
    reads = {
        "amplitude": {"query": "LAMP? 1", "parse": {"kind": "float"}},
        "offset": {"query": "LOFF? 1", "parse": {"kind": "float"}},
        "polarity": {"query": "LPOL? 1", "parse": {"kind": "int"}},
        "delay": {"query": "DLAY? 1", "parse": {"kind": "float"}},
        "holdoff": {"query": "HOLD?", "parse": {"kind": "float"}},
        "trigger_level": {"query": "TLVL?", "parse": {"kind": "float"}},
        "trigger_rate": {"query": "TRAT?", "parse": {"kind": "float"}},
        "burst_count": {"query": "BURC?", "parse": {"kind": "int"}},
        "burst_delay": {"query": "BURD?", "parse": {"kind": "float"}},
        "burst_mode": {"query": "BURM?", "parse": {"kind": "int"}},
        "burst_period": {"query": "BURP?", "parse": {"kind": "float"}},
        "burst_config": {"query": "BURT?", "parse": {"kind": "int"}},
        "timebase": {"query": "TIMB?", "parse": {"kind": "int"}},
        "trigger_source": {"query": "TSRC?", "parse": {"kind": "int"}},
        "last_error": {"query": "LERR?", "parse": {"kind": "str"}},
    }
    writes = {
        "amplitude": {"write": "LAMP 1,{value:.10g}", "type": "number"},
        "offset": {"write": "LOFF 1,{value:.10g}", "type": "number"},
        "polarity": {"write": "LPOL 1,{value:d}", "type": "integer"},
        "delay": {"write": "DLAY 1,0,{value:.10g}", "type": "number"},
        "holdoff": {"write": "HOLD {value:.10g}", "type": "number"},
        "trigger_level": {"write": "TLVL {value:.10g}", "type": "number"},
        "trigger_rate": {"write": "TRAT {value:.10g}", "type": "number"},
        "burst_count": {"write": "BURC {value:d}", "type": "integer"},
        "burst_delay": {"write": "BURD {value:.10g}", "type": "number"},
        "burst_mode": {"write": "BURM {value:d}", "type": "integer"},
        "burst_period": {"write": "BURP {value:.10g}", "type": "number"},
        "burst_config": {"write": "BURT {value:d}", "type": "integer"},
    }
    safety_bindings = {
        "estop": {"write": ["LPOL 1,1", "LPOL 2,1", "LPOL 3,1", "LPOL 4,1"],
                  "description": "set all four BNC outputs to positive polarity (the notebook's default LOW/OFF)"},
    }
