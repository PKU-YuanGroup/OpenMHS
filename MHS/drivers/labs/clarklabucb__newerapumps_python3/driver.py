"""OpenMHS driver for gh.clarklabucb/newerapumps_python3: a New Era NE-500 syringe pump over its serial chain.

DEVIATION FROM THE CARD (family-config / SerialDriver): the upstream builds every wire command from an address and
a token (``<n>DIRINF``, ``<n>RAT<value>UH``, ``<n>DIA<mm>``, ``<n>STP``, ``<n>RAT0UH``) in new_era3.py; it never
writes a literal command line.  A SerialDriver command table cannot reproduce those bytes and gate G7 would not find
their first token in the clone, so this is a direct Driver over the upstream class named by the card,
``pump_control3:PumpControl``.  That class is the Qt GUI; its device interface is the pyserial handle it stores as
``self.ser`` (pump_control3.py:23), and the protocol lives in the module functions of new_era3.py.  The driver uses
only that handle through ``self.native.ser()``: the hardware backend (native.py) returns a transport holder with the
same serial settings, and the fake backend (fake.py) stands in for the handle.  The GUI itself is never imported or
run.

* reads: the signed flow-rate set point (uL/hour) and the syringe diameter (mm);
* writes: flow rate and diameter.  No text file of the clone states a range for either command, so both are
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies its range.
  The four BD syringe sizes in the GUI are a menu, not a device bound, and the README's 10,000 uL/hour prime rate is
  not a maximum;
* actions: start the pump at the configured rate and stop it with the upstream per-pump stop (STP, then RAT0UH);
* the native stop is the broadcast ``*STP`` of new_era3.stop_all: the runtime latches first, then sends it.  The
  safe-state action stops this one pump and zeroes its rate.

The pump moves liquid, so the device is R2 (MHS/spec/04-safety.md).  The package is model-authored and unreviewed,
and its hardware backend is refused by the loader until a human sets ``reviewed_by`` in driver.lock.json.  Every
Fact cites a line of the clone at commit b8e3d0214ded43734ad22fa378b5bd408010f109; the package is checked on the
fake backend only and no instrument was tried.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

PROTOCOL = "new_era3.py"


class NewEraPump(Driver):
    device_id = "newera-ne500"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "pump_control3:PumpControl"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNewEraPump"}
    vendor, model = "New Era Pump Systems", "NE-500 OEM one-channel syringe pump"
    display_name = "New Era NE-500 syringe pump"
    tags = ["syringe pump", "new era", "ne-500", "serial", "fluid"]
    facts = [
        Fact("The upstream programs control New Era NE-500 OEM one-channel syringe pumps with 1 mL, 3 mL, 5 mL "
             "or 10 mL Becton Dickinson syringes", source="vendor_doc", ref="README.md:27"),
        Fact("The pump GUI opens the serial chain at 19200 baud with a 0.2 s read timeout",
             source="upstream_code", ref="pump_control3.py:23"),
        Fact("The GUI offers 1, 3, 5 and 10 mL BD syringes with inner diameters 4.699, 8.585, 11.99 and 14.50 mm",
             source="upstream_code", ref="pump_control3.py:9-12"),
        Fact("Each pump on a chain is named a unique single digit integer 0-9", source="vendor_doc",
             ref="README.md:93"),
        Fact("A chain holds at most 10 pumps, addressed 0-9", source="vendor_doc", ref="README.md:102"),
        Fact("Flow rates are entered and displayed in uL/hour", source="vendor_doc", ref="README.md:119"),
        Fact("The Prime button sets the flow rate to 10,000 uL/hr and starts the pump", source="vendor_doc",
             ref="README.md:122"),
        Fact("The GUI sends the direction (INF or WDR) before the rate, then writes UH below 5000 and MH at 5000 "
             "or above by dividing the rate by 1000", source="upstream_code", ref=f"{PROTOCOL}:47-61"),
        Fact("A rate query is sent twice: the fourth byte of the first reply is W for a withdraw, and the second "
             "reply carries the value and the UH or MH unit", source="upstream_code", ref=f"{PROTOCOL}:68-97"),
        Fact("The syringe diameter is set with <n>DIA<mm> and read with <n>DIA", source="upstream_code",
             ref=f"{PROTOCOL}:111-124"),
        Fact("The broadcast *STP stops all pumps; the per-pump stop sends <n>STP and then <n>RAT0UH",
             source="upstream_code", ref=f"{PROTOCOL}:26-41"),
        Fact("The broadcast *RUN starts all pumps", source="upstream_code", ref=f"{PROTOCOL}:20-24"),
        Fact("Prime starts one pump with <n>RAT10.0MH and then <n>RUN", source="upstream_code",
             ref=f"{PROTOCOL}:126-135"),
    ]
    safe_state = "the pump is stopped with <n>STP and its rate is zeroed with <n>RAT0UH"

    @read("flow_rate", unit="uL/h",
          description="Signed flow-rate set point of the pump: positive infuses, negative withdraws")
    def flow_rate(self):
        link = self._link()
        return self._read_rate(link)

    @write("flow_rate", unit="uL/h",
           description="Signed flow-rate set point in uL/hour; the pump keeps its current run or stop state",
           limit=Limit.operator_required(
               "no text file of the clone states the flow-rate range of an NE-500; the README gives the 10,000 "
               "uL/hour prime rate, which is not a maximum, so the site supplies the range of its pump, syringe "
               "and tubing"))
    def set_flow_rate(self, value):
        link = self._link()
        address = self._address(link)
        rate = float(value)
        direction = "WDR" if rate < 0 else "INF"
        self._exchange(link, f"{address}DIR{direction}\r")
        rate = abs(rate)
        if rate < 5000:
            command = f"{address}RAT{str(rate)[:5]}UH"
        else:
            command = f"{address}RAT{str(rate / 1000.0)[:5]}MH"
        self._exchange(link, command + "\r")
        return self._read_rate(link)

    @read("diameter", unit="mm",
          description="Inner diameter of the mounted syringe used for the plunger-speed conversion")
    def diameter(self):
        link = self._link()
        return self._read_diameter(link)

    @write("diameter", unit="mm",
           description="Inner diameter of the mounted syringe in mm; it changes the plunger speed for a flow rate",
           limit=Limit.operator_required(
               "no text file of the clone states a syringe-diameter range; the four BD diameters in the GUI are a "
               "menu, not a device bound, so the site supplies the range of the syringes it mounts"))
    def set_diameter(self, value):
        link = self._link()
        address = self._address(link)
        self._exchange(link, f"{address}DIA{str(float(value))}\r")
        return self._read_diameter(link)

    @action(name="x-cap.clarklabucb.start_pump.v1", risk="R2",
            description="Start the pump at the flow rate stored on the device (<n>RUN)",
            output={"flow_rate": Field("number", unit="uL/h",
                                       description="Signed flow rate read back after the run command")})
    def start_pump(self):
        link = self._link()
        address = self._address(link)
        self._exchange(link, f"{address}RUN\r")
        return {"flow_rate": self._read_rate(link)}

    @action(name="x-cap.clarklabucb.stop_pump.v1", safe_state=True, risk="R2",
            description="Stop this pump and zero its rate (<n>STP, then <n>RAT0UH); it takes no input",
            output={"stopped": Field("boolean",
                                     description="True once the stop and zero-rate commands were accepted")})
    def stop_pump(self):
        link = self._link()
        address = self._address(link)
        self._exchange(link, f"{address}STP\r")
        self._exchange(link, f"{address}RAT0UH\r")
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the broadcast *STP of new_era3.stop_all (new_era3.py:26-30)."""
        link = self._link()
        self._exchange(link, "*STP\r")

    # -- serial protocol ------------------------------------------------------------------------------------------
    def _link(self):
        link = self.native.ser()
        if link is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the native backend returned no serial handle")
        return link

    @staticmethod
    def _address(link):
        address = getattr(link, "address", None)
        if not isinstance(address, int) or isinstance(address, bool) or not 0 <= address <= 9:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the serial handle has no pump address in 0-9 (got {address!r})")
        return address

    @staticmethod
    def _exchange(link, line):
        link.write(line.encode("ascii"))
        reply = link.readline()
        if not isinstance(reply, (bytes, bytearray)):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the pump returned {type(reply).__name__}, not bytes")
        if b"?" in reply:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the pump did not understand {line.strip()!r}")
        return bytes(reply)

    def _read_rate(self, link):
        address = self._address(link)
        first = self._exchange(link, f"{address}RAT\r")
        if len(first) < 4:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the rate reply {first!r} is too short for its direction byte")
        sign = -1.0 if first[3:4] == b"W" else 1.0
        reply = self._exchange(link, f"{address}RAT\r")
        if len(reply) < 7:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the rate reply {reply!r} is too short for value and unit")
        units = reply[-3:-1]
        try:
            if units == b"MH":
                return sign * float(reply[4:-3]) * 1000.0
            if units == b"UH":
                return sign * float(reply[4:-3])
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the rate reply {reply!r} is not a number") from exc
        raise DriverFailed("MHS.DEVICE.FAULTED", f"the rate reply {reply!r} has an unknown unit")

    def _read_diameter(self, link):
        address = self._address(link)
        reply = self._exchange(link, f"{address}DIA\r")
        if len(reply) < 6:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the diameter reply {reply!r} is too short")
        try:
            return float(reply[4:-1])
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the diameter reply {reply!r} is not a number") from exc
