"""OpenMHS driver for gh.croesnick/keithley-daq6510: the identity query of a Keithley DAQ6510.

The clone is a small sample library, not a measurement API.  Its one instrument operation is ``idn = Operation('*IDN?')``
(``src/keithley_daq6510/instrument.py:10``); ``VisaInstrument`` forwards ``query`` and ``command`` to pyvisa
(``src/keithley_daq6510/visa_instrument.py:24-28``), and the SCPI operation layer sends a string ending in ``?`` as a
query and every other string as a command (``src/keithley_daq6510/scpi/operation/__init__.py:121``).  The clone declares
no measurement, range, channel, trigger or output command, so this package binds only what the clone states: the identity.

* read state: ``idn``, the reply to ``*IDN?``;
* read capability: ``x-cap.croesnick.identity.v1``, an extension because no catalogue class carries an instrument
  identity query;
* no write, no action with an input, no numeric limit and no stop command: the clone actuates nothing.

This is the card's ScpiDriver family configuration, not a direct driver.  The bridge opens the transport itself
(``host``/``port`` or a VISA resource, options of the hardware backend); the fake backend is a package-local SCPI
transport stand-in.  Every Fact cites a line of the clone at the pinned commit
(4c800f325a14a1051819ad089e4b1fc918aab8d4).  This package is model-authored and unreviewed; it is checked on the fake
backend only, and no hardware run has been made.
"""

from mhs.driver import Action, Fact, Field, ScpiDriver

INSTRUMENT = "src/keithley_daq6510/instrument.py"
VISA_INSTRUMENT = "src/keithley_daq6510/visa_instrument.py"
OPERATION = "src/keithley_daq6510/scpi/operation/__init__.py"
FIXTURE = "tests/fixtures/devices.yml"
TEST = "tests/test_instrument.py"


class KeithleyDaq6510(ScpiDriver):
    device_id = "keithley-daq6510"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "keithley_daq6510.instrument:Instrument"
    backends = {"fake": ".fake:FakeDaq6510"}
    vendor = "Keithley Instruments"
    model = "DAQ6510"
    display_name = "Keithley DAQ6510 data acquisition system (identity only)"
    tags = ["keithley", "daq6510", "data acquisition", "scpi", "visa", "identity"]
    facts = [
        Fact("The package is a sample library for the Keithley DAQ6510 instrument that uses pyvisa and pyvisa-sim",
             source="vendor_doc", ref="README.rst:23"),
        Fact("Instrument subclasses VisaInstrument", source="upstream_code", ref=f"{INSTRUMENT}:9"),
        Fact("Instrument declares the SCPI query *IDN? as its idn operation", source="upstream_code",
             ref=f"{INSTRUMENT}:10"),
        Fact("VisaInstrument.query forwards to conn.query and VisaInstrument.command forwards to conn.write",
             source="upstream_code", ref=f"{VISA_INSTRUMENT}:24-28"),
        Fact("Operation sends a command ending in '?' through query and every other command through command",
             source="upstream_code", ref=f"{OPERATION}:121"),
        Fact("The upstream pyvisa-sim fixture declares an *IDN? dialogue with a Keithley Instruments reply",
             source="upstream_code", ref=f"{FIXTURE}:9-10"),
        Fact("The upstream test asserts that Instrument.idn() returns the fixture identity reply",
             source="upstream_code", ref=f"{TEST}:16-17"),
        Fact("The upstream pyvisa-sim fixture also declares a :STATus:CLEar command with no reply",
             source="upstream_code", ref=f"{FIXTURE}:11"),
    ]
    #: The only reply the clone records begins with "Keithley Instruments"; the model suffix is not asserted.
    idn = {"expect": "^Keithley Instruments"}

    parameters = {
        "idn": Field("string", description="Identity string returned by the *IDN? query"),
    }
    reads = {
        "idn": {"query": "*IDN?", "parse": {"kind": "str"}},
    }
    commands = {
        "x-cap.croesnick.identity.v1": {
            "query": "*IDN?",
            "parse": {"kind": "str"},
            "result": {"map": {"idn": "output.$"}},
        },
    }
    actions = {
        "x-cap.croesnick.identity.v1": Action(
            name="identify",
            description="Read the identity of the instrument with *IDN? and return its reply",
            verb="read",
            output={"idn": Field("string", description="Identity string returned by the instrument")},
        ),
    }
