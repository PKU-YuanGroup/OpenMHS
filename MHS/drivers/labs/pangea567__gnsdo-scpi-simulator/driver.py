"""OpenMHS driver for gh.pangea567/gnsdo-scpi-simulator: a serial SCPI GNSDO (GPS-disciplined rubidium oscillator).

A SerialDriver is configuration only: the class attributes below are the command map of the serial bridge, and the
runtime enforces every input before a command reaches the wire.  The upstream repository is a simulator of the
device's serial SCPI behaviour (README.md:3-5), not a client library; it is never imported or run by this package.
The bridge opens a pyserial port for the hardware view, while the fake backend is the package's own in-memory serial
transport.

* reads: identity, lock state, time interval error, health bit mask, tracked/visible satellites, PCB and CSAC
  temperatures, TCXO and supply voltages, DIAG/CSAC runtime hours, leap seconds, PTIME output/date/time and holdover
  duration.  The multiline composite reports (``SYNC?``, ``GPS?``, ``MEAS?``, ``DIAG?``, ``CSAC?``, ``PTIME?`` and
  ``SYST:STAT?``) are not covered: the serial bridge reads one response line per command, and a composite would leave
  its remaining lines in the input buffer for the next command.
* actions: start or recover from holdover, set the reference source mode, and enable or disable the PTIME output.
  The catalogue has no clock, holdover, GNSS or reference-source class, so these are ``x-cap.pangea567.*`` extensions
  with an inline schema.  The driver declares no write parameter and no limit.
* no safety-relevant actuation: the commands change the reference source, holdover state and time-sharing output of a
  time-frequency reference; the device exposes no heater, laser, motion or other hazardous output.

Every Fact cites a line of the clone at the pinned commit a2d57a9759ab72fcfa42578a505d8ca4248bc0a4.  This package is
model-authored and unreviewed: it is checked on the fake backend only, never ran on hardware, and claims no
MHS-Device level.
"""

from mhs.driver import Action, Fact, Field, SerialDriver

CLONE = "src/gnsdo_simulator"


class GnsdoScpiSimulator(SerialDriver):
    device_id = "gnsdo"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "gnsdo_simulator.serial_server:SerialServer"
    backends = {"fake": ".fake:FakeGnsdoScpiSimulator"}
    vendor = "Jackson Labs"
    model = "Low Noise Rubidium GNSDO (PRE), GPS/GNSS-disciplined rubidium oscillator"
    display_name = "Jackson Labs Low Noise Rubidium GNSDO"
    tags = ["gnsdo", "gpsdo", "gnss", "rubidium", "oscillator", "time reference", "serial", "scpi"]
    baudrate = 115200
    timeout_s = 1.0
    terminator = "\r\n"
    facts = [
        Fact("The upstream repository is a Linux serial-port simulator of the SCPI behaviour of a Low Noise Rubidium "
             "GNSDO, a GPS/GNSS-disciplined rubidium time-frequency reference; it is not a client library.",
             source="vendor_doc", ref="README.md:3-5"),
        Fact("The serial port is 8N1 at 115200 baud", source="vendor_doc", ref="README.md:53"),
        Fact("A client writes a command line ending in CRLF (the README shows b'*IDN?\\r\\n')", source="vendor_doc",
             ref="README.md:143"),
        Fact("The simulator writes a response followed by CRLF", source="upstream_code",
             ref=f"{CLONE}/serial_server.py:124"),
        Fact("Command matching is case-insensitive: normalize_command strips the line ends and returns text.upper()",
             source="upstream_code", ref=f"{CLONE}/scpi_parser.py:52-76"),
        Fact("A command with a value is split at the first space into a command prefix and its value",
             source="upstream_code", ref=f"{CLONE}/scpi_parser.py:169"),
        Fact("The identity reply is 'Jackson Labs, LN Rb GPSDO (PRE), Firmware Rev <firmware>'",
             source="upstream_code", ref=f"{CLONE}/commands/system.py:42-43"),
        Fact("SYNC:LOCKED? answers '1' when the oscillator is locked and '0' when it is not", source="upstream_code",
             ref=f"{CLONE}/commands/sync.py:81-85"),
        Fact("SYNC:TINT? is the time interval error in seconds, printed in scientific notation",
             source="upstream_code", ref=f"{CLONE}/commands/sync.py:90-116"),
        Fact("SYNC:HEALTH? is a hexadecimal bit mask: 0x4 is a TINT above 210 ns, 0x8 a runtime below 200 s, 0x10 a "
             "holdover above 60 s and 0x400 a hardware fault", source="upstream_code",
             ref=f"{CLONE}/commands/sync.py:121-158"),
        Fact("SYNC:HOLD:INIT sets holdover, clears the lock and records the holdover start; SYNC:HOLD:REC:INIT clears "
             "holdover, restores the lock and clears the start", source="upstream_code",
             ref=f"{CLONE}/commands/sync.py:184-210"),
        Fact("SYNC:SOUR:MODE <value> stores any non-empty value as the synchronization source mode",
             source="upstream_code", ref=f"{CLONE}/commands/sync.py:216-225"),
        Fact("SYNC:HOLD:DUR? answers two comma-separated numbers: the holdover duration in seconds and 1 while in "
             "holdover or 0 otherwise", source="upstream_code", ref=f"{CLONE}/commands/sync.py:163-179"),
        Fact("GPS:SAT:TRAC:COUN? and GPS:SAT:VIS:COUN? answer the tracked and visible satellite counts",
             source="upstream_code", ref=f"{CLONE}/commands/gps.py:173-186"),
        Fact("MEAS:TEMP? returns the PCB temperature", source="upstream_code",
             ref=f"{CLONE}/commands/measure.py:31-35"),
        Fact("MEAS:VOLT? returns the TCXO adjustment voltage, not the power-supply voltage; the comment gives about "
             "1.6 to 1.7 V from a real device output", source="upstream_code", ref=f"{CLONE}/device_state.py:123-129"),
        Fact("MEAS:POW? returns the power-supply input voltage; the comment gives about 11.7 to 11.74 V from a real "
             "device output", source="upstream_code", ref=f"{CLONE}/device_state.py:160-162"),
        Fact("CSAC:STATUS? answers 0 when the atomic clock module is healthy and 1 when it is not",
             source="upstream_code", ref=f"{CLONE}/commands/csac.py:22-33"),
        Fact("CSAC:TEMP?, CSAC:SN? and CSAC:LIFE? answer the module temperature, serial number and lifetime hours",
             source="upstream_code", ref=f"{CLONE}/commands/csac.py:38-59"),
        Fact("PTIME:OUTPUT? answers 1 or 0, while the PTIME:OUTPUT setter accepts ON or OFF",
             source="upstream_code", ref=f"{CLONE}/commands/ptime.py:61-87"),
        Fact("PTIME:LEAP:ACC? answers the accumulated GPS-UTC leap seconds", source="upstream_code",
             ref=f"{CLONE}/commands/ptime.py:90-94"),
        Fact("DIAG:LIFE:COUN? answers the lifetime in hours, increased by the simulator's runtime",
             source="upstream_code", ref=f"{CLONE}/commands/diagnostic.py:26-32"),
        Fact("The simulator considers the oscillator locked only when at least four satellites are tracked",
             source="upstream_code", ref=f"{CLONE}/device_state.py:230-236"),
        Fact("The GPS survey variance limit is 150000 in the simulator state", source="upstream_code",
             ref=f"{CLONE}/device_state.py:79"),
        Fact("The atomic-lock warmup time is 120 s, from the manual's 'less than 2 minutes warmup time to atomic "
             "lock' comment", source="upstream_code", ref=f"{CLONE}/device_state.py:226-228"),
    ]

    parameters = {
        "identity": Field("string", description="Identity string the device returns to *IDN?"),
        "sync_locked": Field("boolean", description="True when the oscillator reports that it is locked to its "
                                                    "reference (SYNC:LOCKED?)"),
        "tint": Field("number", unit="s", description="Time interval error against the GPS reference (SYNC:TINT?)"),
        "health": Field("string", description="Health status bit mask reported in hexadecimal (SYNC:HEALTH?)"),
        "satellites_tracked": Field("integer", unit="1", description="Satellites currently tracked "
                                                                     "(GPS:SAT:TRAC:COUN?)"),
        "satellites_visible": Field("integer", unit="1", description="Satellites currently visible "
                                                                     "(GPS:SAT:VIS:COUN?)"),
        "pcb_temperature": Field("number", unit="Cel", description="PCB temperature (MEAS:TEMP?)"),
        "tcxo_voltage": Field("number", unit="V", description="TCXO adjustment voltage (MEAS:VOLT?)"),
        "power_supply_voltage": Field("number", unit="V", description="Power-supply input voltage (MEAS:POW?)"),
        "csac_temperature": Field("number", unit="Cel", description="Atomic clock module temperature (CSAC:TEMP?)"),
        "csac_status": Field("integer", unit="1", description="CSAC status: 0 healthy, 1 not healthy (CSAC:STATUS?)"),
        "lifetime": Field("integer", unit="h", description="Lifetime in hours (DIAG:LIFE:COUN?)"),
        "csac_lifetime": Field("integer", unit="h", description="Atomic clock module lifetime in hours (CSAC:LIFE?)"),
        "leap_seconds": Field("integer", unit="s", description="Accumulated GPS-UTC leap seconds (PTIME:LEAP:ACC?)"),
        "ptime_output": Field("boolean", description="True when the time-sharing output is enabled (PTIME:OUTPUT? "
                                                     "answers 1 or 0)"),
        "ptime_date": Field("string", description="Date reported as year,month,day without leading zeros "
                                                  "(PTIME:DATE?)"),
        "ptime_time": Field("string", description="Time reported as hour,minute,second without leading zeros "
                                                  "(PTIME:TIME?)"),
        "holdover_duration": Field("string", description="Comma-separated holdover duration in seconds and holdover "
                                                          "flag (SYNC:HOLD:DUR?)"),
    }
    reads = {
        "identity": {"command": "*IDN?", "parse": {"kind": "str"}},
        "sync_locked": {"command": "SYNC:LOCKED?", "parse": {"kind": "bool"}},
        "tint": {"command": "SYNC:TINT?", "parse": {"kind": "float"}},
        "health": {"command": "SYNC:HEALTH?", "parse": {"kind": "str"}},
        "satellites_tracked": {"command": "GPS:SAT:TRAC:COUN?", "parse": {"kind": "int"}},
        "satellites_visible": {"command": "GPS:SAT:VIS:COUN?", "parse": {"kind": "int"}},
        "pcb_temperature": {"command": "MEAS:TEMP?", "parse": {"kind": "float"}},
        "tcxo_voltage": {"command": "MEAS:VOLT?", "parse": {"kind": "float"}},
        "power_supply_voltage": {"command": "MEAS:POW?", "parse": {"kind": "float"}},
        "csac_temperature": {"command": "CSAC:TEMP?", "parse": {"kind": "float"}},
        "csac_status": {"command": "CSAC:STATUS?", "parse": {"kind": "int"}},
        "lifetime": {"command": "DIAG:LIFE:COUN?", "parse": {"kind": "int"}},
        "csac_lifetime": {"command": "CSAC:LIFE?", "parse": {"kind": "int"}},
        "leap_seconds": {"command": "PTIME:LEAP:ACC?", "parse": {"kind": "int"}},
        "ptime_output": {"command": "PTIME:OUTPUT?", "parse": {"kind": "bool"}},
        "ptime_date": {"command": "PTIME:DATE?", "parse": {"kind": "str"}},
        "ptime_time": {"command": "PTIME:TIME?", "parse": {"kind": "str"}},
        "holdover_duration": {"command": "SYNC:HOLD:DUR?", "parse": {"kind": "str"}},
    }
    actions = {
        "x-cap.pangea567.holdover.v1": Action(
            name="start_holdover",
            description="Put the oscillator into holdover (the device keeps the last known frequency without GPS)",
            output={"initiated": Field("boolean", description="True after the holdover command was accepted")}),
        "x-cap.pangea567.holdover_recovery.v1": Action(
            name="recover_from_holdover",
            description="End holdover and return the oscillator to its reference",
            output={"recovered": Field("boolean", description="True after the recovery command was accepted")}),
        "x-cap.pangea567.sync_source.v1": Action(
            name="set_sync_source",
            description="Set the synchronization source mode; the clone's documentation names GPS, EXTERNAL and "
                        "INTERNAL as examples, and the upstream setter stores any non-empty value",
            input={"mode": Field("string", description="Reference source mode, for example GPS, EXTERNAL or "
                                                       "INTERNAL")},
            output={"accepted": Field("boolean", description="True after the command was accepted")},
            examples=[{"mode": "GPS"}]),
        "x-cap.pangea567.ptime_output.v1": Action(
            name="set_ptime_output",
            description="Enable or disable the PTIME time-sharing output",
            input={"enabled": Field("boolean", description="True enables the time-sharing output; false disables "
                                                          "it")},
            output={"accepted": Field("boolean", description="True after the command was accepted")},
            examples=[{"enabled": True}]),
    }
    commands = {
        "x-cap.pangea567.holdover.v1": {
            "command": "SYNC:HOLD:INIT",
            "parse": {"kind": "str"},
            "result": {"initiated": {"value": True}},
        },
        "x-cap.pangea567.holdover_recovery.v1": {
            "command": "SYNC:HOLD:REC:INIT",
            "parse": {"kind": "str"},
            "result": {"recovered": {"value": True}},
        },
        "x-cap.pangea567.sync_source.v1": {
            "command": "SYNC:SOUR:MODE {mode}",
            "args": {"mode": {"from": "input.mode"}},
            "parse": {"kind": "str"},
            "result": {"accepted": {"value": True}},
        },
        "x-cap.pangea567.ptime_output.v1": {
            "command": "PTIME:OUTPUT {state}",
            "args": {"state": {"from": "input.enabled", "enum_map": {True: "ON", False: "OFF"}}},
            "parse": {"kind": "str"},
            "result": {"accepted": {"value": True}},
        },
    }
