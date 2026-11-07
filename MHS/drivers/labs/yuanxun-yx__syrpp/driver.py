"""OpenMHS driver for gh.yuanxun-yx/syrpp: a New Era syringe pump over its RS232 command set.

A direct Driver over the upstream device class ``syrpp.pump_conn:SyrPump``.  The upstream builds every wire
line from the decimal pump address, the command code and its arguments concatenated with no separator and
terminated by CR LF (``src/syrpp/pump_conn.py:628-650``); a SerialDriver command table cannot reproduce that
per-address framing without changing the syntax, so this package uses the upstream object directly and a
``native.py`` hardware factory.

* reads: status prompt, firmware version, syringe diameter (DIA), phase (PHN), phase function (FUN), pumping
  rate value (RAT), direction (DIR), alarm buzzer (AL), power-fail flag (PF), key beep (BP), buzzer (BUZ),
  the configured phase volume (VOL) and the dispensed infusion/withdrawal volumes (DIS);
* writes: syringe diameter, phase, phase function, pumping rate value, direction and the four boolean settings.
  The clone states no numeric diameter or pumping-rate range, so those two writes are
  ``Limit.operator_required``: every such write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies
  its unit's range (``site-limits.example.json`` shows the overlay).  The phase range 1-41 is the upstream's
  own ``DATA_RANGE['phase']`` and is checked by ``set_phase`` before it sends PHN;
* actions: start the pump program (RUN) and stop it (STP).  The stop action is the safe-state action and the
  native stop; the device can dispense liquid, so the driver is R2 even though the card's floor is R1.

Only phase functions that take no data argument are writable; the functions in PHASE_FUN_DATA (jump, loop,
pause, if, event, output) need a number whose range differs per function and whose bound the clone does not
state, so this driver does not expose them.  The pump address is the ``address`` backend option (default 0,
the address the upstream examples use, ``test/config.py:4``).

Every Fact and Limit cites a line of the clone at the pinned commit
(ae784882903cd9d1b72162835902dca0074b2e14).  This package is model-authored and unreviewed: it is checked on
the fake backend only, and no hardware was attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: Phase-function names whose code in PHASE_FUNCTION takes no data argument; the others are in PHASE_FUN_DATA.
NO_DATA_FUNCTIONS = ["rate", "increment", "decrement", "stop", "loop start", "loop end", "event reset", "beep"]

#: Direction names in PUMP_DIRECTION (src/syrpp/pump_conn.py:70-74).
DIRECTIONS = ["infuse", "withdraw", "reverse"]


class SyrPumpDevice(Driver):
    device_id = "syrpump"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "syrpp.pump_conn:SyrPump"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSyrpp"}
    vendor, model = "New Era Instruments", "SyringeONE NE-1000"
    display_name = "New Era SyringeONE NE-1000 syringe pump (syrpp.SyrPump)"
    tags = ["syringe-pump", "serial", "infuse", "withdraw", "pump"]
    facts = [
        Fact("A command is the pump address, the command code and its arguments concatenated and terminated with "
             "CR LF", source="upstream_code", ref="src/syrpp/pump_conn.py:628-650"),
        Fact("The command table maps DIA, PHN, FUN, RAT, VOL, DIR, DIS, CLD, SAF, AL, PF, TRG, BP, OUT, IN, BUZ, "
             "VER, RUN and STP to the pump operations", source="upstream_code",
             ref="src/syrpp/pump_conn.py:14-34"),
        Fact("DATA_RANGE gives phase 1-41, count 1-99, TTL level 0-1, timeout 0-255 and address 0-99",
             source="upstream_code", ref="src/syrpp/pump_conn.py:155-162"),
        Fact("set_phase rejects a phase outside DATA_RANGE['phase'] before sending PHN", source="upstream_code",
             ref="src/syrpp/pump_conn.py:369-375"),
        Fact("get_diameter sends DIA and returns the reply as a float; set_diameter sends DIA with the truncated "
             "number", source="upstream_code", ref="src/syrpp/pump_conn.py:345-350"),
        Fact("PHASE_FUNCTION maps RAT/INC/DEC to rate/increment/decrement, STP to stop, LPS/LPE to loop start and "
             "loop end, and EVR/BEP to event reset and beep, among others", source="upstream_code",
             ref="src/syrpp/pump_conn.py:117-134"),
        Fact("PHASE_FUN_DATA lists the functions that carry data: jump phase, loop count, pause number, if phase, "
             "event phase and output TTL", source="upstream_code", ref="src/syrpp/pump_conn.py:136-143"),
        Fact("get_function sends FUN and returns the function name; set_function sends FUN with the function code "
             "and optional data", source="upstream_code", ref="src/syrpp/pump_conn.py:377-416"),
        Fact("VOLUME_UNITS maps U to microliter aliases and M to milliliter aliases; TIME_UNITS maps M to minute "
             "aliases and H to hour aliases", source="upstream_code", ref="src/syrpp/pump_conn.py:145-153"),
        Fact("get_rate sends RAT and splits the reply into a value and the trailing volume and time units; when "
             "they are not known units it returns only the value", source="upstream_code",
             ref="src/syrpp/pump_conn.py:418-429"),
        Fact("set_rate sends RAT with the value and, when both are given, the volume and time unit codes",
             source="upstream_code", ref="src/syrpp/pump_conn.py:431-440"),
        Fact("PUMP_DIRECTION maps INF to infuse, WDR to withdraw and REV to reverse", source="upstream_code",
             ref="src/syrpp/pump_conn.py:70-74"),
        Fact("get_direction and set_direction translate through PUMP_DIRECTION", source="upstream_code",
             ref="src/syrpp/pump_conn.py:442-448"),
        Fact("get_volume sends VOL and splits the trailing two characters into a volume value and a unit",
             source="upstream_code", ref="src/syrpp/pump_conn.py:352-360"),
        Fact("get_volume_dispensed sends DIS and returns the infused and withdrawn volumes with one unit",
             source="upstream_code", ref="src/syrpp/pump_conn.py:579-591"),
        Fact("get_status sends an address-only query and maps the prompt character to a status text",
             source="upstream_code", ref="src/syrpp/pump_conn.py:601-606"),
        Fact("start_program sends RUN and stop_program sends STP", source="upstream_code",
             ref="src/syrpp/pump_conn.py:573-577"),
        Fact("get_alarm and set_alarm use AL; get_power_fail and set_power_fail use PF", source="upstream_code",
             ref="src/syrpp/pump_conn.py:468-489"),
        Fact("get_key_beep and set_key_beep use BP; get_buzzer and set_buzzer use BUZ", source="upstream_code",
             ref="src/syrpp/pump_conn.py:533-571"),
        Fact("The pump address and baud rate are set on the pump manually before use", source="vendor_doc",
             ref="README.md:17"),
        Fact("The package is tested on the New Era SyringeONE NE-1000 (distributed by Braintree as BS-9000)",
             source="vendor_doc", ref="README.md:46"),
        Fact("The upstream examples address the pump at 0", source="upstream_code", ref="test/config.py:4"),
    ]
    safe_state = "pumping program stopped (STP), motor stopped"

    def _address(self) -> int:
        """The configured pump address; the upstream examples use 0 (test/config.py:4)."""
        raw = self.options.get("address", 0)
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the backend option address must be an integer, got {raw!r}")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("status", type="string", description="Prompt text the pump reports for its current state")
    def status(self):
        return self.native.get_status(self._address())

    @read("firmware_version", type="string", description="Firmware version reported by VER")
    def firmware_version(self):
        return self.native.get_firmware_version(self._address())

    @read("diameter", unit="1", description="Syringe diameter setting reported by DIA, as the pump reports it")
    def diameter(self):
        return float(self.native.get_diameter(self._address()))

    @read("phase", type="integer", unit="1", description="Current pumping program phase reported by PHN")
    def phase(self):
        return int(self.native.get_phase(self._address()))

    @read("phase_function", type="string", description="Function of the current phase reported by FUN")
    def phase_function(self):
        return self.native.get_function(self._address())["function"]

    @read("pumping_rate", unit="1", description="Pumping rate value reported by RAT, in the pump's current rate units")
    def pumping_rate(self):
        return float(self.native.get_rate(self._address())["value"])

    @read("direction", type="string", description="Pumping direction named by DIR")
    def direction(self):
        return self.native.get_direction(self._address())

    @read("alarm", type="boolean", description="True when the alarm buzzer mode is enabled (AL)")
    def alarm(self):
        return bool(self.native.get_alarm(self._address()))

    @read("power_fail", type="boolean", description="True when the power-fail flag is enabled (PF)")
    def power_fail(self):
        return bool(self.native.get_power_fail(self._address()))

    @read("key_beep", type="boolean", description="True when the key beep is enabled (BP)")
    def key_beep(self):
        return bool(self.native.get_key_beep(self._address()))

    @read("buzzer", type="boolean", description="True when the buzzer is on or beeping (BUZ)")
    def buzzer(self):
        return bool(self.native.get_buzzer(self._address()))

    @read("volume", type="object",
          properties={"volume": Field("number", required=False,
                                      description="Phase volume value reported by VOL"),
                      "unit": Field("string", required=False,
                                    description="Volume unit reported by VOL (a VOLUME_UNITS alias)")},
          description="Volume configured for the current phase, as VOL reports it")
    def volume(self):
        return self.native.get_volume(self._address())

    @read("volume_dispensed", type="object",
          properties={"infusion": Field("number", required=False,
                                        description="Volume infused so far, in the reported unit"),
                      "withdraw": Field("number", required=False,
                                        description="Volume withdrawn so far, in the reported unit"),
                      "unit": Field("string", required=False,
                                    description="Volume unit reported by DIS (a VOLUME_UNITS alias)")},
          description="Dispensed infusion and withdrawal volumes as DIS reports them")
    def volume_dispensed(self):
        return self.native.get_volume_dispensed(self._address())

    # -- writes --------------------------------------------------------------------------------------------------
    @write("diameter", unit="1", description="Syringe diameter setting written with DIA, as the pump reports it",
           limit=Limit.operator_required(
               "no text file of the clone states a syringe diameter range; the clone only truncates the number to "
               "four digits (src/syrpp/pump_conn.py:678-696). The installed syringe sets the bound, so the site "
               "supplies the accepted range."))
    def set_diameter(self, value):
        self.native.set_diameter(self._address(), value)

    @write("phase", type="integer", unit="1", description="Pumping program phase written with PHN",
           limit=Limit(min=1, max=41, source="upstream_code", ref="src/syrpp/pump_conn.py:157",
                       reason="DATA_RANGE['phase'] is (1, 41), checked by set_phase before PHN is sent"))
    def set_phase(self, value):
        self.native.set_phase(self._address(), int(value))

    @write("phase_function", type="string", description="Phase function written with FUN, without a data argument",
           limit=Limit(allowed=NO_DATA_FUNCTIONS, source="upstream_code",
                       ref="src/syrpp/pump_conn.py:117-143",
                       reason="only PHASE_FUNCTION names absent from PHASE_FUN_DATA take no data argument"))
    def set_phase_function(self, value):
        self.native.set_function(self._address(), value)

    @write("pumping_rate", unit="1", description="Pumping rate value written with RAT, in the pump's current rate units",
           limit=Limit.operator_required(
               "no text file of the clone states a numeric pumping rate range; the syringe, the motor and the "
               "process set it. The site supplies the accepted range for its pump and tubing."))
    def set_pumping_rate(self, value):
        self.native.set_rate(self._address(), value)

    @write("direction", type="string", description="Pumping direction written with DIR",
           limit=Limit(allowed=DIRECTIONS, source="upstream_code", ref="src/syrpp/pump_conn.py:70-74",
                       reason="PUMP_DIRECTION lists infuse, withdraw and reverse"))
    def set_direction(self, value):
        self.native.set_direction(self._address(), value)

    @write("alarm", type="boolean", description="Alarm buzzer mode written with AL")
    def set_alarm(self, value):
        self.native.set_alarm(self._address(), bool(value))

    @write("power_fail", type="boolean", description="Power-fail flag written with PF")
    def set_power_fail(self, value):
        self.native.set_power_fail(self._address(), bool(value))

    @write("key_beep", type="boolean", description="Key beep setting written with BP")
    def set_key_beep(self, value):
        self.native.set_key_beep(self._address(), bool(value))

    @write("buzzer", type="boolean", description="Buzzer setting written with BUZ")
    def set_buzzer(self, value):
        self.native.set_buzzer(self._address(), bool(value))

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.yuanxun-yx.start_program.v1",
            description="Start the configured pumping program (RUN) and report the pump prompt afterwards",
            output={"status": Field("string", description="Prompt text the pump reports after RUN")})
    def start_program(self):
        self.native.start_program(self._address())
        self.check_cancelled()
        return {"status": self.native.get_status(self._address())}

    @action(name="x-cap.yuanxun-yx.stop_program.v1", safe_state=True,
            description="Stop the pumping program (STP); the native stop and the safe-state action",
            output={"status": Field("string", description="Prompt text the pump reports after STP")})
    def stop_program(self):
        self.native.stop_program(self._address())
        return {"status": self.native.get_status(self._address())}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends STP."""
        self.native.stop_program(self._address())
