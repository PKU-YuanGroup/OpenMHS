"""OpenMHS driver for gh.graysonbellamy/sartoriuslib: a Sartorius balance over xBPI or SBI.

A direct Driver over the card's first entry symbol, sartoriuslib.devices.balance:Balance.  The upstream facade is
asynchronous (every facade method is ``async def`` and awaits the session), so every method here is ``async def`` and
awaits ``self.native``.

* reads: net weight, gross weight and the stored tare value in milligrams, the reading's stability flag, the status
  state, the identity strings, and the six typed parameter-table settings (display unit, filter mode, auto-zero,
  isoCAL, tare behavior, menu access);
* writes: the same six settings, as string values whose allowed set is the upstream enum or display-unit table.  A
  write reaches the balance only after the OpenMHS runtime has accepted the receipt; the upstream setters additionally
  require ``confirm=True`` and this driver passes it, because the runtime's accepted command is the confirmation;
* ``cap.measure.mass.v1``: one mass measurement in milligrams with the device's stability flag;
* the e-stop closes the transport (``Balance.close``), so no further command can be sent.

The display unit is restricted to g, kg, mg and µg: those are the units the SDK's UCUM converter can convert to mg
(the upstream also offers carat, pound, ounce, tael and other display units, but the SDK has no conversion for them,
and this driver will not label a mass with the wrong unit).  A balance configured outside those four reports
``MHS.DEVICE.PRECONDITION_UNMET`` from the mass reads until the display unit is set back.

No Limit.operator_required is declared: every writable input is an enumerated string whose values are stated by the
upstream enum/tables, so no numeric device bound is invented.  The card's limit hints (MAX_ACCURACY, MAX_FAST,
max_drift_ms) are enum constants and a recorder default, not limits of a balance, and are not used.

Every Fact cites a line of the clone at the pinned commit 52f520767051ecee5af2ef5339e1cddc5c406a60.  This package
is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on hardware.  The
loader refuses the hardware backend of an unreviewed model-written package only at R2 and R3; this package is R1 and
has no such protection.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write
from mhs.units import convert_unit

#: The display units this driver can convert to milligrams through the SDK's UCUM converter.  The upstream Unit enum
#: also has carat, pound, ounce, tael and other display units (registry/units.py:36-93), but the SDK has no conversion
#: for them, so the driver does not expose them as writable values.
MASS_UNITS = ("g", "kg", "mg", "µg")

#: The display-unit values mapped to the UCUM atom the SDK converts (µg is spelled "ug" in UCUM).
_UCUM_MASS = {"g": "g", "kg": "kg", "mg": "mg", "µg": "ug"}

_FILTER_MODES = ("very_stable", "stable", "unstable", "very_unstable")
_AUTO_ZERO_MODES = ("on", "off")
_ISOCAL_MODES = ("off", "note", "on")
_TARE_BEHAVIORS = ("without_stability", "with_stability", "at_stability")
_MENU_ACCESS_MODES = ("can_edit", "read_only")

UNITS = "src/sartoriuslib/registry/units.py"
MODES = "src/sartoriuslib/registry/modes.py"
BALANCE = "src/sartoriuslib/devices/balance.py"
MODELS = "src/sartoriuslib/devices/models.py"


def _enum_name(value):
    """The lower-case member name of an upstream IntEnum (``FilterMode.STABLE`` -> ``"stable"``)."""
    return str(value.name).lower()


def _unit_value(value):
    """The canonical string of an upstream Unit StrEnum (``Unit.G`` -> ``"g"``)."""
    return str(value.value)


def _mass_mg(reading):
    """Convert one upstream Reading to milligrams, or refuse a unit the SDK cannot convert."""
    if reading.value is None:
        raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                           "the balance reports an off-scale reading with no numeric value")
    unit = getattr(reading.unit, "value", reading.unit)
    ucum = _UCUM_MASS.get(str(unit))
    if ucum is None:
        raise DriverFailed(
            "MHS.DEVICE.PRECONDITION_UNMET",
            f"the display unit {unit!r} is not one this driver converts to mg; set the display unit to g, kg, mg or µg")
    return convert_unit(float(reading.value), ucum, "mg")


class SartoriusBalance(Driver):
    device_id = "sartorius-balance"
    device_kind = "instrument.balance"
    mode = "hardware"
    risk = "R1"
    native = "sartoriuslib.devices.balance:Balance"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBalance"}
    vendor, model = "Sartorius", "Sartorius balance (sartoriuslib Balance facade)"
    display_name = "Sartorius balance via sartoriuslib"
    tags = ["balance", "weighing", "mass", "sartorius", "xbpi", "sbi", "asyncio"]
    facts = [
        Fact("Balance is the protocol-neutral facade; construct it via sartoriuslib.open_device",
             source="upstream_code", ref=f"{BALANCE}:300-308"),
        Fact("read_net returns the live net weight as a Reading", source="upstream_code", ref=f"{BALANCE}:408-419"),
        Fact("read_gross returns the gross weight as a Reading", source="upstream_code", ref=f"{BALANCE}:425-428"),
        Fact("read_tare_value returns the stored tare value as a Reading", source="upstream_code",
             ref=f"{BALANCE}:434-436"),
        Fact("status returns the full status block as a BalanceStatus", source="upstream_code",
             ref=f"{BALANCE}:478-480"),
        Fact("The status state is one of stable, unstable, overload, underload, off or unknown",
             source="upstream_code", ref=f"{MODELS}:42-50"),
        Fact("A Reading carries value, unit and stable; value is None on the off-scale sentinel",
             source="upstream_code", ref=f"{MODELS}:62-82"),
        Fact("get_filter_mode reads p01 and set_filter_mode writes p01", source="upstream_code",
             ref=f"{BALANCE}:855-878"),
        Fact("get_display_unit reads p07 and set_display_unit writes p07", source="upstream_code",
             ref=f"{BALANCE}:880-901"),
        Fact("get_auto_zero reads p06 and set_auto_zero writes p06", source="upstream_code",
             ref=f"{BALANCE}:903-919"),
        Fact("get_isocal_mode reads p15 and set_isocal_mode writes p15", source="upstream_code",
             ref=f"{BALANCE}:921-937"),
        Fact("get_tare_behavior reads p05 and set_tare_behavior writes p05", source="upstream_code",
             ref=f"{BALANCE}:939-955"),
        Fact("get_menu_access reads p40 and set_menu_access writes p40", source="upstream_code",
             ref=f"{BALANCE}:957-973"),
        Fact("The parameter writers require confirm=True", source="upstream_code", ref=f"{BALANCE}:818-836"),
        Fact("The p01 filter modes are very stable, stable, unstable and very unstable", source="upstream_code",
             ref=f"{MODES}:41-52"),
        Fact("The p05 tare behaviors are without stability, with stability and at stability", source="upstream_code",
             ref=f"{MODES}:87-93"),
        Fact("The p06 auto-zero modes are on and off", source="upstream_code", ref=f"{MODES}:96-101"),
        Fact("The p15 isoCAL modes are off, note and on", source="upstream_code", ref=f"{MODES}:135-145"),
        Fact("The p40 menu access modes are can_edit and read_only", source="upstream_code",
             ref=f"{MODES}:197-202"),
        Fact("The p07 display-unit table includes g, kg, mg and µg", source="upstream_code",
             ref=f"{UNITS}:36-93"),
        Fact("close closes the underlying transport and is idempotent", source="upstream_code",
             ref=f"{BALANCE}:349-351"),
    ]
    safe_state = "the balance transport is closed; no further command is sent to the instrument"

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _identity(self):
        info = self.native.info
        if info is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the balance has no cached identity; open it with identify=True")
        return info

    # -- weight and status reads -----------------------------------------------------------------------------------
    @read("net_weight", unit="mg", description="Live net weight in milligrams")
    async def net_weight(self):
        return _mass_mg(await self.native.read_net())

    @read("gross_weight", unit="mg", description="Gross weight in milligrams")
    async def gross_weight(self):
        return _mass_mg(await self.native.read_gross())

    @read("tare_value", unit="mg", description="Stored tare value in milligrams")
    async def tare_value(self):
        return _mass_mg(await self.native.read_tare_value())

    @read("stable", type="boolean", description="True when the last net weight reading is stable")
    async def stable(self):
        return bool((await self.native.read_net()).stable)

    @read("status_state", type="string",
          description="Weighing state from the status block: stable, unstable, overload, underload, off or unknown")
    async def status_state(self):
        return str((await self.native.status()).state.value)

    # -- identity reads --------------------------------------------------------------------------------------------
    @read("model", type="string", description="Model string reported by the balance")
    async def model_name(self):
        return str(self._identity().model)

    @read("serial", type="string",
          description="Serial or factory number reported by the balance; empty when it reports none")
    async def serial_number(self):
        return str(self._identity().serial or "")

    @read("software", type="string",
          description="Software version reported by the balance; empty when it reports none")
    async def software_version(self):
        return str(self._identity().software or "")

    # -- typed parameter reads -------------------------------------------------------------------------------------
    @read("display_unit", type="string", description="Display unit p07: g, kg, mg or µg")
    async def display_unit(self):
        return _unit_value(await self.native.get_display_unit())

    @read("filter_mode", type="string", description="Filter/ambient mode p01")
    async def filter_mode(self):
        return _enum_name(await self.native.get_filter_mode())

    @read("auto_zero", type="string", description="Auto-zero tracking p06: on or off")
    async def auto_zero(self):
        return _enum_name(await self.native.get_auto_zero())

    @read("isocal_mode", type="string", description="isoCAL mode p15: off, note or on")
    async def isocal_mode(self):
        return _enum_name(await self.native.get_isocal_mode())

    @read("tare_behavior", type="string", description="Tare-on-stability behavior p05")
    async def tare_behavior(self):
        return _enum_name(await self.native.get_tare_behavior())

    @read("menu_access", type="string", description="Front-panel menu access p40: can_edit or read_only")
    async def menu_access(self):
        return _enum_name(await self.native.get_menu_access())

    # -- typed parameter writes ------------------------------------------------------------------------------------
    @write("display_unit", type="string", description="Display unit p07",
           limit=Limit(allowed=MASS_UNITS, source="upstream_code", ref=f"{UNITS}:36-93"))
    async def set_display_unit(self, value):
        await self.native.set_display_unit(value, confirm=True)
        return _unit_value(await self.native.get_display_unit())

    @write("filter_mode", type="string", description="Filter/ambient mode p01",
           limit=Limit(allowed=_FILTER_MODES, source="upstream_code", ref=f"{MODES}:41-52"))
    async def set_filter_mode(self, value):
        await self.native.set_filter_mode(value, confirm=True)
        return _enum_name(await self.native.get_filter_mode())

    @write("auto_zero", type="string", description="Auto-zero tracking p06",
           limit=Limit(allowed=_AUTO_ZERO_MODES, source="upstream_code", ref=f"{MODES}:96-101"))
    async def set_auto_zero(self, value):
        await self.native.set_auto_zero(value, confirm=True)
        return _enum_name(await self.native.get_auto_zero())

    @write("isocal_mode", type="string", description="isoCAL mode p15",
           limit=Limit(allowed=_ISOCAL_MODES, source="upstream_code", ref=f"{MODES}:135-145"))
    async def set_isocal_mode(self, value):
        await self.native.set_isocal_mode(value, confirm=True)
        return _enum_name(await self.native.get_isocal_mode())

    @write("tare_behavior", type="string", description="Tare-on-stability behavior p05",
           limit=Limit(allowed=_TARE_BEHAVIORS, source="upstream_code", ref=f"{MODES}:87-93"))
    async def set_tare_behavior(self, value):
        await self.native.set_tare_behavior(value, confirm=True)
        return _enum_name(await self.native.get_tare_behavior())

    @write("menu_access", type="string", description="Front-panel menu access p40",
           limit=Limit(allowed=_MENU_ACCESS_MODES, source="upstream_code", ref=f"{MODES}:197-202"))
    async def set_menu_access(self, value):
        await self.native.set_menu_access(value, confirm=True)
        return _enum_name(await self.native.get_menu_access())

    # -- measurement action ----------------------------------------------------------------------------------------
    @action(cap="cap.measure.mass.v1",
            description="Read net, gross or tare mass in milligrams and the device's stability flag",
            input={
                "channel": Field(
                    type="string", description="Which reading to return: net (default), gross or tare",
                    limit=Limit(allowed=("net", "gross", "tare"), source="upstream_code",
                                ref=f"{BALANCE}:408-436")),
                "settle": Field(
                    type="boolean",
                    description="If true, a reading that is not stable is refused; the facade has no settle "
                                "primitive to wait on"),
            })
    async def measure_mass(self, channel=None, settle=False):
        if channel == "gross":
            reading = await self.native.read_gross()
        elif channel == "tare":
            reading = await self.native.read_tare_value()
        else:
            reading = await self.native.read_net()
        if settle and not reading.stable:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "settle=true but the reading is not stable; the facade has no settle primitive")
        return {"mass": _mass_mg(reading), "stable": bool(reading.stable)}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="close")
    async def stop(self):
        """Close the transport: the balance accepts no further command after this returns."""
        await self.native.close()

    async def teardown(self):
        await self.native.close()
