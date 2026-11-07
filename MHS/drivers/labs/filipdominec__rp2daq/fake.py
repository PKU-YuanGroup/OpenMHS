"""Fake backend of the RP2DAQ driver: an in-memory stand-in for rp2daq:Rp2daq.

Gate G7: every public method defined here is a command name the clone's C firmware defines and the upstream
``Rp2daq_internals._register_commands`` attaches to the Rp2daq object (rp2daq.py:110-121): ``adc``,
``gpio_highz``, ``gpio_out``, ``pwm_configure_pair``, ``pwm_set_value``, ``stepper_init``, ``stepper_move``,
``stepper_status`` and ``quit``.  The fake keeps plain state and talks to nothing.  Every fixed number below is
test data (``# placeholder``), not a fact, a limit or a citation.
"""

from types import SimpleNamespace


def _report(**values):
    """The namedtuple-like report object a generated command returns."""
    return SimpleNamespace(**values)


class FakeRp2daq:
    def __init__(self, **_options):
        self._open = True
        self._pins = {}                 # pin -> digital level, only for pins driven by gpio_out
        self._pwm_config = {}           # pin -> (wrap_value, clkdiv, clkdiv_int_frac, phase_correct)
        self._pwm_values = {}           # pin -> duty value
        self._steppers = [
            # placeholder: the start position, pins and inertia are canned test values
            {"initialized": False, "nanopos": 0, "target": 0, "dir_gpio": 0, "step_gpio": 0,
             "endswitch_gpio": -1, "disable_gpio": -1, "inertia": 30}
            for _ in range(16)  # placeholder: 16 stepper slots
        ]
        # placeholder: four canned ADC counts; the real command returns `blocksize` samples
        self._adc_counts = [2048, 2050, 2046, 2052]

    # -- digital GPIO -------------------------------------------------------------------------------------------
    def gpio_out(self, gpio, value):
        self._pins[int(gpio)] = int(value)
        return None

    def gpio_highz(self, gpio):
        self._pins.pop(int(gpio), None)
        return None

    # -- ADC ----------------------------------------------------------------------------------------------------
    def adc(self, channel_mask=1, blocksize=1000, infinite=0, blocks_to_send=1, clkdiv=95,
            trigger_gpio=-1, trigger_on_falling_edge=0):
        # placeholder: the default arguments and the report fields below are canned test data; the fake returns at
        # most four samples, not the requested blocksize
        data = list(self._adc_counts)[: max(1, min(int(blocksize), len(self._adc_counts)))]
        return _report(report_code=6, data_count=len(data), data_bitwidth=12, start_time_us=0,
                       end_time_us=0, start_sync_value=0, end_sync_value=0,
                       channel_mask=int(channel_mask), blocks_to_send=0, block_delayed_by_usb=0,
                       data=data)

    # -- PWM ----------------------------------------------------------------------------------------------------
    def pwm_configure_pair(self, gpio=0, wrap_value=999, clkdiv=1, clkdiv_int_frac=0, phase_correct=0):
        # placeholder: the default arguments are canned test data
        self._pwm_config[int(gpio)] = (int(wrap_value), int(clkdiv), int(clkdiv_int_frac),
                                       int(phase_correct))
        return None

    def pwm_set_value(self, gpio=0, value=0):
        # placeholder: the default arguments are canned test data
        self._pwm_values[int(gpio)] = int(value)
        return None

    # -- steppers -----------------------------------------------------------------------------------------------
    def stepper_init(self, stepper_number=0, dir_gpio=0, step_gpio=0, endswitch_gpio=-1,
                     disable_gpio=-1, inertia=30):
        # placeholder: the default arguments and the report fields below are canned test data
        number = int(stepper_number)
        stepper = self._steppers[number]
        stepper.update({"initialized": True, "nanopos": 0, "target": 0, "dir_gpio": int(dir_gpio),
                        "step_gpio": int(step_gpio), "endswitch_gpio": int(endswitch_gpio),
                        "disable_gpio": int(disable_gpio), "inertia": int(inertia)})
        return _report(report_code=11, initial_nanopos=0)

    def stepper_move(self, stepper_number=0, to=0, speed=1, endswitch_sensitive_up=0,
                     endswitch_sensitive_down=1, relative=0, reset_nanopos_at_endswitch=0):
        # placeholder: the default arguments and the report fields below are canned test data
        number = int(stepper_number)
        stepper = self._steppers[number]
        target = int(to) if not int(relative) else stepper["nanopos"] + int(to)
        stepper["nanopos"] = target
        stepper["target"] = target
        return _report(report_code=12, stepper_number=number, nanopos=int(stepper["nanopos"]),
                       endswitch_was_sensitive=0, endswitch_stopped_last_move=0,
                       steppers_init_bitmask=self._init_mask(), steppers_moving_bitmask=0,
                       steppers_endswitch_bitmask=0, start_time_us=0, end_time_us=0)

    def stepper_status(self, stepper_number=0):
        # placeholder: the default argument and the report fields below are canned test data
        number = int(stepper_number)
        stepper = self._steppers[number]
        moving = 0
        for index, item in enumerate(self._steppers):
            if item["initialized"] and item["nanopos"] != item["target"]:
                moving |= 1 << index
        return _report(report_code=13, timestamp_us=0, stepper_number=number, endswitch=0,
                       nanopos=int(stepper["nanopos"]), steppers_init_bitmask=self._init_mask(),
                       steppers_moving_bitmask=moving, steppers_endswitch_bitmask=0)

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def quit(self):
        self._open = False
        return None

    # -- internal helpers ---------------------------------------------------------------------------------------
    def _init_mask(self):
        mask = 0
        for index, item in enumerate(self._steppers):
            if item["initialized"]:
                mask |= 1 << index
        return mask
