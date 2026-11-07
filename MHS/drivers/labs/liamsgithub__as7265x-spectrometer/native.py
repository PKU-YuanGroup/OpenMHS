"""Hardware backend: a Python 3 port of the clone's AS7265x module functions over I2C.

The upstream clone is a Python 2.7 module that imports ``smbus`` and constructs ``SMBus(1)`` at import time
(``spectrometer.py:5`` and ``spectrometer.py:20``); it cannot be imported by the Python 3 runtime.  This module is
an independent port of the same public functions; it neither imports nor runs the clone.  It is used only with
``backend="hardware"`` and an operator's hardware allowance, and it was never run: no hardware was attached.

This package is R1 and model-authored, so the loader does not refuse its hardware backend the way it refuses an
unreviewed R2 or R3 package.  That is not a safety claim: the stop is the native LED-off path in ``driver.py``
(the upstream ``setBlueLED`` and ``shutterLED`` functions), not a hardware e-stop.  ``smbus`` is provided by the
operating system (for example the ``python3-smbus`` package on a Raspberry Pi); the package does not install it.

The register addresses, status bits and polling delay are the clone's (``spectrometer.py:10-19``).  The bus number
and address defaults are the clone's ``SMBus(1)`` and ``0x49`` (``spectrometer.py:10, 20``), not limits of a device.

Bus ownership (added by the 2026-11-04 model review; the clone is single-threaded and has none of it):

* every virtual-register transaction (the status polls plus one register read or write of ``spectrometer.py:29-83``)
  runs under one re-entrant bus lock, so a stop issued from another thread never interleaves inside a
  transaction;
* a read-modify-write of a register (the LED, drive-current and gain setters, ``spectrometer.py:208-318``) holds the
  lock across its read and its write, so a concurrent stop cannot be overwritten by a stale value;
* device selection (register 0x4F, ``spectrometer.py:120-132``) is remembered per calling thread, and a transaction
  re-selects that thread's device when another thread selected a different one in between, so a stop that selects
  AS72651 cannot redirect a running measurement to the wrong device;
* every wait for TX_VALID or RX_VALID ends after ``poll_timeout_s`` seconds (the clone polls forever,
  ``spectrometer.py:35-51, 63-80``) and every wait for the bus lock after ``lock_timeout_s`` seconds; both raise
  ``TimeoutError``.  These are host timeouts of this port, not device limits.

What this does not bound: a single ``read_byte_data``/``write_byte_data`` call that blocks inside the operating
system's I2C driver cannot be interrupted from Python.  A stop that meets such a call fails with ``TimeoutError``
after ``lock_timeout_s`` and the runtime keeps its latch (``MHS.SAFETY.SAFE_STATE_UNREACHED``).
"""

import struct
import threading
import time

I2C_ADDR = 0x49
STATUS_REG = 0x00
WRITE_REG = 0x01
READ_REG = 0x02
TX_VALID = 0x02
RX_VALID = 0x01
POLLING_DELAY = 0.05
DEVSEL_REG = 0x4F
DEVICES = ("AS72651", "AS72652", "AS72653")
REORDER = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (13, 9), (14, 11), (9, 10),
           (10, 12), (15, 13), (16, 14), (17, 15), (18, 16), (11, 17), (12, 18)]
RAW_REGISTERS = [(0x08, 0x09), (0x0A, 0x0B), (0x0C, 0x0D), (0x0E, 0x0F), (0x10, 0x11), (0x12, 0x13)]
CAL_REGISTERS = [(0x14, 0x15, 0x16, 0x17), (0x18, 0x19, 0x1A, 0x1B), (0x1C, 0x1D, 0x1E, 0x1F),
                 (0x20, 0x21, 0x22, 0x23), (0x24, 0x25, 0x26, 0x27), (0x28, 0x29, 0x2A, 0x2B)]
DEVSEL_BITS = {"AS72651": 0b00, "AS72652": 0b01, "AS72653": 0b10}

#: Host bound of one wait for a status bit; the clone polls forever.  Not a device limit.
POLL_TIMEOUT_S = 1.0
#: Host bound of one wait for the bus lock (another thread's transaction).  Not a device limit.
LOCK_TIMEOUT_S = 2.0


def connect(bus=1, address=I2C_ADDR, **_options):
    """Open the SMBus and return the port object the driver calls."""
    import smbus  # provided by the operating system; never installed by the gate

    return AS7265x(smbus.SMBus(int(bus)), int(address))


class AS7265x:
    def __init__(self, bus, address=I2C_ADDR, *, poll_timeout_s=POLL_TIMEOUT_S, lock_timeout_s=LOCK_TIMEOUT_S,
                 clock=time.monotonic, sleep=time.sleep):
        self._bus = bus
        self._address = int(address)
        self._poll_timeout_s = float(poll_timeout_s)
        self._lock_timeout_s = float(lock_timeout_s)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.RLock()
        self._wanted = threading.local()
        self._selected = None  # the device register 0x4F was last written with; unknown until then

    # -- bus ownership --------------------------------------------------------------------------------------------
    def _owned(self):
        """Acquire the bus lock within ``lock_timeout_s`` (re-entrant for the owning thread)."""
        if not self._lock.acquire(timeout=self._lock_timeout_s):
            raise TimeoutError(f"the AS7265x bus stayed owned by another transaction for {self._lock_timeout_s} s")
        return _Release(self._lock)

    def _coherent(self):
        """Re-select the calling thread's device if another thread selected a different one (lock held)."""
        wanted = getattr(self._wanted, "device", None)
        if wanted is not None and wanted != self._selected:
            self._raw_write(DEVSEL_REG, DEVSEL_BITS[wanted])
            self._selected = wanted

    # -- low level ------------------------------------------------------------------------------------------------
    def _status(self):
        return int(self._bus.read_byte_data(self._address, STATUS_REG))

    def _wait(self, mask, wanted_set, what):
        deadline = self._clock() + self._poll_timeout_s
        while True:
            if bool(self._status() & mask) == wanted_set:
                return
            if self._clock() >= deadline:
                raise TimeoutError(f"the AS7265x did not {what} within {self._poll_timeout_s} s")
            self._sleep(POLLING_DELAY)

    def _raw_read(self, addr):
        if (self._status() & RX_VALID) != 0:
            self._bus.read_byte_data(self._address, READ_REG)  # drain a stale byte (spectrometer.py:31-33)
        self._wait(TX_VALID, False, "clear TX_VALID")
        self._bus.write_byte_data(self._address, WRITE_REG, int(addr))
        self._wait(RX_VALID, True, "set RX_VALID")
        return int(self._bus.read_byte_data(self._address, READ_REG))

    def _raw_write(self, addr, data):
        self._wait(TX_VALID, False, "clear TX_VALID")
        self._bus.write_byte_data(self._address, WRITE_REG, int(addr) | 0x80)
        self._wait(TX_VALID, False, "clear TX_VALID")
        self._bus.write_byte_data(self._address, WRITE_REG, int(data) & 0xFF)

    def readReg(self, addr):
        with self._owned():
            self._coherent()
            return self._raw_read(addr)

    def writeReg(self, addr, data):
        with self._owned():
            self._coherent()
            self._raw_write(addr, data)

    def setDEVSEL(self, device):
        if device not in DEVSEL_BITS:
            return False
        self._wanted.device = device
        with self._owned():
            self._raw_write(DEVSEL_REG, DEVSEL_BITS[device])
            self._selected = device
        return True

    def _modify(self, device, register, change):
        """One atomic read-modify-write of ``register`` on ``device`` (the bus lock spans the read and the write)."""
        self._wanted.device = device
        with self._owned():
            self._coherent()
            current = self._raw_read(register)
            self._raw_write(register, change(current))

    # -- spec functions -------------------------------------------------------------------------------------------
    def init(self):
        self.writeReg(0x04, 1)
        self._sleep(4)  # the clone waits for the on-board firmware after the factory reset (spectrometer.py:158)

    def boardPresent(self):
        try:
            self.readReg(0x00)
            return True
        except Exception:  # noqa: BLE001 - the clone reports an absent board as False (spectrometer.py:167-172)
            return False

    def hwVersion(self):
        return (self.readReg(0x00), self.readReg(0x01))

    def swVersion(self):
        return None

    def temperatures(self):
        values = []
        for device in DEVICES:
            self.setDEVSEL(device)
            values.append(self.readReg(0x06))
        return values

    def setBlueLED(self, state):
        self._modify("AS72651", 0x07, lambda current: (current | 0x01) if state else (current & 0xFE))
        return True

    def shutterLED(self, device, state):
        if device not in DEVSEL_BITS:
            return False
        self._modify(device, 0x07, lambda current: (current | 0x08) if state else (current & 0xF7))
        return True

    def setLEDDriveCurrent(self, current):
        if current not in [0, 1, 2, 3]:
            return False
        for device in DEVICES:
            self._modify(device, 0x07, lambda config: (config & 0b11001111) | (int(current) << 4))
        return True

    def setIntegrationTime(self, time):
        if time not in range(0, 255):
            return False
        for device in DEVICES:
            self.setDEVSEL(device)
            self.writeReg(0x05, int(time))
        return True

    def setGain(self, gain):
        if gain not in [0, 1, 2, 3]:
            return False
        for device in DEVICES:
            self._modify(device, 0x04, lambda config: (config & 0b11001111) | (int(gain) << 4))
        return True

    def readRAW(self):
        values = []
        for device in DEVICES:
            self.setDEVSEL(device)
            for high, low in RAW_REGISTERS:
                values.append((self.readReg(high) << 8) | self.readReg(low))
        return self.reorderData(values)

    def readCAL(self):
        values = []
        for device in DEVICES:
            self.setDEVSEL(device)
            for quad in CAL_REGISTERS:
                values.append(self.IEEE754toFloat([self.readReg(register) for register in quad]))
        return self.reorderData(values)

    def IEEE754toFloat(self, valArray):
        return struct.unpack(">f", bytes(int(item) & 0xFF for item in valArray))[0]

    def reorderData(self, unsortedData):
        sorted_data = [0] * 18
        for source, target in REORDER:
            sorted_data[target - 1] = unsortedData[source - 1]
        return sorted_data


class _Release:
    """Context manager that releases an already acquired lock."""

    def __init__(self, lock):
        self._lock = lock

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self._lock.release()
        return False
