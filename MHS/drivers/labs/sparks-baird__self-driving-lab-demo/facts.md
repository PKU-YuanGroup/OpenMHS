# Facts and tags for gh.sparks-baird/self-driving-lab-demo

This package drives the nonwireless CLSLab:Light Pico demo: one addressable NeoPixel on pin 28 and one AS7341
eight-channel spectrometer, reached through the serial class `extra.nonwireless.lib.host_nonwireless:Talker`.
Every fact cites its source at commit `051e91e34b63e5ce357df3db7e7425186c5c635c`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The nonwireless host helper opens the serial port at 115200 baud and writes set_color(R, G, B) and read_sensor(astep, atime, gain) lines, reading one reply line and one extra line | upstream_code | src/self_driving_lab_demo/utils/observe.py:362-386 |
| Talker appends CR FF to the command text, reads the echoed line, strips a '>>> ' prompt and raises ValueError when the echo differs | upstream_code | src/extra/nonwireless/lib/host_nonwireless.py:12-20 |
| Talker.receive reads to a CR terminator and strips the line | upstream_code | src/extra/nonwireless/lib/host_nonwireless.py:22-24 |
| The nonwireless Pico's set_color writes one NeoPixel on pin 28; read_sensor sets ASTEP, ATIME and gain and returns every channel | upstream_code | src/extra/nonwireless/main.py:10-24 |
| The nonwireless firmware's startup sequence ends with set_color(0, 0, 0), so the LED is off after boot | upstream_code | src/extra/nonwireless/main.py:27-32 |
| The eight AS7341 channels are ch410, ch440, ch470, ch510, ch550, ch583, ch620 and ch670 | upstream_code | src/self_driving_lab_demo/utils/channel_info.py:26-35 |
| The nominal channel centres are 410, 440, 470, 510, 550, 583, 620 and 670 nm | upstream_code | src/self_driving_lab_demo/utils/channel_info.py:3-11 |
| Sensor.all_channels runs an F1F4CN and an F5F8CN measurement and returns the eight values f1 to f8 | upstream_code | src/extra/nonwireless/lib/as7341_sensor.py:100-109 |
| The total integration time is (ASTEP + 1) * (ATIME + 1) * 2.78 / 1000 ms | upstream_code | src/extra/nonwireless/lib/as7341.py:491-500 |
| The host asserts atime 0 to 255, astep 0 to 65534 and gain 0.5 to 512 | upstream_code | src/self_driving_lab_demo/utils/observe.py:76-78 |
| The AS7341 gain code runs from 0 to 10 and maps to the factors 0.5, 1, 2, ..., 512 | upstream_code | src/extra/nonwireless/lib/as7341.py:502-505 |
| The MQTT firmware for the same Pico asserts that R, G and B are each between 0 and 255 | upstream_code | src/public_mqtt_sdl_demo/main.py:163-165 |
| The nonwireless firmware parser reads one line, splits it on parentheses and dispatches set_color and read_sensor | upstream_code | src/extra/nonwireless/main.py:38-51 |
| The nonwireless firmware's read_sensor branch unpacks two arguments and then calls a three-argument read_sensor | upstream_code | src/extra/nonwireless/main.py:48-50 |

## Limits

| field | bound | source | ref |
|---|---|---|---|
| color (R, G, B) | 0 to 255 each | upstream_code | src/public_mqtt_sdl_demo/main.py:163-165 |
| atime | 0 to 255 | upstream_code | src/self_driving_lab_demo/utils/observe.py:76 |
| astep | 0 to 65534 | upstream_code | src/self_driving_lab_demo/utils/observe.py:77 |
| gain | 0.5 to 512 | upstream_code | src/self_driving_lab_demo/utils/observe.py:78 |

No bound is supplied by an operator; this package has no `site-limits.example.json`.

## Safety

The device emits light through one addressable LED and observes through the AS7341; it has no laser, pump, heater,
motion stage or high voltage in this demo. The package is R1, above the card's R0 floor, because the generic
`cap.device.configure.v1` class carries an R1 floor. The e-stop sends `set_color(0, 0, 0)` through the native
`send` path, which is the safe state. The package is model-authored and unreviewed; no hardware was attached or run.

## Tags

spectrometer, as7341, neopixel, led, serial, self-driving-lab, color-matching
