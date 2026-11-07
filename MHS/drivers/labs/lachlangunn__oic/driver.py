"""OpenMHS driver for gh.lachlangunn/oic: the Arduino DAQ firmware over line-oriented SCPI.

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The upstream provides an Arduino sketch
``src/Examples/Meter/Meter.ino`` that registers ``*IDN?``, ``:SOURCE:VOLTAGE``/``:SOURCE:VOLTAGE1`` and
``:MEASURE:VOLTAGE?``/``:MEASURE:VOLTAGE1?``/``:MEASURE:VOLTAGE2?`` on a newline-terminated serial link
(``Meter.ino:33-43``), plus a Python 2 VISA host example ``src/Examples/Meter/test.py`` whose ``ArduinoDAQ`` class
opens the serial resource and issues those commands (``test.py:10-40``).  This driver speaks the same text SCPI
through the bridge's VISA/socket transport and does not import the Python 2 example.

* reads: the measured voltage on analogue inputs A0, A1 and A2;
* writes: the PWM output voltage of channel 0 (pin 3) and channel 1 (pin 5), limited to the 0-5 V full scale the
  sketch's numeric parse and scaling state;
* the e-stop writes 0 V to both source channels, the lowest value of the only outputs this driver sets.

The firmware has no readback command for the PWM outputs.  The upstream host example pairs ``write(0, ...)`` with
``read(0)`` as one channel (``test.py:79-89``), so the state fields ``voltage0`` and ``voltage1`` are the A0/A1
measurements of those channels; the fake models the loopback the example assumes, but a bench must wire the output
to the input for a write to be visible in the state.

Every Limit and Fact cites a line of the clone at the pinned commit (6c7ab800893dcd32584053b49a7825452e3119a9).  This
package is model-authored and unreviewed; it has only been checked on the fake backend and no instrument was used.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

METER = "src/Examples/Meter/Meter.ino"
HOST = "src/Examples/Meter/test.py"
PARSER = "src/ArduinoSCPIParser/scpiparser.h"

#: The firmware scales a voltage by 5.0 V into a 0-255 PWM duty and clamps it (Meter.ino:144, 191).
LIMIT0 = Limit(min=0, max=5, source="upstream_code", ref=f"{METER}:140",
               reason="scpi_parse_numeric(..., default_value=0, min_value=0, max_value=5) at Meter.ino:140 "
                      "(the declaration order is at scpiparser.h:224); line 144 scales the value by 5.0 V into "
                      "0-255 duty")
LIMIT1 = Limit(min=0, max=5, source="upstream_code", ref=f"{METER}:187",
               reason="scpi_parse_numeric(..., default_value=0, min_value=0, max_value=5) at Meter.ino:187 "
                      "(the declaration order is at scpiparser.h:224); line 191 scales the value by 5.0 V into "
                      "0-255 duty")


class Oic(ScpiDriver):
    device_id = "oic-meter"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "Examples.Meter.test:ArduinoDAQ"
    backends = {"fake": ".fake:FakeArduinoDAQ"}
    vendor, model = "Lachlan Gunn", "OIC Meter (Arduino DAQ)"
    display_name = "OIC Arduino DAQ / meter"
    tags = ["arduino", "daq", "dmm", "scpi", "serial", "pwm"]
    facts = [
        Fact("The firmware answers *IDN? with the exact line 'OIC,Embedded SCPI Example,1,10'",
             source="upstream_code", ref=f"{METER}:78"),
        Fact("The host example requires that exact identity reply and closes the resource otherwise",
             source="upstream_code", ref=f"{HOST}:14-19"),
        Fact("The serial link runs at 9600 baud and each command is one newline-terminated line of at most 256 bytes",
             source="upstream_code", ref=f"{METER}:51-62"),
        Fact("The host example opens a VISA resource with a newline terminator",
             source="upstream_code", ref=f"{HOST}:10"),
        Fact("Communication is over the device's virtual serial port with a bare-bones SCPI implementation",
             source="vendor_doc", ref="README.md:37-38"),
        Fact("The README documents ':SOURCE:VOLTAGE 1V' on pin three and ':MEASURE:VOLTAGE?' on analogue input zero",
             source="vendor_doc", ref="README.md:28-29"),
        Fact("The command tree registers *IDN?, :SOURCE:VOLTAGE, :SOURCE:VOLTAGE1, :MEASURE:VOLTAGE?, "
             ":MEASURE:VOLTAGE1? and :MEASURE:VOLTAGE2?", source="upstream_code", ref=f"{METER}:33-43"),
        Fact(":MEASURE:VOLTAGE? returns analogRead(0) * 5.0f/1024, the voltage on A0",
             source="upstream_code", ref=f"{METER}:89"),
        Fact(":MEASURE:VOLTAGE1? returns analogRead(1) * 5.0f/1024, the voltage on A1",
             source="upstream_code", ref=f"{METER}:103"),
        Fact(":MEASURE:VOLTAGE2? returns analogRead(2) * 5.0f/1024, the voltage on A2",
             source="upstream_code", ref=f"{METER}:117"),
        Fact("scpi_parse_numeric takes (string, length, default_value, min_value, max_value)",
             source="upstream_code", ref=f"{PARSER}:223-224"),
        Fact(":SOURCE:VOLTAGE parses a voltage with min 0 and max 5, scales it by 5.0 V into 0-255 and writes "
             "PWM pin 3", source="upstream_code", ref=f"{METER}:140-144"),
        Fact(":SOURCE:VOLTAGE1 parses a voltage with min 0 and max 5, scales it by 5.0 V into 0-255 and writes "
             "PWM pin 5", source="upstream_code", ref=f"{METER}:187-191"),
        Fact("A source value is a number with an optional V suffix; a bare number is volts, and the NT unit "
             "selects a raw 0-255 duty", source="upstream_code", ref=f"{METER}:141-149"),
        Fact("The host example writes source values as strings such as '0V' and '5V'",
             source="upstream_code", ref=f"{HOST}:66-67"),
        Fact("The PWM outputs are initialised to zero at setup (analogWrite(3, 0) and analogWrite(5, 0))",
             source="upstream_code", ref=f"{METER}:48-49"),
    ]
    safe_state = "both PWM source channels driven to 0 V"
    idn = {"expect": r"^OIC,Embedded SCPI Example,1,10$"}
    terminator = "\n"

    parameters = {
        "voltage0": Field(
            "number", unit="V", writable=True,
            description="Channel 0 voltage: the A0 measurement, or the PWM output on pin 3 when written",
            limit=LIMIT0),
        "voltage1": Field(
            "number", unit="V", writable=True,
            description="Channel 1 voltage: the A1 measurement, or the PWM output on pin 5 when written",
            limit=LIMIT1),
        "voltage2": Field("number", unit="V", description="Voltage measured on analogue input A2"),
    }
    reads = {
        "voltage0": {"query": ":MEASURE:VOLTAGE?", "parse": {"kind": "float"}},
        "voltage1": {"query": ":MEASURE:VOLTAGE1?", "parse": {"kind": "float"}},
        "voltage2": {"query": ":MEASURE:VOLTAGE2?", "parse": {"kind": "float"}},
    }
    writes = {
        "voltage0": {"write": ":SOURCE:VOLTAGE {value:.4g}V", "type": "number"},
        "voltage1": {"write": ":SOURCE:VOLTAGE1 {value:.4g}V", "type": "number"},
    }
    safety_bindings = {
        "estop": {"write": [":SOURCE:VOLTAGE 0V", ":SOURCE:VOLTAGE1 0V"]},
    }
