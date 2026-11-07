"""Fake backend of the DTMicroscope driver: an in-memory stand-in for the upstream TEMClient.

Gate G7: every method defined here exists on ``DTMicroscope.base.twisted_client:TEMClient`` (twisted_client.py:49-98),
and the driver reaches only those methods.  Like the upstream client, each method takes the arguments of the matching
JSON-RPC call (``set_stage`` takes ``stage_positions`` and ``relative``, ``acquire_image`` takes the detector name and
extra keyword arguments) and returns what the server side would return: ``get_stage`` five coordinates, ``set_stage``
a ``{"new_stage": [...]}`` dict, ``acquire_image`` an image array, ``acquire_spectrum`` a sample array and
``set_beam_position``/``close`` the integer reply 1.  Nothing here opens a socket or talks to a microscope.

Every numeric value below is test data (a start position or a canned reply), not a fact about the device; each is
marked ``# placeholder`` and none is used in driver.py, facts.md or the reference file.
"""

#: Side of the stand-in image the fake returns (the server's reply is larger; RESULT.json notes the size).
_IMAGE_SIDE = 4  # placeholder


class FakeTEMClient:
    def __init__(self, **_options):
        self.detectors = ["flu_camera", "ceta_camera", "scan", "super_x"]  # placeholder: server default names
        self._stage = [0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder: start position (x, y, z, a, b)
        self._beam = [0.0, 0.0]  # placeholder: start beam position (x, y)
        self._vacuum = 1.0  # placeholder: canned vacuum reply
        self._status = "Idle"  # placeholder: canned status reply
        self.closed = False  # placeholder: close latch

    def get_detectors(self):
        return list(self.detectors)

    def get_stage(self):
        return list(self._stage)

    def set_stage(self, stage_positions, relative=True):
        values = []
        for index, direction in enumerate(("x", "y", "z", "a", "b")):
            if isinstance(stage_positions, dict):
                move = stage_positions.get(direction)
            else:
                move = stage_positions[index] if len(stage_positions) > index else None
            values.append(0.0 if move is None else float(move))  # placeholder: missing direction
        if relative:
            self._stage = [current + delta for current, delta in zip(self._stage, values)]
        else:
            self._stage = values
        return {"new_stage": list(self._stage)}

    def set_beam_position(self, x, y):
        self._beam = [float(x), float(y)]
        return 1  # placeholder: the server's reply

    def acquire_image(self, device, **kwargs):
        if device not in self.detectors:
            return None
        return [[0.0 for _ in range(_IMAGE_SIDE)] for _ in range(_IMAGE_SIDE)]  # placeholder: stand-in image

    def acquire_spectrum(self, device, **kwargs):
        if device not in self.detectors:
            return None
        return [0.0] * 8  # placeholder: stand-in samples (the server replies with 2048)

    def get_vacuum(self):
        return self._vacuum

    def get_microscope_status(self):
        return self._status

    def close(self):
        self.closed = True
        return 1  # placeholder: the server's reply
