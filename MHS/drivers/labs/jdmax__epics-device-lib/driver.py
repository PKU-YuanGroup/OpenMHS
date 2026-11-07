"""OpenMHS driver for gh.jdmax/epics-device-lib: the Lake Shore Model 336 temperature controller.

A direct Driver (decorated methods) over the upstream protocol class
``instruments.ls336:DeviceConnection``.  That class is the telnet/serial-over-Ethernet connection of the repository's
ls336 soft-IOC device: every command is a text line written to ``self.tn`` and every answer is parsed with a regular
expression (instruments/ls336.py:99-272).  The card lists three unrelated ``DeviceConnection`` classes (dp832, ls336
and zaber_motor); this package integrates the ls336 one, the only entry whose per-channel reads and writes, the
``mbbOut mode/range`` PVs and the ``cap.thermal.setpoint.v1`` candidate class describe the same instrument.  The
repository's other device modules (README.md:11-33) are other devices and are not served here.

Scope of this package
---------------------
* reads: the four Kelvin sensor readings (``KRDG? 0``), the configured output's heater output, manual heater output,
  output mode and heater range, and the reply to ``PID?``, which the upstream sends without an output number;
* writes: the setpoint of the configured output, the manual heater percentage and the heater range;
* the catalogue class ``cap.thermal.setpoint.v1`` sets the configured output's setpoint and reports the setpoint and
  the configured sensor channel's temperature;
* the e-stop and the ``safe_state`` action command the configured heater output off
  (``OUTMODE <channel>,0,<channel>,0``: mode 0 is the Off menu entry, and the same command sets that output's control
  input to input ``<channel>`` and its powerup enable to 0, as the upstream ``do_sets`` does); the safe-state action
  confirms mode 0 with a fresh ``OUTMODE?`` read; the input-free re-enable action commands the output back to the
  configured control mode.

The clone is a template/submodule library, not a single device: ``DeviceConnection`` takes an explicit output channel,
and the deployed soft-IOC settings choose that channel and the controller's temperature unit.  Those choices are
deployment options (``channel``, ``setpoint_unit``, ``reenable_mode`` below), not upstream facts.  The hardware backend
refuses every setpoint read and write until ``setpoint_unit`` is declared, because a wrong unit would send the
controller another temperature than the one the envelope checked.  The clone states no setpoint or manual-heater
bound, so those limits are ``Limit.operator_required`` and are filled by the operator's site overlay;
``site-limits.example.json`` is an example only.

Every Fact cites a line of the clone at commit 370b8e3d94224db70ee2a1f51bd28c5d305daefe.  This package is model-authored
and unreviewed: it is checked on the fake backend only, and the loader refuses the hardware backend of a model-authored
R2 package until a human signs ``reviewed_by`` in driver.lock.json.
"""

from mhs import units
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The output-mode menu of the upstream soft-IOC device, in menu order (instruments/ls336.py:17); do_sets passes the
#: _Mode PV's new value to OUTMODE (instruments/ls336.py:62-63).
_OUTPUT_MODES = {0: "Off", 1: "Closed Loop", 2: "Zone", 3: "Open Loop"}
#: The heater-range menu of the upstream soft-IOC device, in menu order (instruments/ls336.py:18).
_HEATER_RANGES = {0: "Off", 1: "Low", 2: "Med", 3: "High"}
_MODE_CODES = {name: code for code, name in _OUTPUT_MODES.items()}
_RANGE_CODES = {name: code for code, name in _HEATER_RANGES.items()}
_SETPOINT_UNITS = ("K", "Cel", "[degF]")


class Ls336(Driver):
    device_id = "ls336"
    device_kind = "thermal.zone"
    mode = "hardware"
    #: A temperature controller that drives a heater is at least R2 (MHS/spec/04-safety.md), equal to the card floor.
    risk = "R2"
    native = "instruments.ls336:DeviceConnection"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLs336"}
    vendor = "Lake Shore Cryotronics"
    model = "Model 336 temperature controller"
    display_name = "Lake Shore 336 temperature controller (epics-device-lib ls336 DeviceConnection)"
    tags = ["lakeshore", "ls336", "temperature-controller", "cryostat", "heater", "telnet", "epics"]
    facts = [
        Fact("The README identifies instruments/ls336.py as the Lake Shore Model 336 temperature controller",
             source="vendor_doc", ref="README.md:26"),
        Fact("The README lists the ls336 driver as a Telnet (RS-232) device exposing temperature/heater inputs and "
             "setpoint/PID outputs", source="vendor_doc", ref="README.md:52"),
        Fact("The README's inheritance tree lists the repository's other device modules, among them the Rigol DP832 "
             "power supply (dp832.py) and the Zaber ASCII motor controller (zaber_motor.py)",
             source="vendor_doc", ref="README.md:11-33"),
        Fact("For each configured channel whose name does not contain _TI, the Device class creates _TI, _Heater, "
             "_Manual, _kP, _kI, _kD, _SP, _Mode and _Range PVs, the _Mode and _Range PVs as mbbOut records built "
             "from mode_list and range_list; a _TI channel gets only its temperature PV",
             source="upstream_code", ref="instruments/ls336.py:20-35"),
        Fact("Device._create_connection passes settings['ip'], settings['port'] and settings['timeout'] to "
             "DeviceConnection", source="upstream_code", ref="instruments/ls336.py:37-42"),
        Fact("do_sets passes a _Mode PV's new value to set_outmode(chan, new_value, chan, 0), the channel as first "
             "and third argument, and a _Range PV's new value to set_range(chan, new_value)",
             source="upstream_code", ref="instruments/ls336.py:62-65"),
        Fact("The output-mode menu names Off, Closed Loop, Zone and Open Loop in that order",
             source="upstream_code", ref="instruments/ls336.py:17"),
        Fact("The heater-range menu names Off, Low, Med and High in that order",
             source="upstream_code", ref="instruments/ls336.py:18"),
        Fact("do_reads sets channel i's temperature PV from temps[i] and, for a channel without _TI in its name, "
             "reads heater, PID, output mode, range, setpoint and manual output for channel i+1",
             source="upstream_code", ref="instruments/ls336.py:75-91"),
        Fact("read_temps sends KRDG? 0 and parses four comma-separated floats; the comment calls KRDG a Kelvin reading",
             source="upstream_code", ref="instruments/ls336.py:107-120"),
        Fact("The set_pid and read_pid docstrings name channel 1 or 2; set_pid sends PID <channel>,<P>,<I>,<D> and "
             "then PID?, and read_pid sends PID? without its channel argument",
             source="upstream_code", ref="instruments/ls336.py:126-147"),
        Fact("read_heater sends HTR? <channel> and read_man_heater sends MOUT? <channel>",
             source="upstream_code", ref="instruments/ls336.py:153-173"),
        Fact("The manual-heater docstrings name output percentages, and set_man_heater sends MOUT <channel>,<value> "
             "then MOUT? <channel>", source="upstream_code", ref="instruments/ls336.py:166-187"),
        Fact("set_outmode sends OUTMODE <channel>,<mode>,<in_channel>,<powerup_on> and then OUTMODE? <channel> and "
             "returns the first number of the reply; read_outmode sends OUTMODE? <channel>",
             source="upstream_code", ref="instruments/ls336.py:193-218"),
        Fact("set_range sends RANGE <channel>,<range> and reads RANGE? <channel> back",
             source="upstream_code", ref="instruments/ls336.py:220-245"),
        Fact("set_setpoint sends SETP <channel>,<value> and reads SETP? <channel> back; read_setpoint sends SETP?",
             source="upstream_code", ref="instruments/ls336.py:247-272"),
        Fact("Each method from read_temps to read_setpoint reads one line with read_until(b'\\n', timeout=2), parses "
             "it with a regex search and, on any Exception (a reply the regex does not match included), prints the "
             "error and raises OSError", source="upstream_code", ref="instruments/ls336.py:113-272"),
        Fact("TelnetConnection's constructor stores host, port and timeout and creates a TelnetSocket to host:port as "
             "self.tn; an exception from that is printed, not raised", source="upstream_code",
             ref="telnet_base.py:27-38"),
        Fact("TelnetSocket.read_until returns whatever has arrived when the timeout or EOF comes instead of raising",
             source="upstream_code", ref="telnet_socket.py:69-78"),
    ]
    safe_state = ("the configured heater output is in output mode Off, confirmed by an OUTMODE? readback of mode 0; "
                  "the stop command (OUTMODE <channel>,0,<channel>,0) also sets that output's control input to input "
                  "<channel> and its powerup enable to 0; its heater range, setpoint and manual output are kept, the "
                  "other heater output is not commanded and keeps heating if it was on, and nothing cools the sample")

    #: The output channel is a deployment choice: DeviceConnection takes it as an argument, and the soft-IOC settings
    #: choose it per device (instruments/ls336.py:20-35, 44-70).  The upstream docstrings name channel 1 or 2
    #: (instruments/ls336.py:127, 141); the default is 1.
    @property
    def _channel(self) -> int:
        raw = self.options.get("channel", 1)
        try:
            channel = int(raw)
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel option {raw!r} is not an integer") from exc
        if channel not in (1, 2):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel option {channel} is not a documented output channel (1 or 2)")
        return channel

    #: SETP uses the control input's preferred unit, which the clone never states.  The fields are published in the
    #: catalogue's Celsius and converted with the ``setpoint_unit`` option.  The hardware backend has no default: a
    #: wrong unit sends another temperature than the one the envelope checked (30 Cel becomes SETP 303.15 under K,
    #: which a controller set to Celsius would take as 303.15 Cel), so the operator declares it.  The fake keeps
    #: Kelvin, the unit of its placeholder setpoints.
    def _setpoint_unit(self) -> str:
        raw = self.options.get("setpoint_unit")
        if raw is None:
            if self.is_hardware:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "the setpoint_unit option is not set: the clone does not state the SETP unit, so "
                                   "the hardware backend needs the control input's unit (K, Cel or [degF])")
            raw = "K"
        unit = str(raw)
        if unit not in _SETPOINT_UNITS:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"setpoint_unit option {unit!r} is not one of {list(_SETPOINT_UNITS)}")
        return unit

    #: The re-enable restores a control mode, not the previous one (the safe state leaves no readable history).
    def _reenable_mode(self) -> int:
        name = str(self.options.get("reenable_mode", "Closed Loop"))
        if name not in _MODE_CODES or name == "Off":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"reenable_mode option {name!r} is not Closed Loop, Zone or Open Loop")
        return _MODE_CODES[name]

    def _cel_to_native(self, value: float) -> float:
        return float(units.convert(float(value), "Cel", self._setpoint_unit()))

    def _native_to_cel(self, value: float) -> float:
        return float(units.convert(float(value), self._setpoint_unit(), "Cel"))

    # -- reads ------------------------------------------------------------------------------------------------
    @read("temperature", unit="K",
          description="Kelvin reading at position <channel> of KRDG? 0, the one the upstream pairs with the "
                      "configured output")
    def temperature(self):
        return float(self.native.read_temps()[self._channel - 1])

    @read("temperatures", type="array", items="number", unit="K", length=4,
          description="The four Kelvin sensor readings returned by KRDG? 0")
    def temperatures(self):
        return [float(value) for value in self.native.read_temps()]

    @read("setpoint", unit="Cel",
          description="Setpoint of the configured control loop, converted from the controller's configured unit "
                      "(setpoint_unit option, required with the hardware backend)")
    def setpoint(self):
        return self._native_to_cel(self.native.read_setpoint(self._channel))

    @read("heater_output", unit="%", description="Heater output of the configured output in percent, from HTR?")
    def heater_output(self):
        return float(self.native.read_heater(self._channel))

    @read("manual_heater", unit="%",
          description="Manual heater output of the configured output in percent, from MOUT?")
    def manual_heater(self):
        return float(self.native.read_man_heater(self._channel))

    @read("pid", type="array", items="number", length=3,
          description="P, I and D gains from PID?, which the upstream read_pid sends without an output number; the "
                      "clone does not say which output's gains the controller returns")
    def pid(self):
        return [float(value) for value in self.native.read_pid(self._channel)]

    @read("output_mode", type="string",
          description="Output mode of the configured output: Off, Closed Loop, Zone or Open Loop")
    def output_mode(self):
        return self._mode_name(self.native.read_outmode(self._channel))

    @read("heater_range", type="string",
          description="Heater range of the configured output: Off, Low, Med or High")
    def heater_range(self):
        return self._range_name(self.native.read_range(self._channel))

    @staticmethod
    def _mode_name(code) -> str:
        name = _OUTPUT_MODES.get(int(code))
        if name is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"OUTMODE? reported an unknown mode code {code!r}")
        return name

    @staticmethod
    def _range_name(code) -> str:
        name = _HEATER_RANGES.get(int(code))
        if name is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"RANGE? reported an unknown range code {code!r}")
        return name

    # -- writes -----------------------------------------------------------------------------------------------
    @write("setpoint", unit="Cel",
           description="Setpoint of the configured control loop, converted to the controller's configured unit "
                       "(setpoint_unit option, required with the hardware backend)",
           limit=Limit.operator_required(
               "no text file of the clone states the SETP range; the controller's configured unit and the safe "
               "sample range differ per installation, so the operator supplies the Celsius bound in site-limits.json"))
    def set_setpoint(self, value):
        applied = self.native.set_setpoint(self._channel, self._cel_to_native(value))
        return self._native_to_cel(applied)

    @write("manual_heater", unit="%",
           description="Manual heater output of the configured output as a percentage; it only acts in the "
                       "open-loop mode of the device",
           limit=Limit.operator_required(
               "no text file of the clone states the manual-heater range; MOUT is documented only as a percentage, "
               "so the operator supplies the bound in site-limits.json"))
    def set_manual_heater(self, value):
        return float(self.native.set_man_heater(self._channel, float(value)))

    @write("heater_range", type="string", enum=list(_HEATER_RANGES.values()),
           description="Heater range of the configured output: Off, Low, Med or High",
           limit=Limit(allowed=list(_HEATER_RANGES.values()), source="upstream_code",
                       ref="instruments/ls336.py:18",
                       reason="the range menu names these four entries; do_sets passes the selected menu index to "
                              "set_range"))
    def set_heater_range(self, value):
        applied = self.native.set_range(self._channel, _RANGE_CODES[str(value)])
        return self._range_name(applied)

    # -- catalogue action -------------------------------------------------------------------------------------
    @action(cap="cap.thermal.setpoint.v1",
            description="Set the setpoint of the configured control loop; it does not wait for the zone to reach it",
            input={"target_temperature": Field(
                "number", unit="Cel",
                description="Target temperature of the configured control loop in Celsius",
                limit=Limit.operator_required(
                    "no text file of the clone states the SETP range; the controller's configured unit and the safe "
                    "sample range differ per installation, so the operator supplies the Celsius bound in "
                    "site-limits.json"))})
    def set_temperature(self, target_temperature):
        self.check_cancelled()
        self.native.set_setpoint(self._channel, self._cel_to_native(target_temperature))
        self.check_cancelled()
        setpoint = self._native_to_cel(self.native.read_setpoint(self._channel))
        actual = float(units.convert(float(self.native.read_temps()[self._channel - 1]), "K", "Cel"))
        return {"setpoint": setpoint, "actual_temperature": actual}

    # -- safety -----------------------------------------------------------------------------------------------
    @action(name="x-cap.jdmax.heater_off.v1", safe_state=True,
            description="Command the configured heater output off (OUTMODE <channel>,0,<channel>,0) and confirm "
                        "mode 0 with a fresh OUTMODE? read; it takes no input",
            output={"output_mode": Field("string",
                                         description="Output mode read back after the command; Off confirms it")})
    def heater_off(self):
        self.native.set_outmode(self._channel, _MODE_CODES["Off"], self._channel, 0)
        mode = int(self.native.read_outmode(self._channel))
        if mode != _MODE_CODES["Off"]:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               f"OUTMODE? read back {mode!r}, expected {_MODE_CODES['Off']} (Off)")
        return {"output_mode": self._mode_name(mode)}

    @action(name="x-cap.jdmax.enable_heater.v1", reenable=True,
            description="Command the configured output back to the reenable_mode option's control mode (default "
                        "Closed Loop) with OUTMODE <channel>,<mode>,<channel>,0 and confirm it with OUTMODE?; heating "
                        "resumes toward the setpoint or manual output stored in the controller; it takes no input",
            output={"output_mode": Field("string",
                                         description="Output mode read back after the command; the configured "
                                                     "reenable_mode")})
    def enable_heater(self):
        mode = self._reenable_mode()
        self.native.set_outmode(self._channel, mode, self._channel, 0)
        applied = int(self.native.read_outmode(self._channel))
        if applied != mode:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"OUTMODE? read back {applied!r}, expected {mode} ({_OUTPUT_MODES[mode]})")
        return {"output_mode": self._mode_name(applied)}

    @estop(native="set_outmode")
    def stop(self):
        """The native stop: OUTMODE <channel>,0,<channel>,0, mode 0 being the Off menu entry.

        The upstream set_outmode also sends OUTMODE? and waits up to 2 s for the reply, raising OSError when none
        matches, and returns the mode it parses (instruments/ls336.py:193-205).  Any mode but Off fails the native
        stop; the safe-state action heater_off, which the runtime runs after it either way, sends the command again
        and confirms mode 0 with a fresh OUTMODE? read.
        """
        mode = int(self.native.set_outmode(self._channel, _MODE_CODES["Off"], self._channel, 0))
        if mode != _MODE_CODES["Off"]:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               f"OUTMODE? after the stop read back {mode!r}, expected {_MODE_CODES['Off']} (Off)")
