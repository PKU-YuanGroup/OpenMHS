# Facts, limits and tags for gh.amsikking/thorlabs_mcm3000

The card's entry symbol `thorlabs_MCM3000:Controller` exists at line 4 of `thorlabs_MCM3000.py` and is the `native`
class of this package. The upstream controller builds framed binary serial commands, so this package is a direct
Driver over that class with a `native.py` factory; the card's `SerialDriver` helper cannot reproduce its bytes
(DEVIATION FROM THE CARD in RESULT.json).

Every fact cites its source at commit `390cd97e44abe04945db9b73ec8dc34a099d9f96`: `upstream_code` is a code or
docstring line of the clone, `vendor_doc` is a text file or a PDF page of it. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The upstream adaptor covers the Thorlabs MCM3000 and MCM3001 3-axis controllers | upstream_code | thorlabs_MCM3000.py:6 |
| The controller's serial port is opened at 460800 baud with a 5 s read timeout | upstream_code | thorlabs_MCM3000.py:27 |
| The supported stage table gives ZFM2020/ZFM2030 0.2116667 um/count within +/-12700 um and MMP-2XY 0.5 um/count within +/-25400 um | upstream_code | thorlabs_MCM3000.py:42-44 |
| `_legalize_move_um` asserts that the requested position lies within the selected stage's `position_limit_um` | upstream_code | thorlabs_MCM3000.py:167-170 |
| A position query is the 6-byte command `0A 04 <channel> 00 00 00`; the 12-byte reply carries the channel at byte 6 and the signed 32-bit little-endian encoder count in its last four bytes | upstream_code | thorlabs_MCM3000.py:97-102 |
| A move is the 12-byte command `53 04 06 00 00 00 <channel word> <signed 32-bit encoder count>` | upstream_code | thorlabs_MCM3000.py:135-138 |
| A relative move first refreshes the encoder position and then adds the requested offset before the limit check | upstream_code | thorlabs_MCM3000.py:163-166 |
| The upstream class docstring says a stop function is not implemented | upstream_code | thorlabs_MCM3000.py:7-8 |
| The vendor protocol defines an abrupt Stop Command with header `65 04`, the channel byte and stop mode `0x01` that stops any type of motor move on the specified channel | vendor_doc | MCM3000_Direct_Serial_Communication.pdf:2 |
| The stage encoder is assumed to be zero at the centre of its range for the +/- position checks | upstream_code | thorlabs_MCM3000.py:110-113 |
| Only the channels with a stage entry are available, and the constructor requires exactly three stage and reverse entries | upstream_code | thorlabs_MCM3000.py:32-54 |

The Stop Command fact cites page 2 of `MCM3000_Direct_Serial_Communication.pdf`, a PDF: the gate reports
`G4.REF_BINARY` because it cannot read the page, and a reviewer opens it. The page's table was read here: it gives
the 6-byte command `65 04 <channel> 01 00 00` ("Stop Axis 0 (stage1) TX 65, 04, 00, 01, 00, 00") and says the
command "stops any type of motor move on the specified channel" with the abrupt stop mode.

## Limits

| input | unit | limit | source |
|---|---|---|---|
| `x-cap.amsikking.move_channel.v1` `channel` | 1 | one of 0, 1, 2 | upstream_code, thorlabs_MCM3000.py:32-54 |
| `x-cap.amsikking.move_channel.v1` `position_um` | um | `operator_required`: the travel depends on the stage selected in the constructor's `stages` argument | operator |
| `x-cap.amsikking.move_channel.v1` `relative` | - | no numeric bound (boolean) | - |
| `cap.motion.stop.v1` `deceleration` | m/s2 | accepted for the class only; the vendor Stop Command is abrupt and takes no profile | - |

The upstream constructor defaults (`3*(None,)` stages) do not describe a connected unit: with no stage entry a
channel is unavailable, and the stage table has one travel per supported stage (ZFM2020/ZFM2030 +/-12700 um,
MMP-2XY +/-25400 um). A single numeric bound in `driver.py` would therefore be a guess for the connected stage, so
`position_um` is `Limit.operator_required` and every move is refused `MHS.SAFETY.LIMITS_UNSET` until the operator's
`site-limits.json` states the travel. `site-limits.example.json` is an example for one bench (+/-100 um), not a
statement about any unit; it fills the operator path for the acceptance run.

## Safety

- The e-stop and `cap.motion.stop.v1` send the vendor's abrupt Stop Command to every configured channel through the
  upstream `_send` frame writer. The upstream class implements no stop method; the command is the vendor document's,
  not an invented one.
- No line of the clone documents an independent hardware e-stop. The package is R1, so SAFE-045 (an independent stop
  for R2/R3) does not apply, and no hardware protection beyond the controller's stop command is claimed.
- Hardware is never attached in the acceptance run: `native.py` and the upstream package were never imported or
  executed, and no hardware run is claimed. The driver is model-authored and unreviewed (`reviewed_by` null).
- The fake has no motion over time, so the blocking move returns immediately; its conversion factors and start
  positions are placeholders, not facts.

## Tags

thorlabs, mcm3000, mcm3001, 3-axis, stage, stepper, encoder, motion
