"""OpenMHS driver for gh.miked63017/dinolite_uvc_led_control: Dino-Lite USB microscope illumination.

A direct Driver over the upstream worker ``dinoliteuvccontrol.dinoliteuvccontrol:DinoLiteUVCControl``.  The
worker enumerates USB devices with ``lsusb``, keeps one device object per recognised Dino-Lite model in
``ourDevices``, and the user-facing LED, FLC and exposure methods live on those device objects
(dinoliteuvccontrol/dinoliteuvccontrol.py:24-41, README.md:19-25).  This driver selects one device object through
``ourDevices``; it does not enumerate USB itself.

* reads: the last main-LED state this driver commanded (the upstream object does not read the LED back), the FLC
  on/off state and brightness, the auto-exposure state, the current exposure label, the UVC video node and the
  product id;
* six extension actions: main/FLC illumination on/off, the FLC brightness (0 to 6), toggling one of the four FLC
  LEDs, toggling auto exposure, one exposure step (increase or decrease), and an illumination-off safe-state
  action.  The generic UVC controls (Brightness, Contrast, Saturation, Hue, Gamma, Sharpness, ...) are not exposed:
  the driver has no evidence of a single range that covers both supported models, and the upstream standard-control
  setter reports a rejected value only by printing (dinoliteuvccontrol/devices/device0980.py:71-83);
* the safe state is all illumination off.  The upstream ``cleanup()`` is a no-op
  (dinoliteuvccontrol/dinoliteuvccontrol.py:68-69), so this package's ``native.py`` adapter and ``fake.py``
  implement it as the illumination-off stop.  The e-stop calls that adapter; no independent hardware e-stop is
  claimed and no hardware path was run.

The risk is R1 because the device emits LED illumination (MHS/spec/04-safety.md:67); the card floor is R0.  Every
Fact cites a line of the clone at the pinned commit f70a4cedfa1f04fa15d5cdffe2d382851291248a.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

_LIMIT_BRIGHTNESS = Limit(
    min=0, max=6, source="upstream_code",
    ref="dinoliteuvccontrol/devices/device0980.py:128-153")
_LIMIT_LED = Limit(
    min=1, max=4, source="upstream_code",
    ref="dinoliteuvccontrol/devices/device0980.py:175-249")


class DinoliteUvcLedControl(Driver):
    device_id = "dinolite-uvc-led"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "dinoliteuvccontrol.dinoliteuvccontrol:DinoLiteUVCControl"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDinoliteUVCControl"}
    vendor, model = "Dino-Lite", "USB microscope with UVC LED/FLC control"
    display_name = "Dino-Lite UVC LED control (dinoliteuvccontrol.DinoLiteUVCControl)"
    tags = ["microscope", "dinolite", "uvc", "led", "illumination", "flc", "exposure"]
    facts = [
        Fact("DinoLiteUVCControl enumerates USB devices with lsusb, filters vendor id a168, and creates "
             "Device0980 for product 0980 and Device0890 for product 0890 in ourDevices",
             source="upstream_code", ref="dinoliteuvccontrol/dinoliteuvccontrol.py:24-41"),
        Fact("The user constructs DinoLiteUVCControl(args) and reaches the microscopes through worker.ourDevices",
             source="vendor_doc", ref="README.md:19-25"),
        Fact("led_on sends the UVC payload f2010000000000 to selector 4:2",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0980.py:171-173"),
        Fact("led_off sends the UVC payload f2000000000000 to selector 4:2",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0980.py:251-253"),
        Fact("flc_on sends f3010000000000 and flc_off sends f3000000000000 to selector 4:2",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0980.py:113-121"),
        Fact("The 5 MP constructor starts the FLC brightness at 6, and led_dim and led_brighten move it one "
             "level at a time",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0980.py:43-169"),
        Fact("toggle_led_1 through toggle_led_4 turn one of the four FLC LEDs off or on and refuse while FLC is "
             "off", source="upstream_code", ref="dinoliteuvccontrol/devices/device0980.py:175-249"),
        Fact("toggle_auto_exposure turns auto exposure on or off with the UVC payloads 05070003357810 and "
             "05000003357810", source="upstream_code",
             ref="dinoliteuvccontrol/devices/device0980.py:255-277"),
        Fact("The 5 MP exposure settings run from 1/1000s to 16s and the default is key 7 (1/8s)",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0980.py:13-30"),
        Fact("Exposure time can only be changed while auto exposure is off, and increase/decrease move one entry "
             "in the settings", source="upstream_code",
             ref="dinoliteuvccontrol/devices/device0980.py:285-309"),
        Fact("The 1.2 MP model has no FLC: flc_on, flc_off, led_dim, led_brighten and toggle_led_1 through "
             "toggle_led_4 report that FLC is not available",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0890.py:74-100"),
        Fact("The 1.2 MP model's LED on and off payloads are 8001f1 and 8001f0 on UVC selector 4:3",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0890.py:86-104"),
        Fact("The 5 MP constructor turns FLC off and the main LED on at startup",
             source="upstream_code", ref="dinoliteuvccontrol/devices/device0980.py:39-42"),
        Fact("The upstream cleanup() is pass and display_shutdown_message() exits the interpreter; neither is a "
             "device stop", source="upstream_code", ref="dinoliteuvccontrol/dinoliteuvccontrol.py:68-73"),
        Fact("The video node defaults to /dev/video0", source="upstream_code",
             ref="dinoliteuvccontrol/devices/device0980.py:9-10"),
        Fact("Every uvcdynctrl call passes the video node with -d", source="upstream_code",
             ref="dinoliteuvccontrol/devices/device0980.py:71-83"),
        Fact("uvcdynctrl must be installed on the host and this module calls it a lot",
             source="vendor_doc", ref="README.md:68-70"),
    ]
    safe_state = ("all illumination off: the main LED and the FLC are switched off by the package's cleanup "
                  "adapter (the upstream cleanup is a no-op)")

    #: The upstream constructor turns the main LED on (device0980.py:41-42, device0890.py:24); it has no LED
    #: readback, so this is the last state this driver commanded.
    _main_led_on = True

    # -- helpers ----------------------------------------------------------------------------------------------
    def _device(self):
        devices = self.native.ourDevices
        if not devices:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "no Dino-Lite microscope is attached")
        return devices[0]

    @staticmethod
    def _exposure_label(device) -> str:
        settings = getattr(device, "_ae_settings", None)
        key = getattr(device, "_current_exposure_key", None)
        if settings is None or key is None:
            return "unknown"
        labels = list(settings.keys())
        if not isinstance(key, int) or key < 0 or key >= len(labels):
            return "unknown"
        return str(labels[key])

    @staticmethod
    def _require_flc(device):
        if getattr(device, "_flc_status", None) is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "this Dino-Lite model has no FLC illumination (device0890.py:74-84)")
        return device

    # -- reads ------------------------------------------------------------------------------------------------
    @read("main_led_on", type="boolean",
          description="Last main-LED state this driver commanded; the upstream object does not read the LED back")
    def main_led_on(self):
        return bool(self._main_led_on)

    @read("flc_on", type="boolean",
          description="True while the FLC illumination is on (the device object's _flc_status)")
    def flc_on(self):
        return getattr(self._device(), "_flc_status", None) == "on"

    @read("flc_brightness", type="integer", unit="1",
          description="FLC brightness level (0 to 6); 0 on a model without FLC")
    def flc_brightness(self):
        return int(getattr(self._device(), "_flc_led_brightness", 0))

    @read("auto_exposure", type="boolean",
          description="True while automatic exposure is on (the device object's _ae_status)")
    def auto_exposure(self):
        return getattr(self._device(), "_ae_status", "off") == "on"

    @read("exposure_time", type="string",
          description="Current exposure label from the device object's exposure table")
    def exposure_time(self):
        return self._exposure_label(self._device())

    @read("video_device", type="string",
          description="UVC video node the device object passes to uvcdynctrl")
    def video_device(self):
        return str(getattr(self._device(), "vid_address", ""))

    @read("product_id", type="string",
          description="USB product id the worker recognised (0980 or 0890)")
    def product_id(self):
        return str(getattr(self._device(), "product_id", ""))

    # -- illumination -----------------------------------------------------------------------------------------
    @action(name="x-cap.miked63017.set_illumination.v1", risk="R1",
            description="Turn the main LED or the FLC illumination on or off",
            input={
                "channel": Field("string", enum=["main", "flc"],
                                 description="Illumination channel: 'main' for the basic LED, 'flc' for the "
                                             "FLC ring"),
                "on": Field("boolean", description="True to turn the channel on, false to turn it off"),
            },
            output={
                "channel": Field("string", description="The channel that was switched"),
                "on": Field("boolean", description="The state the channel was switched to"),
            })
    def set_illumination(self, channel, on):
        device = self._device()
        if channel == "main":
            if on:
                device.led_on()
            else:
                device.led_off()
            self._main_led_on = bool(on)
        elif channel == "flc":
            self._require_flc(device)
            if on:
                device.flc_on()
            else:
                device.flc_off()
        else:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"unknown illumination channel {channel!r} (main or flc)")
        return {"channel": channel, "on": bool(on)}

    @action(name="x-cap.miked63017.set_flc_brightness.v1", risk="R1",
            description="Set the FLC brightness level (0 to 6); FLC is switched on first when it is off",
            input={
                "level": Field("integer", unit="1",
                               description="FLC brightness level; 0 is the dimmest and 6 the brightest",
                               limit=_LIMIT_BRIGHTNESS),
            },
            output={
                "level": Field("integer", unit="1", description="The FLC brightness level the device holds after "
                                                               "the call"),
            })
    def set_flc_brightness(self, level):
        device = self._require_flc(self._device())
        if getattr(device, "_flc_status", "off") != "on":
            device.flc_on()
        target = int(level)
        for _ in range(6):
            current = int(getattr(device, "_flc_led_brightness", 0))
            if current == target:
                break
            if current < target:
                device.led_brighten()
            else:
                device.led_dim()
        return {"level": int(getattr(device, "_flc_led_brightness", 0))}

    @action(name="x-cap.miked63017.toggle_flc_led.v1", risk="R1",
            description="Toggle one of the four FLC LEDs; FLC is switched on first when it is off",
            input={
                "led": Field("integer", unit="1", description="FLC LED number, 1 to 4",
                             limit=_LIMIT_LED),
            },
            output={
                "led": Field("integer", unit="1", description="The FLC LED number that was toggled"),
                "off": Field("boolean", description="True when the LED is now in the off list of the device "
                                                     "object"),
            })
    def toggle_flc_led(self, led):
        device = self._require_flc(self._device())
        if getattr(device, "_flc_status", "off") != "on":
            device.flc_on()
        toggles = {1: device.toggle_led_1, 2: device.toggle_led_2,
                   3: device.toggle_led_3, 4: device.toggle_led_4}
        number = int(led)
        toggle = toggles.get(number)
        if toggle is None:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"FLC LED {number} is not 1 to 4")
        toggle()
        selected = getattr(device, f"_led{number}", None)
        off = selected in getattr(device, "_listOfLights", [])
        return {"led": number, "off": bool(off)}

    # -- exposure ---------------------------------------------------------------------------------------------
    @action(name="x-cap.miked63017.toggle_auto_exposure.v1",
            description="Toggle automatic exposure on the microscope",
            output={
                "enabled": Field("boolean", description="True when automatic exposure is on after the toggle"),
            })
    def toggle_auto_exposure(self):
        device = self._device()
        device.toggle_auto_exposure()
        return {"enabled": getattr(device, "_ae_status", "off") == "on"}

    @action(name="x-cap.miked63017.step_exposure.v1",
            description="Move one step in the device's exposure table; auto exposure is switched off first",
            input={
                "direction": Field("string", enum=["increase", "decrease"],
                                   description="'increase' for a longer exposure, 'decrease' for a shorter one"),
            },
            output={
                "exposure_time": Field("string", description="Exposure label after the step"),
                "direction": Field("string", description="The direction that was applied"),
            })
    def step_exposure(self, direction):
        device = self._device()
        if getattr(device, "_ae_status", "off") == "on":
            device.toggle_auto_exposure()
        if direction == "increase":
            device.increase_exposure_time()
        elif direction == "decrease":
            device.decrease_exposure_time()
        else:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"unknown exposure direction {direction!r} (increase or decrease)")
        return {"exposure_time": self._exposure_label(device), "direction": direction}

    # -- safety -----------------------------------------------------------------------------------------------
    @action(name="x-cap.miked63017.illumination_off.v1", safe_state=True, risk="R1",
            description="Switch all illumination off (the safe state); it takes no input",
            output={
                "on": Field("boolean", description="False: the illumination is off"),
            })
    def illumination_off(self):
        self.native.cleanup()
        self._main_led_on = False
        return {"on": False}

    @estop(native="cleanup")
    def stop(self):
        """The safe-state stop of this package: the cleanup adapter switches all illumination off."""
        self.native.cleanup()
        self._main_led_on = False
