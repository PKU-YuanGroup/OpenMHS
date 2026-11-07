# Facts and tags for gh.graysonbellamy/sartoriuslib

Every fact cites its source at commit `52f520767051ecee5af2ef5339e1cddc5c406a60`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Balance is the protocol-neutral facade; construct it via sartoriuslib.open_device | upstream_code | src/sartoriuslib/devices/balance.py:300-308 |
| read_net returns the live net weight as a Reading | upstream_code | src/sartoriuslib/devices/balance.py:408-419 |
| read_gross returns the gross weight as a Reading | upstream_code | src/sartoriuslib/devices/balance.py:425-428 |
| read_tare_value returns the stored tare value as a Reading | upstream_code | src/sartoriuslib/devices/balance.py:434-436 |
| status returns the full status block as a BalanceStatus | upstream_code | src/sartoriuslib/devices/balance.py:478-480 |
| The status state is one of stable, unstable, overload, underload, off or unknown | upstream_code | src/sartoriuslib/devices/models.py:42-50 |
| A Reading carries value, unit and stable; value is None on the off-scale sentinel | upstream_code | src/sartoriuslib/devices/models.py:62-82 |
| get_filter_mode reads p01 and set_filter_mode writes p01 | upstream_code | src/sartoriuslib/devices/balance.py:855-878 |
| get_display_unit reads p07 and set_display_unit writes p07 | upstream_code | src/sartoriuslib/devices/balance.py:880-901 |
| get_auto_zero reads p06 and set_auto_zero writes p06 | upstream_code | src/sartoriuslib/devices/balance.py:903-919 |
| get_isocal_mode reads p15 and set_isocal_mode writes p15 | upstream_code | src/sartoriuslib/devices/balance.py:921-937 |
| get_tare_behavior reads p05 and set_tare_behavior writes p05 | upstream_code | src/sartoriuslib/devices/balance.py:939-955 |
| get_menu_access reads p40 and set_menu_access writes p40 | upstream_code | src/sartoriuslib/devices/balance.py:957-973 |
| The parameter writers require confirm=True | upstream_code | src/sartoriuslib/devices/balance.py:818-836 |
| The p01 filter modes are very stable, stable, unstable and very unstable | upstream_code | src/sartoriuslib/registry/modes.py:41-52 |
| The p05 tare behaviors are without stability, with stability and at stability | upstream_code | src/sartoriuslib/registry/modes.py:87-93 |
| The p06 auto-zero modes are on and off | upstream_code | src/sartoriuslib/registry/modes.py:96-101 |
| The p15 isoCAL modes are off, note and on | upstream_code | src/sartoriuslib/registry/modes.py:135-145 |
| The p40 menu access modes are can_edit and read_only | upstream_code | src/sartoriuslib/registry/modes.py:197-202 |
| The p07 display-unit table includes g, kg, mg and µg | upstream_code | src/sartoriuslib/registry/units.py:36-93 |
| close closes the underlying transport and is idempotent | upstream_code | src/sartoriuslib/devices/balance.py:349-351 |

Limits: none are declared. Every writable input of this package is a string whose allowed set is quoted from an
upstream enum or the p07 display-unit table; no numeric device bound is stated by the driver. The card's
`safety.limit_hints` point at enum constants (`MAX_ACCURACY = 1`, `MAX_FAST = 6`) and a recorder default
(`max_drift_ms = 0.0`); those are not limits of a balance and are not used.

Display units: the driver exposes only g, kg, mg and µg because those are the display units the SDK's UCUM converter
can convert to milligrams. The upstream p07 table also has carat, pound, ounce, troy ounce, grain, pennyweight, four
tael variants, momme, Austrian carat, tola, baht, mesghal, metric ton, pounds-and-ounces, parts-per-pound and
newton, plus a user-defined unit. A balance whose display unit is one of those reports
`MHS.DEVICE.PRECONDITION_UNMET` from the mass reads and from the mass action until an operator sets one of the four
supported units.

Safety: the e-stop and `teardown` both call `Balance.close` (src/sartoriuslib/devices/balance.py:349-351), which
closes the underlying transport, so no further command can be sent. This is a software stop path at R1; no
independent hardware e-stop is claimed and `estop_physical_ref` is not set (SAFE-045 applies at R2 and above).

Tags: balance, weighing, mass, sartorius, xbpi, sbi, asyncio
