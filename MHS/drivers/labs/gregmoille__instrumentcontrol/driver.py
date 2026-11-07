"""OpenMHS driver for gh.gregmoille/instrumentcontrol: a Tektronix DPO70000 oscilloscope over SCPI.

The upstream repository is a collection of instrument-control classes.  This package drives the first entry symbol,
``pyScope.PyTektronixScope:TekDPO70000``, which wraps the Tektronix DPO70000 series oscilloscope in SCPI property
factories.  The command words occur in the clone (``ACQ:MOD``, ``ACQ:NUMSAM``, ``ACQ:STATE``, ``TRIG:STATE`` and
``:STOP``); the ScpiDriver bridge opens the instrument itself (``host``/``port`` or a VISA resource), so it does not
import the upstream package or the ``instruments`` distribution its class inherits from.

The driver covers scalar acquisition settings and state, not waveform arrays: the upstream ``CURV?`` transfer and
the channel/trigger-configuration helpers are not exposed.  The e-stop sends the upstream ``stop()`` command
(``:STOP``), which disables the trigger and stops the acquisition.

Every Limit and Fact cites a line of the clone at the pinned commit
(2cf8c78dea007c636fff1f3d006a039fc1876055).  The package is model-authored and unreviewed; its wire syntax was not
tried on an instrument.  All numbers in the fake fixture are placeholders.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

SCOPE = "pyScope/PyTektronixScope.py"

#: The acquisition mode tokens of TekDPO70000.AcquisitionMode (SCOPE:61-66).
ACQUISITION_MODES = ["SAM", "PEAK", "HIR", "AVE", "WFMDB", "ENV"]
#: The acquisition state tokens of TekDPO70000.AcquisitionState (SCOPE:75-78).
ACQUISITION_STATES = ["ON", "OFF", "RUN", "STOP"]
#: The stop-after tokens of TekDPO70000.StopAfter (SCOPE:87-88).
STOP_AFTER = ["RUNST", "SEQ"]
#: The sampling mode tokens of TekDPO70000.SamplingMode (SCOPE:97-99).
SAMPLING_MODES = ["RT", "ET", "IT"]


class TekDpo70000Scope(ScpiDriver):
    device_id = "tek-dpo70000"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pyScope.PyTektronixScope:TekDPO70000"
    backends = {"fake": ".fake:FakeTekDpo70000"}
    vendor, model = "Tektronix", "DPO70000 series oscilloscope"
    display_name = "Tektronix DPO70000 oscilloscope"
    tags = ["oscilloscope", "tektronix", "dpo70000", "scpi"]
    safe_state = "acquisition stopped (the trigger is disabled)"
    # The clone does not state the *IDN? identity of a DPO70000, so the driver does not check one.
    idn = False

    facts = [
        Fact("TekDPO70000 is the Tektronix DPO70000 series oscilloscope class", source="upstream_code",
             ref=f"{SCOPE}:34-35"),
        Fact("Acquisition modes are SAM, PEAK, HIR, AVE, WFMDB and ENV", source="upstream_code",
             ref=f"{SCOPE}:61-66"),
        Fact("Acquisition states are ON, OFF, RUN and STOP", source="upstream_code", ref=f"{SCOPE}:75-78"),
        Fact("Stop-after modes are RUNST and SEQ", source="upstream_code", ref=f"{SCOPE}:87-88"),
        Fact("Sampling modes are RT, ET and IT", source="upstream_code", ref=f"{SCOPE}:97-99"),
        Fact("Trigger states are ARMED, AUTO, DPO, PARTIAL and READY", source="upstream_code",
             ref=f"{SCOPE}:152-156"),
        Fact("ACQ:ENHANCEDE accepts AUTO and OFF", source="upstream_code", ref=f"{SCOPE}:655-660"),
        Fact("ACQ:ENHANCEDE:STATE uses 1 for true and 0 for false", source="upstream_code",
             ref=f"{SCOPE}:663-667"),
        Fact("ACQ:INTERPE accepts AUTO, ON and OFF", source="upstream_code", ref=f"{SCOPE}:669-674"),
        Fact("ACQ:MAG uses ON for true and OFF for false", source="upstream_code", ref=f"{SCOPE}:677"),
        Fact("The ACQ:NUMSAM range is 5,000 to 2,147,400,000 samples", source="upstream_code",
             ref=f"{SCOPE}:720-721"),
        Fact("run() sends :RUN and stop() sends :STOP", source="upstream_code", ref=f"{SCOPE}:960-970"),
    ]

    parameters = {
        "acquisition_mode": Field(
            "string", writable=True, description="Acquisition mode (ACQ:MOD)",
            limit=Limit(allowed=ACQUISITION_MODES, source="upstream_code", ref=f"{SCOPE}:61-66")),
        "acquisition_mode_actual": Field(
            "string", description="Acquisition mode the instrument reports (ACQ:MOD:ACT)"),
        "acquisition_num_acquisitions": Field(
            "integer", unit="1", description="Waveform acquisitions since RUN (ACQ:NUMAC)"),
        "acquisition_num_averages": Field(
            "integer", unit="1", description="Waveform acquisitions averaged (ACQ:NUMAV)"),
        "acquisition_num_envelopes": Field(
            "integer", unit="1", description="Waveform acquisitions enveloped (ACQ:NUME)"),
        "acquisition_num_frames": Field(
            "integer", unit="1", description="Frames acquired in FastFrame (ACQ:NUMFRAMESACQ)"),
        "acquisition_num_samples": Field(
            "integer", unit="1", writable=True,
            description="Minimum samples in a WfmDB waveform (ACQ:NUMSAM)",
            limit=Limit(min=5000, max=2147400000, source="upstream_code", ref=f"{SCOPE}:720-721",
                        reason="the ACQ:NUMSAM docstring states 5,000 to 2,147,400,000 samples")),
        "acquisition_sampling_mode": Field(
            "string", writable=True, description="Sampling mode (ACQ:SAMP)",
            limit=Limit(allowed=SAMPLING_MODES, source="upstream_code", ref=f"{SCOPE}:97-99")),
        "acquisition_state": Field(
            "string", writable=True, description="Acquisition state (ACQ:STATE)",
            limit=Limit(allowed=ACQUISITION_STATES, source="upstream_code", ref=f"{SCOPE}:75-78")),
        "acquisition_stop_after": Field(
            "string", writable=True,
            description="Acquire continuously or one sequence (ACQ:STOPA)",
            limit=Limit(allowed=STOP_AFTER, source="upstream_code", ref=f"{SCOPE}:87-88")),
        "acquisition_enhanced_enob": Field(
            "string", writable=True, description="Enhanced ENOB setting (ACQ:ENHANCEDE)",
            limit=Limit(allowed=["AUTO", "OFF"], source="upstream_code", ref=f"{SCOPE}:659")),
        "acquisition_enhanced_state": Field(
            "boolean", writable=True, description="Enhanced ENOB enabled (ACQ:ENHANCEDE:STATE)",
            limit=Limit(allowed=[True, False], source="upstream_code", ref=f"{SCOPE}:665-666")),
        "acquisition_interp_8bit": Field(
            "string", writable=True, description="8-bit interpolation setting (ACQ:INTERPE)",
            limit=Limit(allowed=["AUTO", "ON", "OFF"], source="upstream_code", ref=f"{SCOPE}:673")),
        "acquisition_magnivu": Field(
            "boolean", writable=True, description="MagniVu acquisition enabled (ACQ:MAG)",
            limit=Limit(allowed=[True, False], source="upstream_code", ref=f"{SCOPE}:677")),
        "trigger_state": Field("string", description="Trigger state (TRIG:STATE)"),
    }

    reads = {
        "acquisition_mode": {"query": "ACQ:MOD?", "parse": {"kind": "str"}},
        "acquisition_mode_actual": {"query": "ACQ:MOD:ACT?", "parse": {"kind": "str"}},
        "acquisition_num_acquisitions": {"query": "ACQ:NUMAC?", "parse": {"kind": "int"}},
        "acquisition_num_averages": {"query": "ACQ:NUMAV?", "parse": {"kind": "int"}},
        "acquisition_num_envelopes": {"query": "ACQ:NUME?", "parse": {"kind": "int"}},
        "acquisition_num_frames": {"query": "ACQ:NUMFRAMESACQ?", "parse": {"kind": "int"}},
        "acquisition_num_samples": {"query": "ACQ:NUMSAM?", "parse": {"kind": "int"}},
        "acquisition_sampling_mode": {"query": "ACQ:SAMP?", "parse": {"kind": "str"}},
        "acquisition_state": {"query": "ACQ:STATE?", "parse": {"kind": "str"}},
        "acquisition_stop_after": {"query": "ACQ:STOPA?", "parse": {"kind": "str"}},
        "acquisition_enhanced_enob": {"query": "ACQ:ENHANCEDE?", "parse": {"kind": "str"}},
        "acquisition_enhanced_state": {"query": "ACQ:ENHANCEDE:STATE?", "parse": {"kind": "bool"}},
        "acquisition_interp_8bit": {"query": "ACQ:INTERPE?", "parse": {"kind": "str"}},
        "acquisition_magnivu": {"query": "ACQ:MAG?", "parse": {"kind": "bool"}},
        "trigger_state": {"query": "TRIG:STATE?", "parse": {"kind": "str"}},
    }

    writes = {
        "acquisition_mode": {"write": "ACQ:MOD {value}", "type": "string"},
        "acquisition_num_samples": {"write": "ACQ:NUMSAM {value:d}", "type": "integer"},
        "acquisition_sampling_mode": {"write": "ACQ:SAMP {value}", "type": "string"},
        "acquisition_state": {"write": "ACQ:STATE {value}", "type": "string"},
        "acquisition_stop_after": {"write": "ACQ:STOPA {value}", "type": "string"},
        "acquisition_enhanced_enob": {"write": "ACQ:ENHANCEDE {value}", "type": "string"},
        "acquisition_enhanced_state": {
            "write": "ACQ:ENHANCEDE:STATE {value}", "type": "string",
            "enum_map": {True: "1", False: "0"}},
        "acquisition_interp_8bit": {"write": "ACQ:INTERPE {value}", "type": "string"},
        "acquisition_magnivu": {
            "write": "ACQ:MAG {value}", "type": "string",
            "enum_map": {True: "ON", False: "OFF"}},
    }

    # The upstream stop() sends ':STOP' (SCOPE:966-970): the acquisition and trigger stop, the safe state.
    safety_bindings = {"estop": {"write": ":STOP"}}
