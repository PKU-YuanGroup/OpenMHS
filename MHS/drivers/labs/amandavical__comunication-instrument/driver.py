"""OpenMHS driver for gh.amandavical/comunication-instrument: a read-only serial measurement client.

The upstream is a demonstration of serial communication: ``Client`` wraps a ``serial.Serial`` and sends
three-letter requests, and its companion ``Instrument`` (modules/simulated_instrument.py) answers them with status,
type, voltage, temperature and current values.  The driver uses the five request words the clone dispatches
(``STA``, ``TYP``, ``VOL``, ``TMP`` and ``CUR``) and exposes the replies as state plus one read-only sensing action.

* reads: status, type, voltage, temperature and current;
* ``cap.sensing.read.v1``: the same five channels, optionally filtered by the ``fields`` input;
* the e-stop closes the serial port the upstream ``Client`` wraps and detaches it from the client
  (``Client.ser.close`` then ``Client.ser = None``); no stop command exists in the clone, and a read-only instrument
  has no other native stop or disable path.

This is a direct Driver, not the card's SerialDriver: the upstream entry class is a Python object around a serial
port, and its only stop path is closing that port, which a command table cannot express.  ``cap.device.configure.v1``
from the card is a write class and does not fit a device whose only requests are reads.

No Limit is declared: the upstream reports readings and accepts no numeric setpoint, so there is no bounded write or
invoke input.  The thresholds the demo applies after reading (80 degrees, 190 volts, 25 mA and 800 mA) are facts of
the application checks, not device limits, and are cited in ``facts`` only.

Every Fact cites a line of the clone at the pinned commit
(051c4277fb025ceaec5514e920e3554ff49b9719).  This package is model-authored and unreviewed: it is checked on the
fake backend only and nothing here ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, action, estop, read

CLIENT = "modules/comunication_client.py"
INSTRUMENT = "modules/simulated_instrument.py"


class ComunicationInstrument(Driver):
    device_id = "comunication-instrument"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R1"
    native = "modules.comunication_client:Client"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeClient"}
    model = "Communication Instrument virtual instrument"
    display_name = "Communication Instrument serial measurement client"
    tags = ["serial", "measurement", "virtual instrument", "status", "temperature", "voltage", "current"]
    facts = [
        Fact("The project simulates data collection from a virtual instrument using serial communication",
             source="vendor_doc", ref="README.md:3"),
        Fact("The virtual instrument has temperature, voltage and current attributes", source="vendor_doc",
             ref="README.md:17"),
        Fact("Client wraps a serial.Serial and writes a request as UTF-8 bytes followed by CRLF",
             source="upstream_code", ref=f"{CLIENT}:21-44"),
        Fact("read_response reads one line, decodes it and strips the surrounding whitespace",
             source="upstream_code", ref=f"{CLIENT}:59"),
        Fact("The simulated instrument dispatches the first three characters of a request as STA, TYP, VOL, TMP "
             "or CUR", source="upstream_code", ref=f"{INSTRUMENT}:58-80"),
        Fact("STA returns a random integer from 0 to 0xFFFFFFFF", source="upstream_code",
             ref=f"{INSTRUMENT}:62-63"),
        Fact("TYP returns one of a, b, c or abc", source="upstream_code", ref=f"{INSTRUMENT}:66-67"),
        Fact("VOL returns a random integer from 0 to 220", source="upstream_code", ref=f"{INSTRUMENT}:70-71"),
        Fact("TMP returns a random integer from 0 to 85", source="upstream_code", ref=f"{INSTRUMENT}:74-75"),
        Fact("CUR returns a random integer from 0 to 2000", source="upstream_code", ref=f"{INSTRUMENT}:78-79"),
        Fact("The README describes 20 temperatures, 20 voltages, 5 statuses and 30 currents per collection",
             source="vendor_doc", ref="README.md:52-77"),
        Fact("collect_types sends one TYP request per iteration of range(1, 6)", source="upstream_code",
             ref="data_collection/type_collection.py:25-29"),
        Fact("The README checks temperatures above 80 degrees, voltages above 190 volts and currents outside 25 "
             "to 800 mA", source="vendor_doc", ref="README.md:53-78"),
        Fact("check_temperatures raises TemperatureTooHighError above 80 degrees", source="upstream_code",
             ref="utilities/temperature_check.py:26-28"),
        Fact("check_voltages raises VoltageTooHighError above 190 volts and reports a voltage equal to 0",
             source="upstream_code", ref="utilities/voltage_check.py:28-33"),
        Fact("check_current_threshold prints a threshold alert below 25", source="upstream_code",
             ref="utilities/current_check.py:11-12"),
    ]
    safe_state = "serial port closed and detached from the client; no further request can be sent"

    def _query(self, command):
        """Send one of the five request words and return the reply text."""
        self.native.write_request(command)
        return self.native.read_response()

    @read("status", type="integer", description="Status value returned by the STA request")
    def status(self):
        return int(self._query("STA"))

    @read("type", type="string", description="Type value returned by the TYP request")
    def type(self):
        return str(self._query("TYP"))

    @read("voltage", type="integer", unit="V", description="Voltage returned by the VOL request, in volts")
    def voltage(self):
        return int(self._query("VOL"))

    @read("temperature", type="integer",
          description="Temperature returned by the TMP request, in the degrees of the upstream (no scale is named)")
    def temperature(self):
        return int(self._query("TMP"))

    @read("current", type="integer", unit="mA", description="Current returned by the CUR request, in milliamperes")
    def current(self):
        return int(self._query("CUR"))

    @action(cap="cap.sensing.read.v1",
            description="Read the five measurement channels of the virtual instrument; the fields input selects "
                        "which channels are returned",
            input={"fields": Field(
                type="array", items="string",
                description="Channel names to return: status, type, voltage, temperature and current. Omit the "
                            "input to return every channel")})
    def read_channels(self, fields=None):
        values = {
            "status": self.status(),
            "type": self.type(),
            "voltage": self.voltage(),
            "temperature": self.temperature(),
            "current": self.current(),
        }
        if fields is not None:
            wanted = set(fields)
            values = {name: value for name, value in values.items() if name in wanted}
        return {"values": values}

    @estop(native="ser.close")
    def stop(self):
        """Close the serial port the upstream Client wraps and detach it from the client.

        ``Client.write_request`` writes through ``self.ser`` (modules/comunication_client.py:44), so a closed and
        detached port means no further request can be sent.  The clone has no stop request.
        """
        port = self.native.ser
        if port is not None:
            port.close()
            self.native.ser = None
