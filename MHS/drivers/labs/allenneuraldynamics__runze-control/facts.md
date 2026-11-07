# Facts and tags for gh.allenneuraldynamics/runze-control

Every fact cites its source at commit `34392b3d9bc0d60c0c46f69908fec7f108cef230`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SY01B is the ZSB-SY01B multichannel syringe pump with an integrated rotary valve | upstream_code | src/runze_control/multichannel_syringe_pump.py:80-81 |
| SY01B supports 6, 9 and 12 valve ports | upstream_code | src/runze_control/multichannel_syringe_pump.py:82 |
| SY01B supports syringe volumes of 25, 50, 125, 500, 1250, 2500 and 5000 uL, all with 6000 position steps | upstream_code | src/runze_control/multichannel_syringe_pump.py:87-90 |
| get_position_steps queries GetSyringePosition and returns the reply parameter in encoder steps | upstream_code | src/runze_control/syringe_pump.py:56-64 |
| get_position_ul converts the step count with the configured syringe volume and max_position_steps | upstream_code | src/runze_control/syringe_pump.py:66-68 |
| get_position_percent scales the step count by max_position_steps | upstream_code | src/runze_control/syringe_pump.py:70-71 |
| aspirate converts microliters to steps with max_position_steps / syringe_volume_ul and sends RunInCCW | upstream_code | src/runze_control/syringe_pump.py:73-77 |
| dispense converts microliters to steps and sends RunInCW | upstream_code | src/runze_control/syringe_pump.py:83-87 |
| reset_syringe_position sets the default speed, sends ResetSyringePosition and SynchronizeSyringePosition, and zeroes the local step count | upstream_code | src/runze_control/syringe_pump.py:41-54 |
| force_stop sends ForceStop and then reads the position | upstream_code | src/runze_control/syringe_pump.py:104-115 |
| set_speed_percent rejects a plunger speed outside 0 to 100 percent | upstream_code | src/runze_control/syringe_pump.py:138-150 |
| get_speed_percent returns the locally stored value, not a device reading | upstream_code | src/runze_control/syringe_pump.py:152-155 |
| get_motor_status returns the reply parameter of GetMotorStatus | upstream_code | src/runze_control/syringe_pump.py:120-123 |
| get_address queries GetAddress and returns the reply parameter | upstream_code | src/runze_control/runze_device.py:170-178 |
| get_rs232_baudrate maps the reply parameter through RS232BaudrateReply, whose codes are 9600, 19200, 38400, 57600 and 115200 bps | upstream_code | src/runze_control/runze_protocol.py:45-53 |
| get_firmware_version returns the major and minor reply bytes as a float | upstream_code | src/runze_control/runze_device.py:145-151 |
| Runze protocol frames use STX 0xCC and ETX 0xDD | upstream_code | src/runze_control/runze_protocol.py:20-23 |
| The default communication timeout is 0.5 s and the long timeout used for syringe moves is 60 s | upstream_code | src/runze_control/runze_device.py:38-42 |
| move_absolute_in_percent rejects a target outside 0 to 100 percent | upstream_code | src/runze_control/multichannel_syringe_pump.py:70-74 |
| move_valve_to_position sends MoveValveToPort with the requested port | upstream_code | src/runze_control/multichannel_syringe_pump.py:38-40 |

Limits: the absolute move target and the plunger speed are 0 to 100 percent, written in the upstream code
(`multichannel_syringe_pump.py:70-74`, `syringe_pump.py:138-150`). The aspirate and dispense volume and the valve
port are `Limit.operator_required`: the usable volume depends on the syringe fitted to the pump, and the valve port
count is one of 6, 9 or 12 for this model (`multichannel_syringe_pump.py:82`) but which one is fitted is a deployment
setting. The operator supplies those envelopes in `site-limits.json`; `site-limits.example.json` shows the overlay
and is an example, not a statement about any pump.

Safety: the e-stop and the safe-state action `x-cap.allenneuraldynamics.runze_stop.v1` both call the native
`force_stop()` (`syringe_pump.py:104-115`). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver. `force_stop`
waits for the device reply and then for a position query, and after connecting the upstream timeout is the 60 s long
timeout (`runze_device.py:38-42`, `runze_device.py:142-143`); the hardware path was not run.

Tags: syringe pump, fluid, serial, multichannel, valve
