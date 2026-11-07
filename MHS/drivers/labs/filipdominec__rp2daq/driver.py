"""OpenMHS driver for gh.filipdominec/rp2daq: an RP2DAQ-firmware Raspberry Pi Pico board.

A direct Driver over the upstream class ``rp2daq:Rp2daq``.  The upstream object is a board controller: the
firmware exposes digital GPIO, a 12-bit built-in ADC, PWM and up to 16 A4988-compatible stepper motors.  The
Python class itself defines only ``quit``: at construction ``Rp2daq_internals._register_commands`` parses the C
firmware and attaches one generated method per command to the ``Rp2daq`` object (``rp2daq.py:110-121``).  This
driver calls those documented generated methods (``gpio_out``, ``gpio_in``, ``adc``, ``pwm_configure_pair``,
``pwm_set_value``, ``stepper_init``, ``stepper_move`` and ``stepper_status``).

* reads: the last configured GPIO pin and level, a mean ADC count from channel 0, and the position/motion state
  of stepper 0;
* writes: the GPIO pin and the digital level driven on it;
* actions: an ADC sample, a PWM frequency/duty configuration, a stepper initialization and an absolute or
  relative stepper move;
* the e-stop and the safe-state action both stop every initialized stepper where it is (a relative move of 0, which
  stops a moving stepper at once), zero every PWM output this driver configured and drive every configured GPIO
  output low.  The stepper target position is ``Limit.operator_required``: the firmware bounds it only against a
  32-bit overflow, and the site supplies the travel of its mechanism (``site-limits.example.json``).

The device moves stepper motors, so the package is R2 even though the card floor is R0.  No text file of the clone
documents an independent hardware e-stop, so ``estop_physical_ref`` is not claimed; the safe-state action satisfies
SAFE-045.  The hardware factory is ``native.py`` and is never imported by the acceptance gate.

Every Fact and Limit cites a line of the clone at the pinned commit
``7744f34811d1b3722d30e6efd66205215405fe60``.  The package is model-authored and unreviewed: ``reviewed_by`` is
null, no human reviewed or tested it, and no hardware run is claimed.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The clone files the Facts cite (paths from the clone root).
PY = "rp2daq.py"
GPIO = "include/gpio.c"
ADC = "include/adc_builtin.c"
PWM = "include/pwm.c"
STEPPER = "include/stepper.c"
README = "README.md"

#: The upstream defaults used by the read of channel 0: blocksize 1000, clkdiv 95, channel_mask 1
#: (include/adc_builtin.c:53-57).
ADC_READ_BLOCKSIZE = 1000
ADC_READ_CLKDIV = 95
ADC_READ_CHANNEL_MASK = 1


class Rp2daqBoard(Driver):
    device_id = "rp2daq"
    device_kind = "io.gpio"
    mode = "hardware"
    #: The driver moves stepper motors and drives outputs: real actuation is at least R2 (MHS/spec/04-safety.md:68),
    #: above the card's R0 floor.  The safe-state action below is the independent stop SAFE-045 asks for.
    risk = "R2"
    native = "rp2daq:Rp2daq"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRp2daq"}
    vendor, model = "Filip Dominec", "RP2DAQ board on Raspberry Pi Pico"
    display_name = "RP2DAQ board (rp2daq.Rp2daq)"
    tags = ["rp2040", "rp2350", "daq", "gpio", "adc", "pwm", "stepper", "usb-serial"]
    facts = [
        Fact("Rp2daq is the user-facing object that owns the board connection and delegates the protocol to "
             "Rp2daq_internals", source="upstream_code", ref=f"{PY}:46-54"),
        Fact("The command methods are generated from the C firmware at construction and attached to the Rp2daq "
             "object with setattr; the Python class itself defines only quit", source="upstream_code",
             ref=f"{PY}:110-121"),
        Fact("quit stops the report threads and asks the backend process to release the serial port",
             source="upstream_code", ref=f"{PY}:59-65"),
        Fact("gpio_out connects the selected pin directly to 0 V or 3.3 V and overrides a previous high-Z or pull "
             "state", source="upstream_code", ref=f"{GPIO}:6-24"),
        Fact("gpio_in returns the digital state of a pin; the maximum allowed voltage at any pin is 3.3 V",
             source="upstream_code", ref=f"{GPIO}:94-110"),
        Fact("adc samples the built-in 12-bit ADC and returns a report whose data field is the sample array",
             source="upstream_code", ref=f"{ADC}:31-84"),
        Fact("pwm_configure_pair sets the wrap value and clock divider of a PWM slice; pwm_set_value sets the "
             "duty value of one GPIO", source="upstream_code", ref=f"{PWM}:5-72"),
        Fact("stepper_init configures an A4988-compatible stepper; the endswitch input is documented as a safety "
             "and convenience measure", source="upstream_code", ref=f"{STEPPER}:12-76"),
        Fact("stepper_move moves a stepper to a target in nanosteps (1/256 microstep); speed is in nanosteps per "
             "100 microseconds and its accepted range is 1 to 10000", source="upstream_code",
             ref=f"{STEPPER}:200-246"),
        Fact("stepper_status returns the position, the endswitch state and three 16-bit bitmasks for all 16 "
             "steppers", source="upstream_code", ref=f"{STEPPER}:94-131"),
        Fact("The 12-bit ADC range is about 0 V at count 0 and about 3.2 V at count 4095", source="vendor_doc",
             ref=f"{README}:100"),
        Fact("The firmware identifies its USB serial port by VID:PID 2E8A:000A on RP2040 or 2E8A:0009 on RP2350",
             source="upstream_code", ref=f"{PY}:246-249"),
        Fact("The upstream README drives GPIO 25, the green onboard LED, with gpio_out", source="vendor_doc",
             ref=f"{README}:66-69"),
        Fact("The adc defaults are channel_mask=1, blocksize=1000, clkdiv=95 and trigger_gpio=-1",
             source="upstream_code", ref=f"{ADC}:53-58"),
        Fact("Issuing stepper_move to an already moving stepper stops it immediately", source="vendor_doc",
             ref="docs/PYTHON_REFERENCE.md:467-469"),
        Fact("With relative set to 1 the move is relative to the position of the motor when the command is issued",
             source="upstream_code", ref=f"{STEPPER}:243-244"),
    ]
    safe_state = ("every initialized stepper is held at its current position, PWM outputs are zero and configured "
                  "GPIO outputs are low")

    def __init__(self, **options):
        super().__init__(**options)
        # The firmware has no command that reads back the GPIO or PWM configuration, so the driver remembers the
        # pins it configured.  The start values are the driver's own: pin 25 is the onboard LED used by the
        # upstream README example (README.md:66-69), and level 0 is 0 V.
        self._gpio_pin = 25
        self._gpio_level = 0
        self._gpio_outputs = set()
        self._pwm_outputs = set()

    # -- reads ------------------------------------------------------------------------------------------------
    @read("gpio_pin", type="integer", unit="1",
          description="Last GPIO pin selected for digital output (the firmware has no configuration read-back)")
    def gpio_pin(self):
        return self._gpio_pin

    @read("gpio_level", type="integer", unit="1",
          description="Last digital level driven on gpio_pin (0 or 1)")
    def gpio_level(self):
        return self._gpio_level

    @read("adc_mean", type="number", unit="1",
          description="Mean raw count of one 12-bit ADC block on channel 0 (0 to 4095; README.md:100 relates it "
                      "approximately to volts)")
    def adc_mean(self):
        report = self.native.adc(channel_mask=ADC_READ_CHANNEL_MASK, blocksize=ADC_READ_BLOCKSIZE,
                                 infinite=0, blocks_to_send=1, clkdiv=ADC_READ_CLKDIV,
                                 trigger_gpio=-1, trigger_on_falling_edge=0)
        data = list(report.data)
        if not data:
            return None
        return sum(data) / len(data)

    @read("stepper_position", type="integer", unit="1",
          description="Position of stepper 0 in nanosteps (1/256 microstep)")
    def stepper_position(self):
        return int(self.native.stepper_status(0).nanopos)

    @read("stepper_moving", type="boolean",
          description="True while stepper 0 has a target different from its current position")
    def stepper_moving(self):
        status = self.native.stepper_status(0)
        return bool(status.steppers_moving_bitmask & 1)

    # -- writes -------------------------------------------------------------------------------------------------
    @write("gpio_pin", type="integer", unit="1",
           description="GPIO pin to use for digital output; the pin is first parked in high-impedance state",
           limit=Limit(min=0, max=25, source="upstream_code", ref=f"{GPIO}:16"))
    def set_gpio_pin(self, value):
        pin = int(value)
        self.native.gpio_highz(pin)
        self._gpio_pin = pin
        self._gpio_outputs.discard(pin)
        return pin

    @write("gpio_level", type="integer", unit="1",
           description="Digital level (0 for 0 V, 1 for 3.3 V) driven on the selected gpio_pin",
           limit=Limit(min=0, max=1, source="upstream_code", ref=f"{GPIO}:17"))
    def set_gpio_level(self, value):
        level = int(value)
        self.native.gpio_out(self._gpio_pin, level)
        self._gpio_level = level
        self._gpio_outputs.add(self._gpio_pin)
        return level

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.filipdominec.adc_sample.v1",
            description="Capture one ADC block and return the mean raw count",
            input={
                "channel_mask": Field("integer", unit="1",
                                      description="ADC channel bitmask: 0x01/0x02/0x04 are GPIO26/27/28, "
                                                  "0x08 reference and 0x10 temperature sensor",
                                      limit=Limit(min=1, max=31, source="upstream_code", ref=f"{ADC}:53")),
                "blocksize": Field("integer", unit="1", description="Number of samples in the block",
                                   limit=Limit(min=1, max=8192, source="upstream_code", ref=f"{ADC}:54")),
                "clkdiv": Field("integer", unit="1",
                                description="ADC clock divider; the sampling rate is 48 MHz/(clkdiv+1)",
                                limit=Limit(min=95, max=65535, source="upstream_code", ref=f"{ADC}:57")),
            },
            output={
                "mean_counts": Field("number", unit="1", description="Mean raw 12-bit ADC count of the block"),
                "sample_count": Field("integer", unit="1", description="Number of samples the device reported"),
                "channel_mask": Field("integer", unit="1", description="Channel mask used for the capture"),
            })
    def adc_sample(self, channel_mask, blocksize, clkdiv):
        report = self.native.adc(channel_mask=int(channel_mask), blocksize=int(blocksize), infinite=0,
                                 blocks_to_send=1, clkdiv=int(clkdiv), trigger_gpio=-1,
                                 trigger_on_falling_edge=0)
        data = list(report.data)
        counts = sum(data) / len(data) if data else 0.0
        return {"mean_counts": counts, "sample_count": len(data),
                "channel_mask": int(report.channel_mask)}

    @action(name="x-cap.filipdominec.pwm_set.v1",
            description="Configure a PWM slice and set the duty value of one GPIO",
            input={
                "pin": Field("integer", unit="1", description="GPIO pin for PWM output",
                             limit=Limit(min=0, max=25, source="upstream_code", ref=f"{PWM}:27")),
                "value": Field("integer", unit="1",
                               description="PWM counter value at which the pin switches from high to low",
                               limit=Limit(min=0, max=65535, source="upstream_code", ref=f"{PWM}:60")),
                "wrap_value": Field("integer", unit="1", description="Counter value at which the PWM cycle restarts",
                                    limit=Limit(min=1, max=65535, source="upstream_code", ref=f"{PWM}:28")),
                "clkdiv": Field("integer", unit="1", description="PWM clock divider",
                                limit=Limit(min=1, max=255, source="upstream_code", ref=f"{PWM}:29")),
                "clkdiv_int_frac": Field("integer", unit="1", description="PWM clock divider dithering fraction",
                                         limit=Limit(min=0, max=15, source="upstream_code", ref=f"{PWM}:30")),
                "phase_correct": Field("integer", unit="1",
                                       description="1 doubles the PWM period and centres the two slice waveforms",
                                       limit=Limit(min=0, max=1, source="upstream_code", ref=f"{PWM}:31")),
            },
            output={
                "pin": Field("integer", unit="1", description="GPIO pin configured for PWM"),
                "value": Field("integer", unit="1", description="Duty value applied to the pin"),
                "configured": Field("boolean", description="True once the PWM slice and value were accepted"),
            })
    def pwm_set(self, pin, value, wrap_value, clkdiv, clkdiv_int_frac, phase_correct):
        pin = int(pin)
        self.native.pwm_configure_pair(gpio=pin, wrap_value=int(wrap_value), clkdiv=int(clkdiv),
                                       clkdiv_int_frac=int(clkdiv_int_frac),
                                       phase_correct=int(phase_correct))
        self.native.pwm_set_value(gpio=pin, value=int(value))
        self._pwm_outputs.add(pin)
        return {"pin": pin, "value": int(value), "configured": True}

    @action(name="x-cap.filipdominec.stepper_init.v1",
            description="Initialize one A4988-compatible stepper on two GPIO pins",
            input={
                "stepper_number": Field("integer", unit="1", description="Stepper index (0 to 15)",
                                        limit=Limit(min=0, max=15, source="upstream_code", ref=f"{STEPPER}:30")),
                "dir_gpio": Field("integer", unit="1", description="GPIO pin that selects the direction",
                                  limit=Limit(min=0, max=24, source="upstream_code", ref=f"{STEPPER}:31")),
                "step_gpio": Field("integer", unit="1", description="GPIO pin that emits the microstep pulses",
                                   limit=Limit(min=0, max=24, source="upstream_code", ref=f"{STEPPER}:32")),
                "endswitch_gpio": Field("integer", unit="1",
                                        description="GPIO pin of the end switch, or -1 when no switch is wired",
                                        limit=Limit(min=-1, max=24, source="upstream_code", ref=f"{STEPPER}:33")),
                "disable_gpio": Field("integer", unit="1",
                                      description="GPIO pin of the driver enable input, or -1 when not wired",
                                      limit=Limit(min=-1, max=25, source="upstream_code", ref=f"{STEPPER}:38")),
                "inertia": Field("integer", unit="1",
                                 description="Acceleration/deceleration coefficient; larger is gentler",
                                 limit=Limit(min=0, max=10000, source="upstream_code", ref=f"{STEPPER}:41")),
            },
            output={
                "stepper_number": Field("integer", unit="1", description="Stepper index configured"),
                "initial_nanopos": Field("integer", unit="1", description="Position the stepper was reset to"),
                "initialized": Field("boolean", description="True once the stepper is configured"),
            })
    def stepper_init(self, stepper_number, dir_gpio, step_gpio, endswitch_gpio, disable_gpio, inertia):
        report = self.native.stepper_init(stepper_number=int(stepper_number), dir_gpio=int(dir_gpio),
                                          step_gpio=int(step_gpio), endswitch_gpio=int(endswitch_gpio),
                                          disable_gpio=int(disable_gpio), inertia=int(inertia))
        return {"stepper_number": int(stepper_number), "initial_nanopos": int(report.initial_nanopos),
                "initialized": True}

    @action(name="x-cap.filipdominec.stepper_move.v1",
            description="Move one initialized stepper to an absolute or relative nanostep position",
            input={
                "stepper_number": Field("integer", unit="1", description="Stepper index (0 to 15)",
                                        limit=Limit(min=0, max=15, source="upstream_code", ref=f"{STEPPER}:233")),
                "to": Field("integer", unit="1",
                            description="Target position, or the distance when relative is 1, in nanosteps",
                            limit=Limit.operator_required(
                                "the firmware bounds the position only against a 32-bit overflow (about "
                                "-2_147_000_000 to 2_147_000_000 nanosteps, include/stepper.c:245); the travel of "
                                "the mechanism a stepper drives is the site's, so the site supplies the range")),
                "speed": Field("integer", unit="1",
                               description="Maximum speed in nanosteps per 100 microseconds",
                               limit=Limit(min=1, max=10000, source="upstream_code", ref=f"{STEPPER}:237")),
                "relative": Field("integer", unit="1",
                                  description="1 adds the to value to the current position, 0 treats it as absolute",
                                  limit=Limit(min=0, max=1, source="upstream_code", ref=f"{STEPPER}:243")),
            },
            output={
                "stepper_number": Field("integer", unit="1", description="Stepper index moved"),
                "nanopos": Field("integer", unit="1", description="Position reported after the move"),
                "endswitch_stopped": Field("boolean",
                                           description="True when the end switch stopped the move before the target"),
            })
    def stepper_move(self, stepper_number, to, speed, relative):
        report = self.native.stepper_move(stepper_number=int(stepper_number), to=int(to), speed=int(speed),
                                          relative=int(relative))
        return {"stepper_number": int(stepper_number), "nanopos": int(report.nanopos),
                "endswitch_stopped": bool(report.endswitch_stopped_last_move)}

    @action(name="x-cap.filipdominec.safe_state.v1", safe_state=True,
            description="Stop every initialized stepper at its current position, zero PWM and drive configured "
                        "GPIO outputs low",
            output={
                "stopped": Field("boolean", description="True once the safe-state commands were sent"),
                "steppers_stopped": Field("integer", unit="1", description="Number of steppers held in place"),
                "pwm_zeroed": Field("integer", unit="1", description="Number of PWM pins driven to zero"),
                "gpio_low": Field("integer", unit="1", description="Number of GPIO outputs driven low"),
            })
    def drive_safe_state(self):
        stopped, pwm_zeroed, gpio_low = self._drive_safe_state()
        return {"stopped": True, "steppers_stopped": stopped, "pwm_zeroed": pwm_zeroed, "gpio_low": gpio_low}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Stop every initialized stepper at its current position, zero PWM and drive GPIO outputs low."""
        self._drive_safe_state()

    def _drive_safe_state(self):
        """The native stop sequence: hold initialized steppers, zero PWM, low GPIO.  It never waits for an action.

        A stepper_move to a moving stepper stops it at once (docs/PYTHON_REFERENCE.md:467-469), and a relative move
        of 0 targets the position the motor has when the firmware takes the command (include/stepper.c:243-244), so
        the move finishes where the stepper stopped: no reverse motion, and the report comes back at once.
        """
        status = self.native.stepper_status(0)
        initialized = int(status.steppers_init_bitmask)
        stopped = 0
        for number in range(16):
            if not initialized & (1 << number):
                continue
            self.native.stepper_move(stepper_number=number, to=0, speed=1, relative=1)
            stopped += 1
        for pin in sorted(self._pwm_outputs):
            self.native.pwm_set_value(gpio=pin, value=0)
        for pin in sorted(self._gpio_outputs):
            self.native.gpio_out(pin, 0)
        if self._gpio_outputs:
            self._gpio_level = 0
        return stopped, len(self._pwm_outputs), len(self._gpio_outputs)

    def teardown(self):
        """Release the upstream threads and the serial port (rp2daq.py:59-65)."""
        self.native.quit()
