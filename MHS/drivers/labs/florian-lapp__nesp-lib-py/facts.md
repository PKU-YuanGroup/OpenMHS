# Facts and tags for gh.florian-lapp/nesp-lib-py

Every fact cites its source at commit `c16abc82c9feb7c356f06c30b0dff0d4d421cfe3`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Pump is the high level interface to the New Era syringe pumps, also sold as Aladdin by World Precision Instruments and LA by Landgraf Laborsysteme | vendor_doc | README.md:3-7 |
| A pump is constructed from a Port of the pyserial connection: pump = Pump(port) | vendor_doc | README.md:62-65 |
| Port opens a pyserial serial port and BAUD_RATE_DEFAULT is 9_600 | upstream_code | nesp_lib/port.py:9-10 |
| Port.__init__ opens serial.Serial(port=name, baudrate=baud_rate) | upstream_code | nesp_lib/port.py:30-35 |
| Pump.__init__ sets the safe mode timeout and reads the model number, firmware version and firmware upgrade from the pump on construction | upstream_code | nesp_lib/pump.py:71-79 |
| syringe_diameter_mm is in millimetres and its values are SYRINGE_DIAMETER_MINIMUM_MM (0.1 mm) to SYRINGE_DIAMETER_MAXIMUM_MM (80.0 mm) | upstream_code | nesp_lib/pump.py:30-33 |
| safe_mode_timeout_s is in seconds within SAFE_MODE_TIMEOUT_DISABLED (0 s) and SAFE_MODE_TIMEOUT_LIMIT_S (255 s) | upstream_code | nesp_lib/pump.py:25-28 |
| A safe mode timeout of zero sets the communication to basic mode and a non-zero value sets it to safe mode | upstream_code | nesp_lib/pump.py:130-133 |
| PumpingDirection has the members INFUSE and WITHDRAW; pumping_direction is set as one of them and a value the direction tables do not know raises ValueError | upstream_code | nesp_lib/pump.py:195-201 |
| The pumping volume setter refuses a value below 0.001/1000.0 mL and a value at or above 10_000.0 mL | upstream_code | nesp_lib/pump.py:226-227 |
| The pumping rate limits are dictated by the syringe diameter of the pump | upstream_code | nesp_lib/pump.py:255 |
| The pumping rate setter refuses a value below 0.001/60_000.0 mL/min and a value at or above 10_000.0 mL/min | upstream_code | nesp_lib/pump.py:262-263 |
| pumping_volume_ml and pumping_rate_ml_per_min are read from a value and a unit the pump reports and converted to millilitres and millilitres per minute (VOL with ML/UL, RAT with MM/MH/UM/UH) | upstream_code | nesp_lib/pump.py:411-427 |
| volume_infused_ml and volume_withdrawn_ml read the dispensation counters of the pump, the DIS reply "I" <infused> "W" <withdrawn> <units> | upstream_code | nesp_lib/pump.py:280-300 |
| run(wait_while_running=True) sends RUN and waits while the pump is running; run(False) returns after starting it and wait_while_running polls the status every PUMPING_POLL_DELAY_S | upstream_code | nesp_lib/pump.py:302-335 |
| run_purge sends PUR: the pump runs at maximum rate in the configured direction until it is stopped | upstream_code | nesp_lib/pump.py:313-319 |
| stop(wait_while_running=True) sends STP and waits while the pump is running | upstream_code | nesp_lib/pump.py:321-330 |
| The status property reads the Status of the pump and running is true while the status is INFUSING, WITHDRAWING or PURGING | upstream_code | nesp_lib/pump.py:140-149 |
| Status has the members INFUSING, WITHDRAWING, PURGING, STOPPED, PAUSED, SLEEPING and WAITING | upstream_code | nesp_lib/status.py:3-19 |
| The command names are an empty name for the status and SAF, VER, DIA, DIR, VOL, RAT, DIS, CLD, RUN, PUR and STP | upstream_code | nesp_lib/pump.py:342-354 |
| A request is the address, the command name and the formatted arguments, str(address) + name.value + arguments | upstream_code | nesp_lib/pump.py:490-493 |
| In safe mode a request is framed as STX, a length byte, the request bytes, the CCITT CRC (binascii.crc_hqx) and ETX; in basic mode it is the request text with a carriage return | upstream_code | nesp_lib/pump.py:527-543 |
| A reply is an STX ... ETX frame in basic mode and carries a length byte and a checksum in safe mode | upstream_code | nesp_lib/pump.py:545-576 |
| The reply begins with a two character address that must equal the pump's address | upstream_code | nesp_lib/pump.py:500-505 |
| The pump address defaults to ADDRESS_DEFAULT 0 and may not exceed ADDRESS_LIMIT 99 | upstream_code | nesp_lib/pump.py:20-23 |
| The README prints model_number (1000 for NE-1000) and firmware_version ((3, 928) for 3.928) | vendor_doc | README.md:82-87 |

## Limits

- `syringe_diameter_mm` (writable state field, number in mm): `Limit(min=0.1, max=80.0, source=upstream_code,
  ref=nesp_lib/pump.py:30-33)`. The two class constants are `SYRINGE_DIAMETER_MINIMUM_MM = 0.1` and
  `SYRINGE_DIAMETER_MAXIMUM_MM = 80.0`, and the setter refuses everything outside them (nesp_lib/pump.py:177-181).
- `safe_mode_timeout_s` (writable state field, integer in s): `Limit(min=0, max=255, source=upstream_code,
  ref=nesp_lib/pump.py:25-28)`. The class constants are `SAFE_MODE_TIMEOUT_DISABLED = 0` and
  `SAFE_MODE_TIMEOUT_LIMIT_S = 255`, and the setter refuses everything outside them (nesp_lib/pump.py:636-637).
  A value of zero stays in basic mode and a non-zero value switches the pump to safe mode (nesp_lib/pump.py:130-133).
- `pumping_volume_ml` and `pumping_rate_ml_per_min` (writable state fields): `Limit.operator_required`. The class's
  own setter statements are protocol envelopes, not bounds of the device: the volume is refused below
  `0.001 / 1_000.0` mL and at or above `10_000.0` mL (nesp_lib/pump.py:226-227, an open upper edge), and the rate
  limits are dictated by the syringe fitted (nesp_lib/pump.py:255) within `0.001 / 60_000.0` to `10_000.0` mL/min
  (nesp_lib/pump.py:262-263). The site supplies the ranges its syringe allows (`site-limits.example.json` shows the
  overlay; until then every call that sets either field is refused `MHS.SAFETY.LIMITS_UNSET`).
- `pumping_direction` (writable state field, string): the allowed values `INFUSE` and `WITHDRAW` are the members of
  `PumpingDirection` (nesp_lib/pumping_direction.py:3-8); they are declared as the field's enum, not as a limit, so
  the site overlay cannot widen it.

## Deviation from the card

The card is `family-config` with the `SerialDriver` helper (`reason_code: family:serial`). That shape cannot express
this pump: a request is assembled from the address, a command letter code and formatted arguments
(nesp_lib/pump.py:490-493), and in safe mode it is a binary frame with STX, a length byte, a CCITT CRC and ETX
(nesp_lib/pump.py:527-543), while a command table writes text lines. The package is therefore a direct `Driver` over
`nesp_lib.pump:Pump` with a `native.py` factory, as "Choosing the shape" of the authoring guide prescribes.

## Safety

The pump is an actuator that dispenses liquid: R2 (a model review raised it from the card's floor). The native stop is `Pump.stop(False)` (STP, nesp_lib/pump.py:321-330), used by `@estop`
and by the safe-state action `x-cap.florian-lapp.stop_pump.v1` (`safe_state=True`, no input). `estop_physical_ref` is
not set: no line of the clone documents an independent hardware stop, so the safe-state action is the independent
stop SAFE-045 asks for at R2. There is no interlock and no permit in the clone. The run and purge actions start the
pump without waiting (`run(False)`, nesp_lib/pump.py:302-311), so their receipts do not claim that a dispense finished:
the state (`status`, `running`, `volume_infused_ml`, `volume_withdrawn_ml`) reports it.

## Not covered

- The serial protocol itself: the safe-mode framing and checksums (nesp_lib/pump.py:527-576) are done by the upstream
  library at run time, and the fake does not reproduce them; no frame was produced or checked by this package.
- The heartbeat thread that safe mode starts (nesp_lib/pump.py:646-672): it runs inside the upstream object and the
  fake does not model it.
- The upstream volume and rate *settlement* units (ML/UL, MM/MH/UM/UH, nesp_lib/pump.py:411-427): they are chosen by
  the upstream setter, and the state reads report the value converted back to millilitres and millilitres per minute.
- The `firmware_upgrade` field, `address` field, the `volume_infused_clear`/`volume_withdrawn_clear` methods and the
  alarm status (`StatusAlarmException`) are not exposed.

Tags: syringe-pump, fluid, infuse, withdraw, serial
