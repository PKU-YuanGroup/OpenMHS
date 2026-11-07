# Facts and tags for gh.miked63017/dinolite_uvc_led_control

Every fact cites its source at commit `f70a4cedfa1f04fa15d5cdffe2d382851291248a`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DinoLiteUVCControl enumerates USB devices with lsusb, filters vendor id a168, and creates Device0980 for product 0980 and Device0890 for product 0890 in ourDevices | upstream_code | dinoliteuvccontrol/dinoliteuvccontrol.py:24-41 |
| The user constructs DinoLiteUVCControl(args) and reaches the microscopes through worker.ourDevices | vendor_doc | README.md:19-25 |
| led_on sends the UVC payload f2010000000000 to selector 4:2 | upstream_code | dinoliteuvccontrol/devices/device0980.py:171-173 |
| led_off sends the UVC payload f2000000000000 to selector 4:2 | upstream_code | dinoliteuvccontrol/devices/device0980.py:251-253 |
| flc_on sends f3010000000000 and flc_off sends f3000000000000 to selector 4:2 | upstream_code | dinoliteuvccontrol/devices/device0980.py:113-121 |
| The 5 MP constructor starts the FLC brightness at 6, and led_dim and led_brighten move it one level at a time | upstream_code | dinoliteuvccontrol/devices/device0980.py:43-169 |
| toggle_led_1 through toggle_led_4 turn one of the four FLC LEDs off or on and refuse while FLC is off | upstream_code | dinoliteuvccontrol/devices/device0980.py:175-249 |
| toggle_auto_exposure turns auto exposure on or off with the UVC payloads 05070003357810 and 05000003357810 | upstream_code | dinoliteuvccontrol/devices/device0980.py:255-277 |
| The 5 MP exposure settings run from 1/1000s to 16s and the default is key 7 (1/8s) | upstream_code | dinoliteuvccontrol/devices/device0980.py:13-30 |
| Exposure time can only be changed while auto exposure is off, and increase/decrease move one entry in the settings | upstream_code | dinoliteuvccontrol/devices/device0980.py:285-309 |
| The 1.2 MP model has no FLC: flc_on, flc_off, led_dim, led_brighten and toggle_led_1 through toggle_led_4 report that FLC is not available | upstream_code | dinoliteuvccontrol/devices/device0890.py:74-100 |
| The 1.2 MP model's LED on and off payloads are 8001f1 and 8001f0 on UVC selector 4:3 | upstream_code | dinoliteuvccontrol/devices/device0890.py:86-104 |
| The 5 MP constructor turns FLC off and the main LED on at startup | upstream_code | dinoliteuvccontrol/devices/device0980.py:39-42 |
| The upstream cleanup() is pass and display_shutdown_message() exits the interpreter; neither is a device stop | upstream_code | dinoliteuvccontrol/dinoliteuvccontrol.py:68-73 |
| The video node defaults to /dev/video0 | upstream_code | dinoliteuvccontrol/devices/device0980.py:9-10 |
| Every uvcdynctrl call passes the video node with -d | upstream_code | dinoliteuvccontrol/devices/device0980.py:71-83 |
| uvcdynctrl must be installed on the host and this module calls it a lot | vendor_doc | README.md:68-70 |

## Limits

| input | limit | source | ref |
|---|---|---|---|
| FLC brightness level | 0 to 6 | upstream_code | dinoliteuvccontrol/devices/device0980.py:128-153 |
| FLC LED index | 1 to 4 | upstream_code | dinoliteuvccontrol/devices/device0980.py:175-249 |

No input of this package uses `Limit.operator_required`, so there is no `site-limits.example.json`. The generic UVC
standard controls are not exposed: their ranges are loaded per model from `device0980.json` and `device0890.json`
(the two tables differ), and the upstream setter reports a rejected value only by printing
(dinoliteuvccontrol/devices/device0980.py:71-83). The driver does not invent a range that covers both models.

## Safety

The device emits LED illumination, which MHS/spec/04-safety.md:67 puts at R1; the card floor is R0. The safe state is
all illumination off. The upstream has no stop: `cleanup()` is a no-op and `display_shutdown_message()` exits the
interpreter (dinoliteuvccontrol/dinoliteuvccontrol.py:68-73). The package's `native.py` adapter and `fake.py` therefore
implement `cleanup()` as the illumination-off stop; the `@estop` and the safe-state action
`x-cap.miked63017.illumination_off.v1` call it. No independent hardware e-stop is claimed, no hardware was attached
and the hardware path was never run.

Tags: microscope, dinolite, uvc, led, illumination, flc, exposure
