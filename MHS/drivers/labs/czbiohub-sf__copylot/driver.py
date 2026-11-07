"""OpenMHS driver for gh.czbiohub-sf/copylot: a Vortran Stradus laser over its serial command protocol.

A direct Driver (decorated methods) over the upstream class
``copylot.hardware.lasers.vortran.vortran:VortranLaser``.  The upstream wrapper owns a ``serial.Serial`` on a COM
port and builds every command as ``CMD`` or ``CMD=value`` plus a carriage return (vortran.py:173-192); the reply is
parsed as the command name, ``=`` and the values separated by ``, `` (vortran.py:225-228).  A native.py factory opens
the port and returns that class, so the driver translates only.

* reads: the emission state, the power set point, the maximum power the head reports, the 5 second emission delay,
  the pulse mode, the fault code and the fault description;
* writes: the power set point, the emission delay and the pulse mode.  No text of the clone states a power range and
  the maximum power is a property of the head (``?MAXP``), so the power set point is ``Limit.operator_required``: the
  site states its operating range and until then every power write is refused ``MHS.SAFETY.LIMITS_UNSET``;
* actions: switch the emission on and off.  The off action is the safe state and puts the head in it without
  waiting for the running action;
* the e-stop is the upstream ``turn_off`` alias (``LE=0``): the emission goes off.

DEVIATION FROM THE CARD: the card reads this repository as a family-config SerialDriver over text commands.  The
upstream laser builds every command from parts (``cmd + '=' + str(value)``, vortran.py:189-192), so a serial command
table cannot reproduce the wire lines (a table would send ``LE 1``, the device receives ``LE=1``).  This package is
therefore a direct Driver over the upstream class with a native.py factory, as driver-authoring.md "Choosing the
shape" prescribes.  Commands and the fake are checked on the fake backend only.

Every Fact cites a line of the clone at the pinned commit (eac4fdbf6ee49130d25764a486acb35a48d999db).  This package
is model-authored and unreviewed: it was never run against a laser (RESULT.json notes).
"""

from typing import Any

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

VORTRAN = "copylot/hardware/lasers/vortran/vortran.py"


def _flag(value: Any) -> bool:
    """The protocol answers a flag query with 1 (on) or 0 (off) (vortran.py:326-340)."""
    return str(value).strip() in ("1", "ON", "TRUE")


class VortranStradus(Driver):
    device_id = "vortran"
    device_kind = "optics.laser"
    mode = "hardware"
    #: R2, above the card's floor: a laser above class 1 is R2 (MHS/spec/04-safety.md), and a class 3B or 4 head is R3.  The model review raised it; the hardware backend
    #: of this model-written package stays refused until a human signs reviewed_by.
    risk = "R2"
    native = "copylot.hardware.lasers.vortran.vortran:VortranLaser"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeVortranLaser"}
    vendor, model = "Vortran", "Stradus laser"
    display_name = "Vortran Stradus laser (copylot VortranLaser)"
    tags = ["laser", "vortran", "stradus", "emission", "serial"]
    facts = [
        Fact("The wrapper drives a Vortran Stradus laser over RS-232/COM", source="upstream_code",
             ref=f"{VORTRAN}:1-9"),
        Fact("Every command must terminate with a carriage return '\\r' or 0x0D to be processed",
             source="upstream_code", ref=f"{VORTRAN}:173-174"),
        Fact("A command with a value is sent as 'CMD=value' and a command without one as 'CMD', both plus the "
             "carriage return", source="upstream_code", ref=f"{VORTRAN}:187-192"),
        Fact("A reply is parsed as the command name, '=', and the values separated by ', '", source="upstream_code",
             ref=f"{VORTRAN}:225-228"),
        Fact("All replies to commands are in upper case", source="upstream_code", ref=f"{VORTRAN}:217"),
        Fact("The command vocabulary is the four lists GLOBAL_CMD, GLOBAL_QUERY, LASER_CMD and LASER_QUERY",
             source="upstream_code", ref=f"{VORTRAN}:20-48"),
        Fact("Emission is switched with LE: 1 = on, 0 = off; the setter sends 'LE=<value>'",
             source="upstream_code", ref=f"{VORTRAN}:325-340"),
        Fact("turn_on and turn_off are aliases that set the emission toggle to 1 and 0", source="upstream_code",
             ref=f"{VORTRAN}:342-356"),
        Fact("The emission delay is a 5 second delay toggled with DELAY: 1 = on, 0 = off", source="upstream_code",
             ref=f"{VORTRAN}:276-291"),
        Fact("Laser power is set with LP and read with ?LP; it requires pulse mode to be off", source="upstream_code",
             ref=f"{VORTRAN}:358-379"),
        Fact("The power setter clamps the requested value to the maximum power read from the head",
             source="upstream_code", ref=f"{VORTRAN}:373-377"),
        Fact("Maximum laser power is queried with ?MAXP", source="upstream_code", ref=f"{VORTRAN}:413-419"),
        Fact("Pulse mode is toggled with PUL: 1 = on", source="upstream_code", ref=f"{VORTRAN}:398-411"),
        Fact("The status query returns a fault code (?FC) and a fault description (?FD)", source="upstream_code",
             ref=f"{VORTRAN}:425-434"),
        Fact("The wrapper identifies the head with ?LI: the serial number and the head's data fields",
             source="upstream_code", ref=f"{VORTRAN}:240-251"),
        Fact("The wrapper opens the port with a default baud rate of 19200", source="upstream_code",
             ref=f"{VORTRAN}:50"),
    ]
    safe_state = "laser emission off (turn_off sets the emission toggle to 0, LE=0)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("emission", type="boolean", description="True while the laser emission is on (LE=1)")
    def emission(self) -> bool:
        return _flag(self.native.toggle_emission)

    @read("power", unit="1",
          description="Power set point of the head in the unit the head uses; no text of the clone names that unit")
    def power(self) -> float:
        return float(self.native.laser_power)

    @read("maximum_power", unit="1",
          description="Maximum power the head reports (?MAXP), in the unit the head uses")
    def maximum_power(self) -> float:
        return float(self.native.maximum_power)

    @read("emission_delay", type="boolean",
          description="True while the 5 second laser emission delay is on (DELAY=1)")
    def emission_delay(self) -> bool:
        return _flag(self.native.emission_delay)

    @read("pulse_mode", type="boolean", description="True while pulse mode is on (PUL=1)")
    def pulse_mode(self) -> bool:
        return _flag(self.native.pulse_mode)

    @read("fault_code", type="integer", description="Fault code of the laser status (?FC); 0 is no fault")
    def fault_code(self) -> int:
        return int(self.native.status[0])

    @read("fault_description", type="string", description="Fault description of the laser status (?FD)")
    def fault_description(self) -> str:
        return str(self.native.status[1])

    # -- writes -----------------------------------------------------------------------------------------------
    @write("power", unit="1",
           description="Power set point of the head in the unit the head uses; no text of the clone names that unit",
           limit=Limit.operator_required(
               "no text file of the clone states a power range: the maximum power is a property of each head "
               "(?MAXP, read at connect) and the wrapper clamps to it; the site states the operating power range "
               "of its own head"))
    def set_power(self, value: float) -> float:
        self.native.laser_power = value
        return float(self.native.laser_power)      # the value the head stored (the wrapper clamps it)

    @write("emission_delay", type="boolean", description="Turn the 5 second laser emission delay on (true) or off")
    def set_emission_delay(self, value: bool) -> None:
        self.native.emission_delay = 1 if value else 0

    @write("pulse_mode", type="boolean", description="Turn pulse mode on (true) or off")
    def set_pulse_mode(self, value: bool) -> None:
        self.native.pulse_mode = 1 if value else 0

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.czbiohub-sf.laser_emission_on.v1",
            description="Switch the laser emission on (the upstream turn_on alias, LE=1)",
            output={"emission": Field("boolean", description="True once the emission is on")})
    def emission_on(self) -> dict:
        self.native.turn_on()
        return {"emission": _flag(self.native.toggle_emission)}

    @action(name="x-cap.czbiohub-sf.laser_emission_off.v1", safe_state=True,
            description="Switch the laser emission off (the upstream turn_off alias, LE=0); the safe state",
            output={"emission": Field("boolean", description="False once the emission is off")})
    def emission_off(self) -> dict:
        self.native.turn_off()
        return {"emission": _flag(self.native.toggle_emission)}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self) -> None:
        """The native stop: the runtime latches first, then the emission goes off (LE=0)."""
        self.native.turn_off()
