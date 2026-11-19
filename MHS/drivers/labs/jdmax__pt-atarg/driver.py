"""OpenMHS driver for gh.jdmax/pt-atarg: the Lake Shore Model 218 temperature monitor.

The upstream repository is an EPICS soft-IOC device pack.  The card's entry symbols are
``devices.ls218:Device`` and ``devices.ls218:DeviceConnection``; this package serves the second one, the class that
actually talks to the instrument.  ``Device`` only creates softioc analog-input records and hands the reads to a
``DeviceConnection`` (devices/ls218.py:6-19); a hardware deployment would need pythonSoftIOC and the soft-IOC PV
layer, while ``DeviceConnection`` is the plain serial-over-Ethernet transport.

The card's helper is ``PythonObjectDriver`` and that family fits the runtime: the native class is an ordinary
Python object with one method, ``read_all()``, which writes the ASCII command ``KRDG? 0`` and parses the reply into
a list of floats (devices/ls218.py:29-35).  The card's ``decision`` says direct-driver; the package uses the card's
helper family instead (DEVIATION FROM THE CARD, recorded in RESULT.json).

* read state: ``temperatures``, the list of channel readings one ``KRDG? 0`` reply returns;
* one observational extension action, ``x-cap.jdmax.read_channels.v1``, that performs the same read once.  No
  catalogue class fits the channel array: ``cap.sensing.read.v1`` binds sensor/sensor.imu/sensor.force_torque and
  returns a ``values`` object, while ``cap.measure.temperature.v1`` takes one probe and returns one temperature in
  Celsius.  The clone states neither the unit nor a per-channel selection, so the package does not invent either;
  ``RESULT.json`` requests the extension.

The Model 218 monitors temperatures and drives no actuator.  The clone defines no stop, close, disable or abort
method on ``DeviceConnection``; its whole public interface is the constructor and ``read_all`` (devices/ls218.py:22-38
and devices/telnet_base.py:27-38). The safety binding performs a fresh measurement query as a communication check.
It neither drains nor cancels an in-flight query and changes no actuator state; the runtime latch is the only
command protection. No physical stop, interlock or hardware e-stop is claimed.

Every Fact cites a line of the clone at commit 476a6a21a7a31d0a457fcb5519a18214cc2b19e0.  This package is
model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null); it is checked on the fake backend only,
and nothing here ran against a Model 218 or opened a serial-to-Ethernet socket.
"""

from mhs.driver import Action, Fact, Field, PythonObjectDriver

#: The upstream file that holds both card entry symbols.
LS218 = "devices/ls218.py"


class Ls218(PythonObjectDriver):
    device_id = "ls218"
    device_kind = "instrument.thermometer"
    mode = "hardware"
    risk = "R1"
    native = "devices.ls218:DeviceConnection"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLs218"}
    vendor = "Lake Shore Cryotronics"
    model = "Model 218 temperature monitor"
    display_name = "Lake Shore Model 218 temperature monitor (devices.ls218.DeviceConnection)"
    tags = ["lakeshore", "temperature", "thermometer", "serial-over-ethernet", "read-only"]
    facts = [
        Fact("DeviceConnection is the Lake Shore Model 218 connection class; it handles the instrument over serial "
             "over Ethernet", source="upstream_code", ref=f"{LS218}:22-27"),
        Fact("read_all writes the ASCII command KRDG? 0 followed by a newline, reads one line, and returns the "
             "decimal numbers its regular expression finds", source="upstream_code", ref=f"{LS218}:29-35"),
        Fact("The written command is KRDG? 0, where the comment says 0 means all channels", source="upstream_code",
             ref=f"{LS218}:32"),
        Fact("The Device class creates one softioc analog-input record per configured channel and creates a "
             "DeviceConnection from the ip, port and timeout settings", source="upstream_code", ref=f"{LS218}:9-19"),
        Fact("The sample settings file configures the lakeshore_218 IOC with module devices.ls218 and port 23, "
             "channel 1 of a serial-to-Ethernet adapter, with a 2 s timeout", source="upstream_code",
             ref="settings.yaml:9-15"),
        Fact("The sample settings file lists eight channel slots for the 218 and publishes only Test_TI, with "
             "EGU set to K", source="upstream_code", ref="settings.yaml:17-37"),
        Fact("TelnetConnection opens telnetlib.Telnet(host, port, timeout) and stores it as self.tn; it defines no "
             "close, stop, abort or disable method", source="upstream_code", ref="devices/telnet_base.py:27-38"),
        Fact("The IOC host imports the device module, constructs module.Device(device_name, ioc_settings), calls "
             "connect() and then repeatedly awaits device.do_reads()", source="upstream_code",
             ref="master_ioc.py:50-76"),
        Fact("DeviceConnection has no stop path: the class body is its constructor and read_all, and its base "
             "TelnetConnection has only the constructor", source="upstream_code", ref=f"{LS218}:22-38"),
    ]
    safe_state = ("no actuator is driven by this temperature monitor; the runtime latch refuses effectful commands. "
                  "The e-stop performs a fresh KRDG? 0 communication check and does not cancel an in-flight read")

    parameters = {
        "temperatures": Field(
            "array", min_items=1, items=Field("number", description="One channel reading parsed from the KRDG? 0 reply"),
            description="Channel readings returned by one read_all() (KRDG? 0); the clone states no unit and the "
                        "array length is the number of channels the instrument answers"),
    }
    reads = {
        "temperatures": {"native": "read_all", "invoke": "call", "timeout_ms": 2500},
    }
    commands = {
        "x-cap.jdmax.read_channels.v1": {
            "native": "read_all", "invoke": "call",
            "result": {"map": {"temperatures": "output.$"}},
            "concurrency": "shared", "timeout_ms": 2500,
        },
    }
    actions = {
        "x-cap.jdmax.read_channels.v1": Action(
            name="read_channels", verb="read",
            description="Read every channel with one KRDG? 0 query and return the parsed numbers; it changes nothing",
            output={"temperatures": Field(
                "array", min_items=1, items=Field("number", description="One channel reading parsed from the KRDG? 0 reply"),
                description="Channel readings of one KRDG? 0 reply, in reply order")},
        ),
    }
    safety_bindings = {
        "estop": {
            "native": "read_all", "invoke": "call", "timeout_ms": 2500,
            "description": "the native class has no stop, close or disable call; read_all starts a fresh KRDG? 0 "
                           "communication check. It does not drain or cancel another read and changes no actuator "
                           "state; the runtime latch is the only command protection",
        },
    }
