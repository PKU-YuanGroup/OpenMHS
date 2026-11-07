# Facts and tags for gh.davehe929/scopebench-mcp

Every fact cites its source at commit `3f0abc87a2839e816744a7d867c1ef06ed721f7a`: `vendor_doc` (a text file of the
clone such as `README.md` or `docs/*.md`) or `upstream_code` (a Python file of the clone with its line). The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| The project targets the RIGOL DHO800/DHO900 SCPI oscilloscope family and was verified on a DHO804D | vendor_doc | README.md:15-17 |
| The DHO804D identity reply is 'RIGOL TECHNOLOGIES,DHO804D,<serial>,<firmware>' | vendor_doc | README.md:185 |
| Raw LAN SCPI is reachable on port 5555; port 5025 did not accept connections on the tested DHO804D | vendor_doc | docs/compatibility_matrix.md:6 |
| The instrument is identified with *IDN? | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:36-37 |
| The error queue is read with ':SYSTem:ERRor?'; a reply that starts with 0 or '+0', or contains 'No error', means no error | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:62-75 |
| The acquisition state is queried with ':TRIGger:STATus?' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:20 |
| An analog channel's display, scale and offset are read with ':CHANnel<n>:DISPlay?', ':CHANnel<n>:SCALe?' and ':CHANnel<n>:OFFSet?', and the coupling with ':CHANnel<n>:COUPling?' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:40-51 |
| The timebase scale and offset are read with ':TIMebase:MAIN:SCALe?' and ':TIMebase:MAIN:OFFSet?' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:25-26 |
| The edge-trigger level is read with ':TRIGger:EDGE:LEVel?' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:24 |
| Channel settings are written as ':CHANnel<n>:COUPling <value>', ':CHANnel<n>:SCALe <value>' and ':CHANnel<n>:OFFSet <value>' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:118-131 |
| The timebase is written as ':TIMebase:MAIN:SCALe <value>' and ':TIMebase:MAIN:OFFSet <value>' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:143-150 |
| The edge-trigger level is written as ':TRIGger:EDGE:LEVel <value>' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:174-186 |
| The coupling accepts AC, DC and GND (the map also accepts the alias GROUND) | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:1149-1154 |
| The acquisition is controlled with ':RUN', ':STOP' and ':SINGle' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:1193-1199 |
| A measurement is queried with ':MEASure:ITEM? <item>,CHANnel<n>' | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:596 |
| The measurement names select the SCPI items FREQuency, PERiod, VPP, VMAX, VMIN, VAVG, VRMS, PDUTy, NDUTy, RTIMe and FTIMe | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:519-536 |
| The analog channels are numbered 1 to 4 | upstream_code | src/scopebench_mcp/drivers/rigol_dho.py:1240-1241 |
| Valid vertical and horizontal offset ranges depend on the active volts/div setting, the main timebase and the RUN/STOP state, so they must not be hard-coded | vendor_doc | docs/development_plan.md:148-151 |
| The device readback is authoritative because valid ranges depend on scale and acquisition state | vendor_doc | README.md:294-296 |
| The clone's raw TCP transport defaults to port 5555 | upstream_code | src/scopebench_mcp/transports/tcp.py:18 |

## Limits

| parameter | command | limit | source and ref |
|---|---|---|---|
| channel_coupling | :CHANnel1:COUPling | one of AC, DC, GND | upstream_code, src/scopebench_mcp/drivers/rigol_dho.py:1149-1154 |
| channel_scale (V/div) | :CHANnel1:SCALe | operator_required: no text of the clone states the volts/div range; it depends on the active volts/div setting (docs/development_plan.md:148-150) | operator overlay |
| channel_offset (V) | :CHANnel1:OFFSet | operator_required: no text of the clone states a vertical offset range; it depends on the active volts/div setting (docs/development_plan.md:148-150) | operator overlay |
| trigger_level (V) | :TRIGger:EDGE:LEVel | operator_required: no text of the clone states a trigger level range; valid ranges depend on scale and acquisition state (docs/development_plan.md:148-151, README.md:294-296) | operator overlay |
| timebase_scale (s/div) | :TIMebase:MAIN:SCALe | operator_required: no text of the clone states the seconds/div range; it depends on the main timebase and RUN/STOP state (docs/development_plan.md:148-150) | operator overlay |
| timebase_offset (s) | :TIMebase:MAIN:OFFSet | operator_required: no text of the clone states a horizontal offset range; it depends on the main timebase and RUN/STOP state (docs/development_plan.md:148-150) | operator overlay |
| x-cap.davehe929.scope_measure.v1 channel | :MEASure:ITEM? | integer 1 to 4 | upstream_code, src/scopebench_mcp/drivers/rigol_dho.py:1240-1241 |
| x-cap.davehe929.scope_measure.v1 measurement | :MEASure:ITEM? | one of the 16 names of the clone's table | upstream_code, src/scopebench_mcp/drivers/rigol_dho.py:519-536 |

`site-limits.example.json` fills the five operator-required fields with example bounds; an actual site replaces
them with the bounds of its probes and timebase. The overlay may only narrow.

## Safety

R1: the driver sets no instrument output. The e-stop writes `:STOP` (the clone's acquisition stop), so the scope
stops acquiring. The waveform, screenshot, statistics, pulse-trigger, cursor, autoscale and LAN-configuration
functions of the clone are not part of this driver.

Tags: oscilloscope, rigol, dho800, dho804d, scpi
