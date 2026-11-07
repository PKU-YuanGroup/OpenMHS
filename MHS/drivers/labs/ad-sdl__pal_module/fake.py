"""Fake backend of the PAL3 driver: an in-memory stand-in for ``PAL3_driver:PALService``.

Gate G7: every method defined here exists on ``PAL3_driver:PALService`` in the clone
(``get_current_pos`` at PAL3_driver.py:909, ``move_absolute`` at :950, ``move_relative`` at :965, ``safe_home`` at
:1024, ``gripper_distance`` at :1890, ``set_vial`` at :863, ``move_gripper`` at :1829, ``clean_wash`` at :1140,
``stop_remote_service`` at :701, ``start_remote_service`` at :682 and ``shutdown`` at :705), and the attributes the
driver reads (``x``, ``y``, ``z``, ``vial``, ``remote_service``) are set by the upstream class.  The nested
``remote_service`` is only modelled enough for the upstream ``IsConnected``/``Disconnect`` use.

Every starting number, address and reply below is test data (``# placeholder``), not a fact about a PAL3 rail and not
a copied constructor default.  The fake does not model motion, forces, timing, the gripper hardware or the remote
protocol; it does not prove that disconnecting the remote service stops an arm.  Nothing here opens a .NET assembly,
a network connection or a device.
"""

#: Test occupancy of the example rack (# placeholder: the real rack is configured in PAL).
OCCUPIED = {
    "Tray Holder 1:Slot1:1",  # placeholder
    "Tray Holder 1:Slot1:2",  # placeholder
}

#: Test home position in millimetres (# placeholder: the PAL3 home switch sets the real reference).
HOME_POSITION = (0.0, 0.0, 0.0)  # placeholder

#: Test starting position in millimetres (# placeholder: not a device coordinate).
START_POSITION = (100.0, 100.0, 100.0)  # placeholder

#: Test gripper adapter distances in millimetres (# placeholder: the PALGripper width/release defaults are test data
#: here; the closure threshold is an upstream mechanism with no cited range).
GRIPPER_OPEN_MM = 15.0  # placeholder
GRIPPER_CLOSED_MM = 4.2  # placeholder


class _FakeRemoteService:
    """The nested IRemoteService face the upstream stop/start pair uses (IsConnected, Disconnect)."""

    def __init__(self):
        self.IsConnected = True

    def Disconnect(self):
        self.IsConnected = False

    def Connect(self):
        self.IsConnected = True


class _FakeVial:
    """The vial object set_vial returns: the driver only hands it back to move_gripper."""

    def __init__(self, address):
        self.address = address


class FakePALService:
    def __init__(self, **_options):
        self.x, self.y, self.z = START_POSITION  # placeholder
        self.vial = None
        self.remote_service = _FakeRemoteService()
        self._occupied = set(OCCUPIED)  # placeholder occupancy
        self._gripper_open = True
        self._wash_calls = 0  # placeholder counter
        self._shutdown = False

    # -- position ------------------------------------------------------------------------------------------------
    def get_current_pos(self):
        return None

    def move_absolute(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        return None

    def move_relative(self, dx, dy, dz):
        self.x += float(dx)
        self.y += float(dy)
        self.z += float(dz)
        return None

    def safe_home(self):
        self.x, self.y, self.z = HOME_POSITION  # placeholder
        return None

    def gripper_distance(self):
        return GRIPPER_OPEN_MM if self._gripper_open else GRIPPER_CLOSED_MM  # placeholder

    # -- vials and gripper ---------------------------------------------------------------------------------------
    def set_vial(self, address):
        self.vial = _FakeVial(str(address))
        return self.vial

    def move_gripper(self, v1, v2):
        if v1 is None or v2 is None:
            return 1
        if v2.address in self._occupied:
            return 1
        if v1.address not in self._occupied:
            return 1
        self._occupied.discard(v1.address)
        self._occupied.add(v2.address)
        self.vial = None
        self._gripper_open = False
        return 0

    # -- maintenance ---------------------------------------------------------------------------------------------
    def clean_wash(self):
        self._wash_calls += 1
        return None

    # -- remote service ------------------------------------------------------------------------------------------
    def stop_remote_service(self):
        if self.remote_service.IsConnected:
            self.remote_service.Disconnect()
        return None

    def start_remote_service(self):
        self.remote_service.Connect()
        return None

    def shutdown(self):
        self._shutdown = True
        return None
