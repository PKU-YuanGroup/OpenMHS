"""Fake backend of the Acton driver: an in-memory stand-in for ``acton_spec_interface:ActonSpectrometer``.

Gate G7: every public method defined here exists on ``acton_spec_interface:ActonSpectrometer`` at the pinned commit.
The wire protocol, the serial port and the reply parsers of the clone are not reproduced; this fake only keeps the
state the driver reads and answers the native methods the driver calls.  Every starting value and every grating
name below is test data (marked ``# placeholder``), not a fact or a limit about a device.  Reading the state twice
gives the same state, and nothing here talks to hardware.

The upstream ``read_grating_name`` reads the current grating and returns the ``(number, name)`` entry
(acton_spec_interface.py:99-106); the fake mirrors that shape.  ``close`` is the native e-stop of the driver.
"""


class FakeActonSpectrometer:
    """In-memory spectrometer; the public methods mirror the ones the driver calls on the upstream class."""

    def __init__(self, **_options):
        self._closed = False
        self._wl = 500.000                     # placeholder, nm
        self._done = True                      # placeholder, the last move is done
        self._grating = 1                      # placeholder, current grating number
        self._turret = 1                       # placeholder, current turret number
        self._exit_mirror = "SIDE"             # placeholder, exit mirror position
        self._entrance_slit = 100              # placeholder, um
        self._exit_slit = 100                  # placeholder, um
        #: Test grating table: three installed gratings and the uninstalled slots the clone's example lists.  # placeholder
        self.gratings = [
            (1, "300 g/mm BLZ=500NM"),         # placeholder
            (2, "300 g/mm BLZ=1.0UM"),         # placeholder
            (3, "150 g/mm BLZ=500NM"),         # placeholder
            (4, "Not Installed"),              # placeholder
            (5, "Not Installed"),              # placeholder
            (6, "Not Installed"),              # placeholder
            (7, "Not Installed"),              # placeholder
            (8, "Not Installed"),              # placeholder
            (9, "Not Installed"),              # placeholder
        ]

    # -- the serial interface methods the driver calls ------------------------------------------------------------
    def read_done_status(self):
        return self._done

    def read_wl(self):
        return self._wl

    def write_wl_fast(self, wl, waittime=1.0):
        self._wl = float(f"{float(wl):.3f}")   # placeholder, the upstream sends three decimals
        self._done = True                      # placeholder

    def read_grating(self):
        return self._grating

    def write_grating(self, grating):
        assert 0 < grating < 10
        self._grating = int(grating)

    def read_grating_name(self):
        self.read_grating()
        return self.gratings[self._grating - 1]

    def read_turret(self):
        return self._turret

    def read_exit_mirror(self):
        return self._exit_mirror

    def write_exit_mirror(self, pos):
        pos = pos.upper()
        assert pos in ["FRONT", "SIDE"]
        self._exit_mirror = pos

    def read_entrance_slit(self):
        return self._entrance_slit

    def write_entrance_slit(self, pos):
        assert 5 <= pos <= 3000
        self._entrance_slit = int(pos)

    def read_exit_slit(self):
        return self._exit_slit

    def write_exit_slit(self, pos):
        assert 5 <= pos <= 3000
        self._exit_slit = int(pos)

    def close(self):
        self._closed = True
