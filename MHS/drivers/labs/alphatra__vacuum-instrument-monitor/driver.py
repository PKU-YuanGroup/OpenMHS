"""OpenMHS driver for gh.alphatra/vacuum-instrument-monitor: the Granville-Phillips 350 ion gauge controller.

The upstream repository is a collector toolkit for vacuum instruments.  This package drives the GP350 over its
RS-232 module through the project's own serial client, ``collectors.serial_client:SerialClient``.  The card names
that class as an entry symbol; it is the transport of the GP350 profile, and its ``send_command`` writes one ASCII
line and returns one stripped reply line (collectors/serial_client.py:34-47).  The upstream device layer
(``devices/gp350.py``) is a thin profile over the same client, so the commands below are the commands of the clone.

DEVIATION FROM THE CARD: the card's helper is ``SerialDriver``.  A SerialDriver is a configuration-only command
map; this package is a direct Driver over the upstream ``SerialClient`` so that a write can verify the controller's
readback (IGB/DGS) and reject an INVALID reply instead of reporting it as applied.  The wire syntax is unchanged.

* reads: the ion-gauge pressure (DS IG), filament 1 and filament 2 state (IGB) and degas state (DGS);
* writes: filament 1 (IG1 ON/OFF), filament 2 (IG2 ON/OFF) and degas (DG ON/OFF), each verified by its readback;
* the e-stop and the safe-state action switch both filaments and degas off (IG1 OFF, IG2 OFF, DG OFF).

The package declares R2: the controller energises the two hot-cathode ion-gauge filaments and the degas cycle, which
are heating elements (README.md:138-142).  The clone states no independent hardware stop, so the stop is the
safe-state action required by SAFE-045; it is software over the same serial line, not a physical e-stop, and
``estop_physical_ref`` is deliberately unset.

Every Fact cites a line of the clone at the pinned commit 838275818a2f48b0fbb46ea5a35cbaa857396a7e.  This package
is model-authored and unreviewed: it is checked on the fake backend only, and the loader refuses the hardware
backend of an unreviewed model-written package at R2.
"""

import re

from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop, read, write

#: The pressure reply of the upstream parser: X.XXE+XX, optionally prefixed by "* " on the RS-485 interface
#: (simulators/parser.py:7, docs/operations/gp350-wiring.md:90-94).
_PRESSURE_RE = re.compile(r"^\*?\s*([+-]?\d\.\d{2}E[+-]\d{2})$", re.IGNORECASE)

#: 9.90E+09 is the controller's "no valid reading" value, not a pressure (docs/operations/gp350-wiring.md:175-176).
_NO_READING = {"9.90E+09", "9.90E+9", "9.9E+09", "9.9E+9"}

#: Error replies of the upstream parser (simulators/parser.py:12-18).
_ERROR_REPLIES = {"OVERRUN ERROR", "PARITY ERROR", "SYNTAX ERROR", "INVALID"}


class Gp350(Driver):
    device_id = "gp350"
    device_kind = "instrument.gauge"
    mode = "hardware"
    risk = "R2"
    native = "collectors.serial_client:SerialClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSerialClient"}
    vendor = "Granville-Phillips"
    model = "350"
    display_name = "Granville-Phillips 350 ion gauge controller"
    tags = ["vacuum", "pressure", "ion gauge", "gp350", "serial", "rs-232"]
    facts = [
        Fact("The serial client sends a command plus its line terminator as ASCII and returns the stripped reply "
             "line", source="upstream_code", ref="collectors/serial_client.py:34-47"),
        Fact("The RS-232 module command DS IG returns the ion-gauge pressure; the documented reply example is "
             "1.20E-07", source="vendor_doc", ref="README.md:137"),
        Fact("The upstream GP350 parser accepts a pressure reply written X.XXE+XX and returns the value in Torr",
             source="upstream_code", ref="simulators/parser.py:85-88"),
        Fact("9.90E+09 is not a real pressure: the controller uses it when there is no valid reading, for example "
             "when the ion gauge is off", source="vendor_doc", ref="docs/operations/gp350-wiring.md:175-176"),
        Fact("DGS returns the degas status as 1 or 0", source="vendor_doc", ref="README.md:140"),
        Fact("DG ON and DG OFF control degas and answer OK or INVALID", source="vendor_doc", ref="README.md:138"),
        Fact("At high pressure DG ON can answer OK while DGS still reports degas off", source="vendor_doc",
             ref="README.md:139"),
        Fact("IG1 ON/OFF controls filament 1 and IG2 ON/OFF controls filament 2", source="vendor_doc",
             ref="README.md:141-142"),
        Fact("IGB returns a two-digit filament status; the documented values are 00, 01, 10 and 11",
             source="vendor_doc", ref="docs/development/dzialanie.md:33"),
        Fact("The upstream simulator encodes IGB as 01 when filament 1 is on, 10 when filament 2 is on and 11 when "
             "both are on", source="upstream_code", ref="simulators/simulator.py:303-312"),
        Fact("The upstream simulator answers INVALID when a filament or degas switch already has the requested "
             "state", source="upstream_code", ref="simulators/simulator.py:365-379"),
    ]
    safe_state = "both ion-gauge filaments off and degas off"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("pressure", unit="Pa", native_unit="Torr",
          description="Absolute pressure reported by the ion gauge (DS IG reply, converted from Torr to Pa)")
    def pressure(self):
        return self._read_pressure()

    @read("filament_1", type="boolean", description="True when IGB reports filament 1 on")
    def filament_1(self):
        return self._read_filament(1)

    @read("filament_2", type="boolean", description="True when IGB reports filament 2 on")
    def filament_2(self):
        return self._read_filament(2)

    @read("degas", type="boolean", description="True when DGS reports the degas cycle on")
    def degas(self):
        return self._read_degas()

    # -- writes -----------------------------------------------------------------------------------------------
    @write("filament_1", type="boolean",
           description="Switch ion-gauge filament 1 on or off (IG1 ON/OFF)")
    def set_filament_1(self, value):
        return self._set_switch("IG1", bool(value), self._read_filament_1)

    @write("filament_2", type="boolean",
           description="Switch ion-gauge filament 2 on or off (IG2 ON/OFF)")
    def set_filament_2(self, value):
        return self._set_switch("IG2", bool(value), self._read_filament_2)

    @write("degas", type="boolean",
           description="Switch the degas cycle on or off (DG ON/OFF)")
    def set_degas(self, value):
        return self._set_switch("DG", bool(value), self._read_degas)

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Switch both filaments and degas off; the runtime latches before it calls this."""
        self._all_off()

    @action(name="x-cap.alphatra.safe_state.v1", safe_state=True,
            description="Switch both ion-gauge filaments and the degas cycle off",
            output={"state": Field("string",
                                   description="The off commands sent to the controller, in order")})
    def all_off(self):
        """The safe-state action: the same commands as the e-stop, run after it during an e-stop."""
        self._all_off()
        return {"state": "IG1 OFF, IG2 OFF, DG OFF"}

    # -- native helpers ---------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()

    def _command(self, command: str) -> str:
        reply = self.native.send_command(command)
        if not isinstance(reply, str):
            raise DriverFailed("MHS.ADAPTER.SHIM_FAILED",
                               f"the serial client returned {type(reply).__name__}, not text")
        return reply.strip()

    def _read_pressure(self) -> float:
        reply = self._command("DS IG")
        text = reply.strip()
        if not text:
            raise DriverFailed("MHS.OUTCOME.TIMEOUT", "the controller did not answer DS IG")
        if text.upper() in _NO_READING:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the controller reports no valid pressure reading ({text})")
        if text.upper() in _ERROR_REPLIES or text.startswith("? "):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the controller answered {text!r} to DS IG")
        match = _PRESSURE_RE.match(text)
        if not match:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the DS IG reply is not a GP350 pressure: {text!r}")
        return float(match.group(1))

    def _read_filament_1(self) -> bool:
        return self._read_filament(1)

    def _read_filament_2(self) -> bool:
        return self._read_filament(2)

    def _read_filament(self, number: int) -> bool:
        reply = self._command("IGB")
        text = reply.strip().upper()
        if len(text) != 2 or any(character not in "01" for character in text):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the IGB reply is not a filament status: {reply!r}")
        return text[1] == "1" if number == 1 else text[0] == "1"

    def _read_degas(self) -> bool:
        reply = self._command("DGS")
        text = reply.strip().upper()
        if text not in ("0", "1"):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the DGS reply is not a degas status: {reply!r}")
        return text == "1"

    def _set_switch(self, switch: str, on: bool, readback) -> bool:
        command = f"{switch} {'ON' if on else 'OFF'}"
        reply = self._command(command)
        if reply not in ("OK", "INVALID"):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the controller answered {reply!r} to {command}")
        actual = readback()
        if actual != on:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"{command} answered {reply!r} but the controller reports the switch {actual!r}, not {on!r}",
                native_code=reply,
            )
        return on

    def _all_off(self) -> None:
        for switch in ("IG1", "IG2", "DG"):
            reply = self._command(f"{switch} OFF")
            if reply not in ("OK", "INVALID"):
                raise DriverFailed("MHS.DEVICE.FAULTED", f"the controller answered {reply!r} to {switch} OFF")
