"""Fake backend of the Dino-Lite driver: an in-memory stand-in for the upstream worker and one 5 MP device.

Gate G7: the public method of the fake class, ``cleanup``, exists on
``dinoliteuvccontrol.dinoliteuvccontrol:DinoLiteUVCControl``
(dinoliteuvccontrol/dinoliteuvccontrol.py:68-69), and ``ourDevices`` is assigned by the upstream __init__
(dinoliteuvccontrol/dinoliteuvccontrol.py:24).  The nested device object mirrors the upstream
``dinoliteuvccontrol/devices/device0980.py`` class: the same state attributes (``_flc_status``,
``_flc_led_brightness``, ``_ae_status``, ``_ae_settings``, ``_current_exposure_key``, ``_listOfLights``,
``vid_address``, ``product_id``) and the same public LED/FLC/exposure methods.  The driver never calls the device
object through the top-level recorder; it reaches it through ``ourDevices``, exactly as the upstream README does
(README.md:19-25).

The upstream ``cleanup`` is a no-op; this fake implements the illumination-off stop of the package's ``native.py``
adapter so the e-stop and the safe-state action have an effect on the fake.  The 2 s sleep of the upstream
toggle_auto_exposure (device0980.py:262) is not reproduced: the fake models the state change, not the timing.  Every
number here is test data, marked ``# placeholder``; none of it is a Fact, a Limit or a reference.
"""

from collections import OrderedDict


class _FakeDevice0980:
    """A stand-in for dinoliteuvccontrol/devices/device0980.py at the pinned clone."""

    def __init__(self):
        self.product_id = "0980"                  # placeholder
        self.vid_address = "/dev/video0"          # placeholder
        self._flc_status = "off"                  # placeholder
        self._flc_led_brightness = 6              # placeholder
        self._led1 = 0x0e                         # placeholder
        self._led2 = 0x0d                         # placeholder
        self._led3 = 0x0b                         # placeholder
        self._led4 = 0x07                         # placeholder
        self._listOfLights = []
        self._led_status = "on"                   # placeholder
        self._ae_settings = OrderedDict([         # placeholder: labels mirror the model table
            ("1/1000s", "05000001357810"),
            ("1/500s", "05010001357810"),
            ("1/250s", "05020001357810"),
            ("1/125s", "05040001357810"),
            ("1/60s", "05080001357810"),
            ("1/30s", "05100001357810"),
            ("1/15s", "0500000d387810"),
            ("1/8s", "051f0001357810"),
            ("1/4s", "0508000c387810"),
            ("1/2s", "053e0001357810"),
            ("1s", "05510035307810"),
            ("2s", "050d000c387810"),
            ("4s", "05610035307810"),
            ("8s", "050f000c387810"),
            ("16s", "0510000c387810"),
        ])
        self._ae_default_key = 7                  # placeholder
        self._current_exposure_key = 7            # placeholder
        self._ae_status = "on"                    # placeholder

    # -- main LED -----------------------------------------------------------------------------------------
    def led_on(self):
        self._led_status = "on"                   # the upstream send is not reproduced

    def led_off(self):
        self._led_status = "off"                  # the upstream send is not reproduced

    # -- FLC ----------------------------------------------------------------------------------------------
    def flc_on(self):
        self._flc_status = "on"
        return "FLC on"

    def flc_off(self):
        self._flc_status = "off"
        return "FLC off"

    def led_dim(self):
        if self._flc_status == "off":
            return
        if self._flc_led_brightness == 0:
            return
        self._flc_led_brightness -= 1

    def led_brighten(self):
        if self._flc_status == "off":
            return
        if self._flc_led_brightness == 6:
            return
        self._flc_led_brightness += 1

    def _toggle(self, code):
        if self._flc_status == "off":
            return
        if code in self._listOfLights:
            self._listOfLights.remove(code)
        else:
            self._listOfLights.append(code)

    def toggle_led_1(self):
        self._toggle(self._led1)

    def toggle_led_2(self):
        self._toggle(self._led2)

    def toggle_led_3(self):
        self._toggle(self._led3)

    def toggle_led_4(self):
        self._toggle(self._led4)

    # -- exposure -----------------------------------------------------------------------------------------
    def toggle_auto_exposure(self):
        if self._ae_status == "on":
            self._ae_status = "off"
            self._current_exposure_key = self._ae_default_key
        else:
            self._ae_status = "on"
            self._current_exposure_key = self._ae_default_key

    def increase_exposure_time(self):
        if self._ae_status == "on":
            return
        if self._current_exposure_key + 1 < len(self._ae_settings):
            self._current_exposure_key += 1

    def decrease_exposure_time(self):
        if self._ae_status == "on":
            return
        if self._current_exposure_key > 0:
            self._current_exposure_key -= 1


class FakeDinoliteUVCControl:
    """The upstream worker with one enumerated 5 MP device; ``cleanup`` is the package stop."""

    def __init__(self, **_options):
        self.ourDevices = [_FakeDevice0980()]

    def cleanup(self):
        for device in self.ourDevices:
            device.led_off()
            device.flc_off()
