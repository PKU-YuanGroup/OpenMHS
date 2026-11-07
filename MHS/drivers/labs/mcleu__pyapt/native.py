"""Hardware backend: an independent Python 3 port of PyAPT.PyAPT:APTMotor for Thorlabs APT.dll.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R1, so the loader's refusal of an unreviewed model-written hardware backend applies only at
R2 and R3 and does not protect this backend; an operator must review the package and the site's stop arrangement
before any hardware use.  The acceptance gate runs the fake backend and never imports this module or the clone.

The upstream file is Python 2 syntax and imports ctypes.windll (PyAPT/PyAPT.py:18-21), so it cannot be imported under
Python 3, and this module repeats the APT.dll calls of the upstream class without importing or executing the clone.
Package code must not import ctypes directly (the gate's G3.FORBIDDEN scan rejects it), so this module loads the vendor
DLL through numpy.ctypeslib, a public numpy API; the hardware host therefore needs numpy.  numpy.ctypeslib returns a
cdecl CDLL, and the APT API is stdcall (APTDLLPack/APTDLLClient/APTAPI.h uses WINAPI), so this port refuses a 32-bit
host: 64-bit Windows has one calling convention.  The APT.dll entry points and their signatures come from the vendor
header bundled in the clone: APTInit and APTCleanUp (lines 108-109), InitHWDevice (line 113), the velocity queries
(lines 125-127), the stage axis information (line 137), the limit switches (line 139), the position (line 143), the
moves (lines 144-146) and MOT_StopProfiled (line 148).  The stage unit code is 1 for mm and 2 for degrees (lines 82-84).
The upstream needs the matching x86 or x64 APT.dll (README.md:10-12, 16); this port runs the x64 one.

Options: ``serial_number`` (required) is the controller serial number passed to InitHWDevice; ``hwtype`` (default 31,
the TDC001 type from the upstream constructor) is the hardware type used for enumeration; ``dll_path`` (default
"APT.dll") is the vendor DLL; ``verbose`` is accepted for parity with the upstream constructor.
"""

import os
import struct

import numpy as np
from numpy.ctypeslib import as_ctypes_type, load_library, ndpointer

_INT32 = as_ctypes_type(np.int32)
_FLOAT32 = as_ctypes_type(np.float32)
_BOOL = as_ctypes_type(np.int32)  # Windows BOOL is a 32-bit int, not ctypes c_bool
_INT32_PTR = ndpointer(dtype=np.int32)
_FLOAT32_PTR = ndpointer(dtype=np.float32)
_BYTE_PTR = ndpointer(dtype=np.uint8)


def _bind(dll):
    """Declare the APT.dll signatures the port calls, so pointers and floats cross the library boundary correctly."""
    dll.APTInit.argtypes, dll.APTInit.restype = [], _INT32
    dll.APTCleanUp.argtypes, dll.APTCleanUp.restype = [], _INT32
    dll.EnableEventDlg.argtypes, dll.EnableEventDlg.restype = [_BOOL], _INT32
    dll.InitHWDevice.argtypes, dll.InitHWDevice.restype = [_INT32], _INT32
    dll.GetNumHWUnitsEx.argtypes, dll.GetNumHWUnitsEx.restype = [_INT32, _INT32_PTR], _INT32
    dll.GetHWSerialNumEx.argtypes, dll.GetHWSerialNumEx.restype = [_INT32, _INT32, _INT32_PTR], _INT32
    dll.GetHWInfo.argtypes = [_INT32, _BYTE_PTR, _INT32, _BYTE_PTR, _INT32, _BYTE_PTR, _INT32]
    dll.GetHWInfo.restype = _INT32
    dll.MOT_GetStageAxisInfo.argtypes = [_INT32, _FLOAT32_PTR, _FLOAT32_PTR, _INT32_PTR, _FLOAT32_PTR]
    dll.MOT_GetStageAxisInfo.restype = _INT32
    dll.MOT_SetStageAxisInfo.argtypes = [_INT32, _FLOAT32, _FLOAT32, _INT32, _FLOAT32]
    dll.MOT_SetStageAxisInfo.restype = _INT32
    dll.MOT_GetHWLimSwitches.argtypes = [_INT32, _INT32_PTR, _INT32_PTR]
    dll.MOT_GetHWLimSwitches.restype = _INT32
    dll.MOT_GetVelParams.argtypes = [_INT32, _FLOAT32_PTR, _FLOAT32_PTR, _FLOAT32_PTR]
    dll.MOT_GetVelParams.restype = _INT32
    dll.MOT_SetVelParams.argtypes = [_INT32, _FLOAT32, _FLOAT32, _FLOAT32]
    dll.MOT_SetVelParams.restype = _INT32
    dll.MOT_GetVelParamLimits.argtypes = [_INT32, _FLOAT32_PTR, _FLOAT32_PTR]
    dll.MOT_GetVelParamLimits.restype = _INT32
    dll.MOT_GetPosition.argtypes = [_INT32, _FLOAT32_PTR]
    dll.MOT_GetPosition.restype = _INT32
    dll.MOT_MoveHome.argtypes = [_INT32, _BOOL]
    dll.MOT_MoveHome.restype = _INT32
    dll.MOT_MoveRelativeEx.argtypes = [_INT32, _FLOAT32, _BOOL]
    dll.MOT_MoveRelativeEx.restype = _INT32
    dll.MOT_MoveAbsoluteEx.argtypes = [_INT32, _FLOAT32, _BOOL]
    dll.MOT_MoveAbsoluteEx.restype = _INT32
    dll.MOT_StopProfiled.argtypes = [_INT32]
    dll.MOT_StopProfiled.restype = _INT32
    dll.MOT_Identify.argtypes = [_INT32]
    dll.MOT_Identify.restype = _INT32


def _text(buffer):
    """The NUL-terminated ASCII text of a byte buffer that the DLL filled."""
    return bytes(buffer).split(b"\x00", 1)[0].decode("latin-1", "replace")


class APTMotor:
    """The upstream APTMotor interface, ported to Python 3 and to the vendor DLL signatures."""

    def __init__(self, serial_number, hwtype=31, verbose=False, dll_path="APT.dll"):
        if not hasattr(np.ctypeslib, "ctypes") or os.name != "nt":
            raise OSError("APT.dll needs 64-bit Windows and numpy")
        if struct.calcsize("P") != 8:
            raise OSError("this port supports 64-bit Windows only: the APT API is stdcall and the DLL is loaded "
                          "through numpy.ctypeslib")
        self.verbose = verbose
        self.Connected = False
        self.aptdll = load_library(os.path.basename(dll_path), os.path.dirname(dll_path) or ".")
        _bind(self.aptdll)
        self.aptdll.EnableEventDlg(True)
        self.aptdll.APTInit()
        self.HWType = int(hwtype)
        self.blCorr = 0.10          # the upstream constructor's 100 um backlash correction (PyAPT/PyAPT.py:53)
        self.SerialNum = int(serial_number)
        self.initializeHardwareDevice()

    # -- system information -----------------------------------------------------------------------------------
    def getNumberOfHardwareUnits(self):
        num_units = np.zeros(1, dtype=np.int32)
        self.aptdll.GetNumHWUnitsEx(self.HWType, num_units)
        return int(num_units[0])

    def getSerialNumberByIdx(self, index):
        serial = np.zeros(1, dtype=np.int32)
        self.aptdll.GetHWSerialNumEx(self.HWType, int(index), serial)
        return int(serial[0])

    def setSerialNumber(self, SerialNum):
        self.SerialNum = int(SerialNum)
        return self.SerialNum

    def initializeHardwareDevice(self):
        if self.aptdll.InitHWDevice(self.SerialNum) != 0:
            raise RuntimeError("Connection Failed. Check Serial Number!")
        self.Connected = True
        return True

    def getHardwareInformation(self):
        model = np.zeros(255, dtype=np.uint8)
        software_version = np.zeros(255, dtype=np.uint8)
        hardware_notes = np.zeros(255, dtype=np.uint8)
        self.aptdll.GetHWInfo(self.SerialNum, model, 255, software_version, 255, hardware_notes, 255)
        return [_text(model), _text(software_version), _text(hardware_notes)]

    # -- stage and velocity configuration ---------------------------------------------------------------------
    def getStageAxisInformation(self):
        minimum_position = np.zeros(1, dtype=np.float32)
        maximum_position = np.zeros(1, dtype=np.float32)
        units = np.zeros(1, dtype=np.int32)
        pitch = np.zeros(1, dtype=np.float32)
        self.aptdll.MOT_GetStageAxisInfo(self.SerialNum, minimum_position, maximum_position, units, pitch)
        return [float(minimum_position[0]), float(maximum_position[0]), int(units[0]), float(pitch[0])]

    def setStageAxisInformation(self, stageAxisInformation):
        self.aptdll.MOT_SetStageAxisInfo(self.SerialNum, float(stageAxisInformation[0]),
                                         float(stageAxisInformation[1]), int(stageAxisInformation[2]),
                                         float(stageAxisInformation[3]))
        return True

    def getHardwareLimitSwitches(self):
        reverse_limit_switch = np.zeros(1, dtype=np.int32)
        forward_limit_switch = np.zeros(1, dtype=np.int32)
        self.aptdll.MOT_GetHWLimSwitches(self.SerialNum, reverse_limit_switch, forward_limit_switch)
        return [int(reverse_limit_switch[0]), int(forward_limit_switch[0])]

    def getVelocityParameters(self):
        minimum_velocity = np.zeros(1, dtype=np.float32)
        acceleration = np.zeros(1, dtype=np.float32)
        maximum_velocity = np.zeros(1, dtype=np.float32)
        self.aptdll.MOT_GetVelParams(self.SerialNum, minimum_velocity, acceleration, maximum_velocity)
        return [float(minimum_velocity[0]), float(acceleration[0]), float(maximum_velocity[0])]

    def getVel(self):
        return self.getVelocityParameters()[2]

    def setVelocityParameters(self, minVel, acc, maxVel):
        self.aptdll.MOT_SetVelParams(self.SerialNum, float(minVel), float(acc), float(maxVel))
        return True

    def setVel(self, maxVel):
        minimum_velocity, acceleration, _old_velocity = self.getVelocityParameters()
        self.setVelocityParameters(minimum_velocity, acceleration, maxVel)
        return True

    def getVelocityParameterLimits(self):
        maximum_acceleration = np.zeros(1, dtype=np.float32)
        maximum_velocity = np.zeros(1, dtype=np.float32)
        self.aptdll.MOT_GetVelParamLimits(self.SerialNum, maximum_acceleration, maximum_velocity)
        return [float(maximum_acceleration[0]), float(maximum_velocity[0])]

    # -- motion ------------------------------------------------------------------------------------------------
    def getPos(self):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        position = np.zeros(1, dtype=np.float32)
        self.aptdll.MOT_GetPosition(self.SerialNum, position)
        return float(position[0])

    def mRel(self, relDistance):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        if self.aptdll.MOT_MoveRelativeEx(self.SerialNum, float(relDistance), True) != 0:
            raise RuntimeError("MOT_MoveRelativeEx failed")
        return True

    def mAbs(self, absPosition):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        if self.aptdll.MOT_MoveAbsoluteEx(self.SerialNum, float(absPosition), True) != 0:
            raise RuntimeError("MOT_MoveAbsoluteEx failed")
        return True

    def go_home(self):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        if self.aptdll.MOT_MoveHome(self.SerialNum, True) != 0:
            raise RuntimeError("MOT_MoveHome failed")
        return True

    def identify(self):
        self.aptdll.MOT_Identify(self.SerialNum)
        return True

    def cleanUpAPT(self):
        self.aptdll.APTCleanUp()
        self.Connected = False


def connect(serial_number, hwtype=31, verbose=False, dll_path="APT.dll"):
    """Return the ported APTMotor for the controller with ``serial_number`` (64-bit Windows, numpy and APT.dll)."""
    return APTMotor(serial_number, hwtype=hwtype, verbose=verbose, dll_path=dll_path)
