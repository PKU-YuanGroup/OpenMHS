# Facts and tags for gh.raphaelsura/pythonphotonicslab

This package binds one entry symbol of the clone: `LowLevelModules.Instruments:DG645`
(`LowLevelModules/Instruments.py:96`), the SRS DG645 digital delay generator.  The clone also contains an SG384 signal
generator, a Lake Shore 335 temperature controller, a Gauss meter and two Newport Conex stages; this package does not
cover them.  Every fact cites the clone at commit `bdef2648d4aec219566f710ade6c1b9ba224bc19`; the reference file is
generated from `driver.py`, not from this page.

| fact | source | ref |
|---|---|---|
| DG645 is the digital delay generator class of the clone and opens a VISA resource | upstream_code | LowLevelModules/Instruments.py:96-101 |
| set_polarity writes 'LPOL <output>,<index>' and get_polarity queries 'LPOL? <output>' | upstream_code | LowLevelModules/Instruments.py:109-113 |
| set_delay writes 'DLAY <channel>,<reference>,<time>' and get_delay queries 'DLAY? <channel>' | upstream_code | LowLevelModules/Instruments.py:172-176 |
| set_amplitude writes 'LAMP <output>,<value>' and get_amplitude queries 'LAMP? <output>' | upstream_code | LowLevelModules/Instruments.py:178-182 |
| set_offset writes 'LOFF <output>,<value>' and get_offset queries 'LOFF? <output>' | upstream_code | LowLevelModules/Instruments.py:184-188 |
| The burst settings are BURC count, BURD delay, BURM mode, BURP period and BURT configuration | upstream_code | LowLevelModules/Instruments.py:142-170 |
| The clone's notebook uses four BNC outputs numbered 1 to 4 | upstream_code | ControlHardware/Obsolete/PLEScan-Copy1.ipynb:8647-8659 |
| Polarity index 0 is 'negative polarity, default HIGH' | upstream_code | ControlHardware/Obsolete/PLEScan-Copy1.ipynb:8707 |
| Polarity index 1 is 'positive polarity, default LOW', the notebook's off state for a laser channel | upstream_code | ControlHardware/Obsolete/PLEScan-Copy1.ipynb:8709 |
| The notebook's DG645 timing constants are seconds (init_time = 1e-6 # sec, PLE_time = 5e-6 # sec) | upstream_code | ControlHardware/Obsolete/PLEScan-Copy1.ipynb:8632-8633 |
| The notebook sets burst mode 1 and writes the burst period, delay and count | upstream_code | ControlHardware/Obsolete/PLEScan-Copy1.ipynb:8727-8730 |

## Limits

The clone's DG645 class writes every argument unchanged and states no accepted numeric range for any setting.  There is
also no README or documentation text in the clone that states a DG645 range.  Every numeric write is therefore
`Limit.operator_required`: the deployment operator supplies the bound in `site-limits.json`, and until then every write
is refused with `MHS.SAFETY.LIMITS_UNSET`.  `site-limits.example.json` fills the twelve writable fields with example
bounds; it is an example deployment overlay, not a statement about the instrument.

The units are the ones the driver publishes.  The notebook's timing constants are seconds, so the delay, holdoff, burst
delay and burst period fields use `s`; the trigger rate uses `Hz`.  The clone states no unit for LAMP, LOFF or TLVL, so
those fields use the UCUM unity code `1` and their descriptions say so.

| parameter | command | bound in driver.py |
|---|---|---|
| amplitude (output 1) | LAMP 1,value | operator_required |
| offset (output 1) | LOFF 1,value | operator_required |
| polarity (output 1) | LPOL 1,index | operator_required |
| delay (channel 1 from T0) | DLAY 1,0,value | operator_required |
| holdoff | HOLD value | operator_required |
| trigger_level | TLVL value | operator_required |
| trigger_rate | TRAT value | operator_required |
| burst_count | BURC value | operator_required |
| burst_delay | BURD value | operator_required |
| burst_mode | BURM value | operator_required |
| burst_period | BURP value | operator_required |
| burst_config | BURT value | operator_required |

## Safety

The device is an R1 instrument: the card's floor is R1 and the driver only sets timing and output levels.  The e-stop
writes `LPOL 1,1`, `LPOL 2,1`, `LPOL 3,1` and `LPOL 4,1`, putting all four BNC outputs at positive polarity.  The clone's
notebook calls polarity index 1 "positive polarity, default LOW" and uses it as the off state for its laser channels,
so this is the safe state for that wiring.  It is a software command to the delay generator, not a hardware emergency
stop, and it does not remove power from a laser or shutter; deployments that need an independent stop must wire one.

## Fake and coverage

No upstream simulator or recorded session exists in the clone.  The card's preferred mock is a transcript, but a strict
replay of one fixed sequence cannot serve the gate and the conformance suite, which send many different sequences on
fresh transports.  `fake.py` is therefore a stateful in-memory SCPI transport; every start value is test data marked
`# placeholder`, never a device fact.  It answers only the command mnemonics the clone's DG645 class writes.

NOT COVERED: outputs 2-4 for LAMP, LOFF and LPOL, and delay channels 2-9.  The OpenMHS state schema has one field per
name, so the package exposes output 1 and delay channel 1 as writable state fields and leaves the other indexes to a
future capability.  NOT COVERED: the SG384, LakeShore335, GaussMeter475, ConexCC and ConexAGP classes of the same
repository.  The package is model-authored and unreviewed; no hardware backend was run and no hardware run is claimed.

Tags: delay generator, dg645, srs, scpi, instrument
