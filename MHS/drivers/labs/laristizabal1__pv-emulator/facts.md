# Facts and tags for gh.laristizabal1/pv-emulator

Every fact cites the clone at commit `a2339189e88c80889a86ac67bcf98b5cc9fc4447`: `vendor_doc` for the text of the
clone (README.md, docs/) or `upstream_code` for a code line. The same facts are declared in `driver.py`.

| fact | source | ref |
|---|---|---|
| The platform uses a programmable EA-PS 10060-170 source rated 0-60 V, 0-170 A and 5 kW | vendor_doc | README.md:4 |
| The source connects over USB as a virtual COM port and SCPIController sends SCPI ASCII commands | vendor_doc | docs/hardware.md:5-6 |
| The electrical limits come from the EA-PS 10000 3U manual, document 06230820_EN | upstream_code | config/hardware.py:26-27 |
| V_MAX is 60.0 V, I_MAX 170.0 A, P_MAX 5000.0 W and DT_MIN 200 ms | upstream_code | config/hardware.py:28-31 |
| EAPowerSupply is the low-latency SCPI driver the upstream bridge uses for the source | upstream_code | comm/bridge.py:132-143 |
| V and I setpoints are not queried from the source; the upstream caches them when it sends commands | upstream_code | comm/bridge.py:141-142 |
| read_meas_fast returns measured V, I and P, using MEAS:ALL? or the separate MEAS:VOLT? and MEAS:CURR? queries | upstream_code | comm/bridge.py:214-240 |
| get_output_state queries OUTP:STAT? and treats the reply '1' or 'ON' as output on | upstream_code | comm/bridge.py:257-262 |
| get_error_code queries SYST:ERR? and reads the first field as an integer | upstream_code | comm/bridge.py:267-271 |
| output(on) writes OUTP ON or OUTP OFF and caches the resulting state | upstream_code | comm/bridge.py:276-278 |
| set_voltage writes VOLT after clamping the value to 0.0 through V_MAX and caches it as cached_vset | upstream_code | comm/bridge.py:280-283 |
| set_current_limit writes CURR after clamping the value to 0.0 through I_MAX and caches it as cached_iset | upstream_code | comm/bridge.py:285-288 |
| SCPIController.stop() clears the running flag and calls output_off(), which sends OUTP OFF | upstream_code | comm/scpi.py:723-725 |
| STAT:OPER:COND? bit 6 (0x0040) means the output is active and bit 9 (0x0200) means remote control is active | upstream_code | comm/scpi.py:346-355 |

Tags: `dc source`, `power supply`, `pv emulator`, `scpi`, `ea-ps`.

The two write bounds (0-60 V and 0-170 A) are the ratings on README.md:4 and the clamps in
`set_voltage`/`set_current_limit` (comm/bridge.py:280-288); the power rating is a Fact but this driver exposes no
power setpoint because EAPowerSupply has none. The source has no vendor-text hardware emergency stop in the clone,
so the R2 independent stop is the safe-state action that writes OUTP OFF.
