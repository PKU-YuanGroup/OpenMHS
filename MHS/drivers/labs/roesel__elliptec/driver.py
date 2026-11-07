"""OpenMHS driver for gh.roesel/elliptec: one Thorlabs Elliptec slider driven as an optical shutter.

A direct Driver (decorated methods) over the upstream class elliptec.shutter:Shutter (src/elliptec/shutter.py:10), the
class the library documents for a shutter (README.md:42-54) and the class the README lists for the Dual-Position
Slider (ELL6), "useful as a shutter" (README.md:141).  The upstream object is a motor that asks the device for its
info when it is created (src/elliptec/motor.py:31-43) and whose Controller composes every command from a bus address,
the instruction bytes and an optional 32-bit argument (src/elliptec/controller.py:115-138); a command table cannot
reproduce those bytes, so the driver calls the object and native.py builds it.

* reads: the slot the slider is in (Shutter.get_slot, src/elliptec/shutter.py:20-24) and the open/closed state the
  class derives from that slot (Shutter.is_open / Shutter.is_closed, src/elliptec/shutter.py:62-68);
* ``cap.optics.shutter.v1``: open or close the shutter with Shutter.open / Shutter.close
  (src/elliptec/shutter.py:50-60) and report the state read back from the device;
* ``x-cap.roesel.home_shutter.v1``: the homing move Shutter.home (src/elliptec/motor.py:93-98) that the README runs
  before use (README.md:48-49);
* ``x-cap.roesel.move_to_slot.v1``: Shutter.set_slot, which accepts slot 1 or slot 2 only and returns None for any
  other value (src/elliptec/shutter.py:26-38), so its input carries that bound as a sourced Limit;
* ``x-cap.roesel.close_shutter.v1``: the safe-state action, and the e-stop calls the same native close, because
  closing the shutter blocks the optical path.  The clone documents no independent hardware e-stop for the device.

Whether the mount was created inverted=True (src/elliptec/shutter.py:13-15, 50-60) is a construction option the
driver does not know, so the driver reports the raw slot and the open/closed state the object computes and does not
name either slot "the safe one" beyond what Shutter.close does.  Shutter.jog (src/elliptec/shutter.py:40-47), the
relative and absolute moves of Shutter.move (src/elliptec/motor.py:62-78) and the jog step, home offset and frequency
settings of the motor are not exposed.

Every Fact cites a line of the clone at the pinned commit (5f86ca595f80397bca280347830339c832a7b0bc).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on a device.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read


def _reported_slot(native):
    """The slot Shutter.get_slot() reports, or a DriverFailed when the device did not answer with a position."""
    value = native.get_slot()
    if value is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", "Shutter.get_slot() reported no slot")
    return int(value)


class ElliptecShutter(Driver):
    device_id = "elliptec-shutter"
    device_kind = "optics.shutter"
    mode = "hardware"
    risk = "R2"
    native = "elliptec.shutter:Shutter"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeShutter"}
    vendor, model = "Thorlabs", "Elliptec Dual-Position Slider (ELL6)"
    display_name = "Thorlabs Elliptec shutter (elliptec.Shutter)"
    tags = ["shutter", "beam-block", "optical-path", "elliptec", "thorlabs", "slider"]
    facts = [
        Fact("Shutter.get_slot() asks the motor for its position and converts the pulse position to a slot number",
             source="upstream_code", ref="src/elliptec/shutter.py:20-24"),
        Fact("Shutter.set_slot(1) moves the slider backward and set_slot(2) moves it forward; any other slot value "
             "returns None without a move", source="upstream_code", ref="src/elliptec/shutter.py:26-38"),
        Fact("Shutter.open() selects slot 2 and Shutter.close() selects slot 1 when the shutter was not created "
             "inverted; inverted=True swaps the two", source="upstream_code", ref="src/elliptec/shutter.py:50-60"),
        Fact("Shutter.is_open() and Shutter.is_closed() compare the current slot with 2 and 1, swapped when the "
             "shutter was created inverted", source="upstream_code", ref="src/elliptec/shutter.py:62-68"),
        Fact("pos_to_slot computes the slot as position / (range / (slots - 1)) + 1 from the slot count the device "
             "database holds for the motor type", source="upstream_code", ref="src/elliptec/shutter.py:82-87"),
        Fact("The device database lists ELL6 as a Dual-Position Slider with 2 slots at positions 0 and 31",
             source="upstream_code", ref="src/elliptec/devices.py:5-12"),
        Fact("Shutter.jog(direction) accepts only 'forward' and 'backward'", source="upstream_code",
             ref="src/elliptec/shutter.py:40-47"),
        Fact("Motor.home() moves the motor with the clockwise or anticlockwise homing command",
             source="upstream_code", ref="src/elliptec/motor.py:93-98"),
        Fact("The movement instruction table maps 'home_clockwise' to ho0, 'home_anticlockwise' to ho1, 'forward' to "
             "fw, 'backward' to bw, 'absolute' to ma and 'relative' to mr", source="upstream_code",
             ref="src/elliptec/cmd.py:20-27"),
        Fact("Motor.load_motor_info() queries the 'info' response when the object is created and stores the motor "
             "range, pulses per revolution, serial number and motor type", source="upstream_code",
             ref="src/elliptec/motor.py:31-43"),
        Fact("The controller composes a command from the bus address, the instruction bytes and an optional signed "
             "32-bit big-endian hex argument", source="upstream_code", ref="src/elliptec/controller.py:115-138"),
        Fact("The README homes the shutter before use and opens and closes it with open() and close()",
             source="vendor_doc", ref="README.md:48-53"),
        Fact("The README lists the Dual-Position Slider (ELL6) as useful as a shutter", source="vendor_doc",
             ref="README.md:141"),
    ]
    safe_state = "shutter closed, the optical path blocked (Shutter.close)"

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("is_open", type="boolean", description="True while the slider is in its open slot")
    def is_open(self):
        return bool(self.native.is_open())

    @read("is_closed", type="boolean", description="True while the slider is in its closed slot")
    def is_closed(self):
        return bool(self.native.is_closed())

    @read("slot", type="integer", unit="1",
          description="Slot the slider reports: 1 is the closed slot and 2 the open slot of a non-inverted shutter")
    def slot(self):
        value = self.native.get_slot()
        return int(value) if value is not None else None

    # -- the shutter action ----------------------------------------------------------------------------------------
    @action(cap="cap.optics.shutter.v1",
            description="Open or close the optical shutter by moving the slider to its open or closed slot and "
                        "report the state the device reads back",
            input={"state": Field(description="Wanted shutter state: 'open' moves the slider to slot 2, 'closed' "
                                              "moves it to slot 1 of a non-inverted shutter")})
    def set_state(self, state):
        if state == "open":
            self.native.open()
        else:
            self.native.close()
        return {"state": "open" if self.native.is_open() else "closed"}

    @action(name="x-cap.roesel.home_shutter.v1",
            description="Home the shutter slider (Shutter.home) so that its slot positions are referenced; the "
                        "device drives to its home position",
            output={"slot": Field("integer", unit="1",
                                  description="Slot the slider reports after the homing move")})
    def home_shutter(self):
        self.native.home()
        return {"slot": _reported_slot(self.native)}

    @action(name="x-cap.roesel.move_to_slot.v1",
            description="Move the slider to a slot with Shutter.set_slot: slot 1 or slot 2 of a non-inverted shutter",
            input={"slot": Field("integer", unit="1",
                                 description="Slot to move to: 1 is the closed slot and 2 the open slot of a "
                                             "non-inverted shutter",
                                 limit=Limit(min=1, max=2, source="upstream_code",
                                             ref="src/elliptec/shutter.py:26-38"))},
            output={"slot": Field("integer", unit="1",
                                  description="Slot the slider reports after the move")})
    def move_to_slot(self, slot):
        self.native.set_slot(int(slot))
        return {"slot": _reported_slot(self.native)}

    @action(name="x-cap.roesel.close_shutter.v1", safe_state=True,
            description="Close the shutter (the native Shutter.close, the safe state of the optical path); it takes "
                        "no input",
            output={"state": Field("string", enum=["open", "closed"],
                                   description="The shutter state after the close")})
    def close_shutter(self):
        self.native.close()
        return {"state": "closed" if self.native.is_closed() else "open"}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop: the runtime latches first, then Shutter.close() blocks the beam."""
        self.native.close()

    def teardown(self):
        self.native.close_connection()
