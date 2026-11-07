# Facts and tags for gh.alexshkarin/pylablib

This card is a driver pack: the repository is a library of many device classes. One package covers one device class,
so this package covers the first entry symbol of the card, `pylablib.devices.Thorlabs.kinesis:KinesisMotor`
(`pylablib/devices/Thorlabs/kinesis.py:1171`), a Thorlabs APT/Kinesis motor controller stage.

Every fact cites its source at commit `96d9504d3e668f18beb3b75503c01b93152dbcd5`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| KinesisMotor is the Thorlabs motor controller class; it implements FTDI chip connectivity via pyft232 (virtual serial interface) | upstream_code | pylablib/devices/Thorlabs/kinesis.py:1173-1175 |
| The physical units are encoder steps for position (ratio to m or degrees depends on the connected stage), steps/sec for velocity, and steps/sec^2 for acceleration | upstream_code | pylablib/devices/Thorlabs/kinesis.py:1177-1178 |
| get_position(scale=False) returns the position in the device internal units (steps) | upstream_code | pylablib/devices/Thorlabs/kinesis.py:440-444 |
| move_to(position, scale=False) sends MOT_MOVE_TO (0x0453) with the position as a 32-bit signed integer | upstream_code | pylablib/devices/Thorlabs/kinesis.py:469-475 |
| stop(immediate=True, sync=False) sends MOT_STOP (0x0465) with parameter 1 (abrupt stop); immediate=False sends parameter 2 | upstream_code | pylablib/devices/Thorlabs/kinesis.py:501-509 |
| is_moving is true when any of moving_fw, moving_bk, jogging_fw, jogging_bk or active is set | upstream_code | pylablib/devices/Thorlabs/kinesis.py:491-496 |
| home(sync=False) sends MOT_HOME (0x0443); is_homing and is_homed read the homing and homed status bits | upstream_code | pylablib/devices/Thorlabs/kinesis.py:388-407 |
| get_status returns the status strings of the status_bits table, which names the hardware and software limit switches, the motion bits, homing, interlock, overtemperature and error | upstream_code | pylablib/devices/Thorlabs/kinesis.py:338-344 |
| get_velocity_parameters(scale=False) returns (min_velocity, acceleration, max_velocity) in device internal units; according to the documentation the minimal velocity is always zero | upstream_code | pylablib/devices/Thorlabs/kinesis.py:517-530 |
| setup_velocity(max_velocity=..., scale=False) writes the velocity parameters and uses the current values for the ones given as None | upstream_code | pylablib/devices/Thorlabs/kinesis.py:531-546 |
| get_device_info returns (serial_no, model_no, fw_ver, hw_type, hw_ver, mod_state, nchannels, notes) and get_number_of_channels returns nchannels | upstream_code | pylablib/devices/Thorlabs/kinesis.py:224-241 |
| get_scale_units reports the scale units in use (deg, m, step, user_step, user or internal); this driver asks every value with scale=False and so always works in device internal units | upstream_code | pylablib/devices/Thorlabs/kinesis.py:1335-1346 |

Limits: `max_velocity` (the write) and `target_position` (the move action) are `Limit.operator_required`. The clone
states the unit of a position (encoder steps) and of a velocity (encoder steps per second) but never the velocity or
travel range of the stage that is mounted on a controller: a Kinesis controller drives different stages, so the range
is a property of the stage, not of the library. `site-limits.example.json` shows an overlay of a site.

Safety: the e-stop and the safe-state action `cap.motion.stop.v1` both call the native `stop(immediate=True)` (MOT_STOP
with the abrupt-stop parameter, kinesis.py:509). No line of the clone documents an independent hardware e-stop; the
package is `risk = "R1"` (the card's floor), so SAFE-045 does not apply.

Mock path: the card's `mock_strategy.preferred` is `upstream-sim`, but its hints are not a device simulator
(`pylablib/core/utils/general.py:401` `DummyResource` is a no-op context manager, and
`pylablib/devices/SiliconSoftware/fgrab_prototyp_defs.py:410` is a camera trigger-mode constant). The clone has no
Kinesis simulator (the only Kinesis test is `tests/devices/test_stages.py:64` and it needs a real device), so this
package ships an in-memory recording fake (`fake.py`).

Not covered by this package (driver pack, one class per package):

- `pylablib.devices.Andor.AndorSDK2:AndorSDK2Camera` (pylablib/devices/Andor/AndorSDK2.py:81), an Andor SDK2 camera;
- `pylablib.devices.IDS.peak:IDSPeakCamera` (pylablib/devices/IDS/peak.py:1141), an IDS peak camera;
- `pylablib.devices.AlliedVision.VimbaX:AlliedVisionVimbaXCamera` (pylablib/devices/AlliedVision/VimbaX.py:292),
  an Allied Vision Vimba X camera;
- `pylablib.devices.PrincetonInstruments.picam:PicamCamera`
  (pylablib/devices/PrincetonInstruments/picam.py:285), a Princeton Instruments Picam camera.
- Inside the Kinesis controller this package uses the default channel only: it reads the channel count but never selects
  another channel, and it does not cover jog, move-by, the position reference, the limit-switch and trigger setup, or
  the piezo classes of the module.

Tags: motor, stage, thorlabs, apt, kinesis, motion
