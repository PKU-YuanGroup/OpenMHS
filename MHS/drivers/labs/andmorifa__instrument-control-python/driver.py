"""OpenMHS driver for gh.andmorifa/instrument-control-python: a Red Pitaya SCPI-over-TCP client.

The clone contains one class, ``redpitaya_client:RedPitayaClient`` (src/redpitaya_client.py:9), a thin SCPI client:
it opens a TCP socket (lines 26-39), sends a command as UTF-8 bytes followed by CRLF (lines 41-53), returns one
stripped response line (lines 55-62), closes the socket (lines 64-71), and has a ``get_mock_data`` helper that
generates a synthetic sine wave for testing without hardware (lines 73-81).

The clone defines no device-specific command table and no acquisition command (the only command text is the reset
example ``GEN:RST`` in the send_cmd docstring, line 44), so the driver does not invent one and does not present
``get_mock_data`` as a measurement:

* one read, ``connected``: the upstream ``is_connected`` flag, set by ``connect`` and cleared by ``close``;
* one extension, ``x-cap.andmorifa.scpi_query.v1``: it forwards one caller-supplied SCPI query through the
  upstream ``query`` and returns the response text.  The caller supplies the command because the clone has no
  command table;
* the native stop is ``close``: after it the client cannot send a command, because ``send_cmd`` requires
  ``is_connected`` and the socket is closed.  An operator reset runs ``reconnect``, which calls the upstream
  ``connect`` and opens a new socket.

No Limit is declared: the driver has no numeric write or invoke input, so there is no bound to source.  The mock
signal array is a test helper, not a device measurement, and the driver never returns it.

Every Fact cites a line of the clone at the pinned commit (0622a4aee5cf8b7a4704711d1fdf81fe35b0b6ff).  This package
is model-authored and unreviewed: it is checked on the fake backend only, no hardware was attached, and the hardware
backend stays an operator decision.
"""

from mhs.driver import Driver, Fact, Field, action, estop, read, reset


class RedPitaya(Driver):
    device_id = "redpitaya"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "redpitaya_client:RedPitayaClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRedPitaya"}
    vendor, model = "Red Pitaya", "SCPI-over-TCP client"
    display_name = "Red Pitaya SCPI client (redpitaya_client.RedPitayaClient)"
    tags = ["red pitaya", "scpi", "tcp", "signal acquisition", "connection"]
    facts = [
        Fact("RedPitayaClient is a class for SCPI communication with Red Pitaya hardware over TCP/IP",
             source="upstream_code", ref="src/redpitaya_client.py:9-13"),
        Fact("connect opens an AF_INET/SOCK_STREAM socket, sets is_connected True after connecting, and sets it "
             "False and re-raises when the connection fails", source="upstream_code",
             ref="src/redpitaya_client.py:30-39"),
        Fact("send_cmd appends CRLF to the command and sends it as UTF-8 bytes", source="upstream_code",
             ref="src/redpitaya_client.py:50-52"),
        Fact("query sends the command and returns the decoded, stripped response read from the socket",
             source="upstream_code", ref="src/redpitaya_client.py:55-62"),
        Fact("close closes the socket and sets is_connected to False", source="upstream_code",
             ref="src/redpitaya_client.py:64-71"),
        Fact("get_mock_data generates a synthetic sine wave with noise for testing without physical hardware",
             source="upstream_code", ref="src/redpitaya_client.py:73-81"),
        Fact("The README names SCPI over TCP/IP as the protocol and a Mock Mode that simulates signal acquisition "
             "without physical hardware", source="vendor_doc", ref="README.md:17-19"),
    ]
    safe_state = "SCPI socket closed; the client cannot send a command after close"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("connected", type="boolean", description="True while the TCP connection to the instrument is open")
    def connected(self):
        return bool(self.native.is_connected)

    # -- the caller-supplied SCPI query ------------------------------------------------------------------------
    @action(
        name="x-cap.andmorifa.scpi_query.v1",
        description="Send one SCPI query through the client and return the response text",
        input={"command": Field(
            "string",
            description="SCPI command text forwarded verbatim; the upstream query appends CRLF and reads one "
                        "response")},
        output={"response": Field(
            "string",
            description="Response text returned by the instrument (decoded and stripped by the upstream query)")},
    )
    def scpi_query(self, command):
        return {"response": self.native.query(command)}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """Close the SCPI socket; ``send_cmd`` refuses a command once ``is_connected`` is False."""
        self.native.close()

    def teardown(self):
        self.native.close()

    @reset
    def reconnect(self):
        """Open a new TCP socket after the operator accepts a reset of the latched e-stop."""
        self.native.connect()
