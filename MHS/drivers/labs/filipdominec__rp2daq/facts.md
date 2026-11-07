# Facts and tags for gh.filipdominec/rp2daq

Every fact cites its source at commit `7744f34811d1b3722d30e6efd66205215405fe60`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a C or Python file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Rp2daq is the user-facing object that owns the board connection and delegates the protocol to Rp2daq_internals | upstream_code | rp2daq.py:46-54 |
| The command methods are generated from the C firmware at construction and attached to the Rp2daq object with setattr; the Python class itself defines only quit | upstream_code | rp2daq.py:110-121 |
| quit stops the report threads and asks the backend process to release the serial port | upstream_code | rp2daq.py:59-65 |
| gpio_out connects the selected pin directly to 0 V or 3.3 V and overrides a previous high-Z or pull state | upstream_code | include/gpio.c:6-24 |
| gpio_in returns the digital state of a pin; the maximum allowed voltage at any pin is 3.3 V | upstream_code | include/gpio.c:94-110 |
| adc samples the built-in 12-bit ADC and returns a report whose data field is the sample array | upstream_code | include/adc_builtin.c:31-84 |
| pwm_configure_pair sets the wrap value and clock divider of a PWM slice; pwm_set_value sets the duty value of one GPIO | upstream_code | include/pwm.c:5-72 |
| stepper_init configures an A4988-compatible stepper; the endswitch input is documented as a safety and convenience measure | upstream_code | include/stepper.c:12-76 |
| stepper_move moves a stepper to a target in nanosteps (1/256 microstep); speed is in nanosteps per 100 microseconds and its accepted range is 1 to 10000 | upstream_code | include/stepper.c:200-246 |
| stepper_status returns the position, the endswitch state and three 16-bit bitmasks for all 16 steppers | upstream_code | include/stepper.c:94-131 |
| The 12-bit ADC range is about 0 V at count 0 and about 3.2 V at count 4095 | vendor_doc | README.md:100 |
| The firmware identifies its USB serial port by VID:PID 2E8A:000A on RP2040 or 2E8A:0009 on RP2350 | upstream_code | rp2daq.py:246-249 |
| The upstream README drives GPIO 25, the green onboard LED, with gpio_out | vendor_doc | README.md:66-69 |
| The adc defaults are channel_mask=1, blocksize=1000, clkdiv=95 and trigger_gpio=-1 | upstream_code | include/adc_builtin.c:53-58 |

## Limits

Each bound is attached once to the input it bounds in `driver.py`; the cited line states it in the clone.

| input | bound | source | ref |
|---|---|---|---|
| gpio_pin | 0 to 25 | upstream_code | include/gpio.c:16 |
| gpio_level | 0 to 1 | upstream_code | include/gpio.c:17 |
| adc_sample.channel_mask | 1 to 31 | upstream_code | include/adc_builtin.c:53 |
| adc_sample.blocksize | 1 to 8192 | upstream_code | include/adc_builtin.c:54 |
| adc_sample.clkdiv | 95 to 65535 | upstream_code | include/adc_builtin.c:57 |
| pwm_set.pin | 0 to 25 | upstream_code | include/pwm.c:27 |
| pwm_set.value | 0 to 65535 | upstream_code | include/pwm.c:60 |
| pwm_set.wrap_value | 1 to 65535 | upstream_code | include/pwm.c:28 |
| pwm_set.clkdiv | 1 to 255 | upstream_code | include/pwm.c:29 |
| pwm_set.clkdiv_int_frac | 0 to 15 | upstream_code | include/pwm.c:30 |
| pwm_set.phase_correct | 0 to 1 | upstream_code | include/pwm.c:31 |
| stepper_init.stepper_number | 0 to 15 | upstream_code | include/stepper.c:30 |
| stepper_init.dir_gpio | 0 to 24 | upstream_code | include/stepper.c:31 |
| stepper_init.step_gpio | 0 to 24 | upstream_code | include/stepper.c:32 |
| stepper_init.endswitch_gpio | -1 to 24 | upstream_code | include/stepper.c:33 |
| stepper_init.disable_gpio | -1 to 25 | upstream_code | include/stepper.c:38 |
| stepper_init.inertia | 0 to 10000 | upstream_code | include/stepper.c:41 |
| stepper_move.stepper_number | 0 to 15 | upstream_code | include/stepper.c:233 |
| stepper_move.to | `Limit.operator_required`: the firmware bounds the position only against a 32-bit overflow (-2_147_000_000 .. 2_147_000_000, include/stepper.c:245); the site supplies the travel | operator | site-limits.example.json |
| stepper_move.speed | 1 to 10000 | upstream_code | include/stepper.c:237 |
| stepper_move.relative | 0 to 1 | upstream_code | include/stepper.c:243 |

One bound is `Limit.operator_required` (the stepper target position); `site-limits.example.json` shows the overlay.

## Safety

The device moves stepper motors, so the package is R2 above the card's R0 floor. The `@estop` method and the
safe-state action `x-cap.filipdominec.safe_state.v1` both call the same native sequence: `stepper_status(0)` reads the
initialized mask, each initialized stepper is moved to its current position, configured PWM outputs are set to zero and
configured GPIO outputs are driven low. The clone documents an endswitch input as a safety measure
(include/stepper.c:33-37) but no independent hardware e-stop, so `estop_physical_ref` is not set and SAFE-045 is
satisfied by the safe-state action. This package is model-authored and unreviewed; `reviewed_by` stays null and no
hardware run is claimed.

Tags: rp2040, rp2350, daq, gpio, adc, pwm, stepper, usb-serial
