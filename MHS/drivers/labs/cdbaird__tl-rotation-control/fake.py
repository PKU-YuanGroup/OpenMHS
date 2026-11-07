"""Fake backend of the Elliptec rotation stage driver: an in-memory stand-in for ``elliptec.rotation:Motor``.

Gate G7: the public methods defined here (``get_``, ``set_``, ``do_`` and ``deg_to_hex``) exist on the upstream
``Motor`` class, and the attributes the driver reaches (``info``, ``range``, ``counts_per_rev`` and ``status``) are
set by the upstream class.  The fake answers the upstream command letters of ``elliptec/cmd.py``: ``in``, ``gs``,
``gp``, ``gj``, ``sj``, ``is``, ``ho``, ``fw``, ``bw``, ``ma`` and ``mr``.  It keeps the state in plain attributes
and records every command line it would send in ``commands`` for the package tests.

The start values are test data, not facts about a stage: mark them here and never copy one into a Fact or a Limit.
Nothing here talks to a device.
"""

#: The query instructions of the clone (elliptec/cmd.py:2-7).
_GET = {"info": "in", "status": "gs", "position": "gp", "stepsize": "gj"}
#: The setting instructions of the clone (elliptec/cmd.py:9-12).
_SET = {"stepsize": "sj", "isolate": "is"}
#: The move instructions of the clone (elliptec/cmd.py:14-20).
_MOV = {"home": "ho", "forward": "fw", "backward": "bw", "absolute": "ma", "relative": "mr"}


def _s32(value):
    """The signed 32-bit reading of a position field (elliptec/helper.py:74-75)."""
    return -(value & 0x80000000) | (value & 0x7FFFFFFF)


def _hex32(value):
    return format(value & 0xFFFFFFFF, "08X")


class FakeMotor:
    def __init__(self, **_options):
        # Placeholders for the information reply of an Elliptec stage (elliptec/helper.py:34-43).
        self.info = {
            "Address": "0",              # placeholder
            "Motor Type": "08",          # placeholder
            "Serial No.": "00000000",    # placeholder
            "Year": "0000",              # placeholder
            "Firmware": "00",            # placeholder
            "Thread": "Metric",          # placeholder
            "Hardware": "0",             # placeholder
            "Range": 360,                # placeholder
            "Pulse/Rev": 262144,         # placeholder
        }
        self.range = self.info["Range"]
        self.counts_per_rev = self.info["Pulse/Rev"]
        self.conv_factor = float(self.range) / float(self.counts_per_rev)
        self.position_counts = 90 * (self.counts_per_rev // self.range)  # placeholder: 90 degrees
        self.step_size_counts = 45 * (self.counts_per_rev // self.range)  # placeholder: 45 degrees
        self.status_code = 0             # placeholder
        self.isolated = False            # placeholder
        self.status = ("GS", "0")        # placeholder
        self.commands = []

    def deg_to_hex(self, deg):
        # The same conversion as the clone (elliptec/rotation.py:78-81).
        factor = self.counts_per_rev // self.range
        return hex(deg * factor).replace("0x", "").zfill(8).upper()

    def get_(self, req="status", data="", addr="0"):
        instruction = _GET.get(req)
        if instruction is None:
            self.status = ("GS", "3")    # placeholder: command error
            return
        self.commands.append(addr + instruction + data)
        if req == "position":
            self.status = ("PO", self.position_counts)
        elif req == "stepsize":
            self.status = ("GJ", _hex32(self.step_size_counts))
        elif req == "status":
            self.status = ("GS", str(self.status_code))
        else:
            self.status = ("IN", "0000000000000000")  # placeholder

    def set_(self, req="", data="", addr="0"):
        instruction = _SET.get(req)
        if instruction is None:
            self.status = ("GS", "3")    # placeholder: command error
            return
        self.commands.append(addr + instruction + data)
        if req == "stepsize":
            self.step_size_counts = _s32(int(data, 16))
            self.status = ("GS", "0")
        elif req == "isolate":
            self.isolated = data == "01"
            self.status_code = 5 if self.isolated else 6
            self.status = ("GS", str(self.status_code))
        else:
            self.status = ("GS", "3")    # placeholder: command error

    def do_(self, req="home", data="0", addr="0"):
        instruction = _MOV.get(req)
        if instruction is None:
            self.status = ("GS", "3")    # placeholder: command error
            return
        self.commands.append(addr + instruction + data)
        if req == "home":
            self.position_counts = 0
        elif req == "absolute":
            self.position_counts = _s32(int(data, 16))
        elif req == "relative":
            self.position_counts += _s32(int(data, 16))
        elif req == "forward":
            self.position_counts += self.step_size_counts
        elif req == "backward":
            self.position_counts -= self.step_size_counts
        self.status = ("PO", self.position_counts)
