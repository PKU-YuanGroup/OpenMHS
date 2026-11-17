"""Fake backend of the LevyLab lock-in: an in-memory stand-in for levylabinst.MCLockin:MCLockin.

Gate G7: every public method here exists on the upstream class (``get_idn`` and ``close``, the latter through
``ZMQInstrument``).  The private members mirror the upstream methods the driver calls: ``config`` is the label to lead
map set by ``MCLockin.__init__`` (levylabinst/MCLockin.py:36), ``_ref_channel`` is fixed to 1 by the same constructor
(line 41), ``_get_lockin`` and ``_get_state`` call ``_send_command`` exactly as the upstream ones do (lines 210-223),
and ``_send_command`` answers with a JSON-RPC shaped dictionary.

Every reading, status word and lead number below is synthetic test data (# placeholder).  The identity dictionary is
the literal reply of the upstream ``get_idn`` (levylabinst/MCLockin.py:181-186); it is not a measurement.
"""


class FakeMCLockin:
    """Analytic F0 stand-in: fixed readings, no timing model and no device I/O."""

    def __init__(self, **_options):
        # placeholder: synthetic channel configuration used by the acceptance tests
        self.config = {"source": 1, "drain": 2, "gate": 3}
        self._ref_channel = 1                     # MCLockin.py:41
        self._status = "idle"                     # placeholder: a getStatus result word
        # placeholder: canned lock-in readings keyed by (lead, measurement)
        self._readings = {
            (1, "X"): 1.0, (1, "Y"): -2.0, (1, "R"): 2.236, (1, "Theta"): 30.0, (1, "Mean"): 0.5,
            (2, "X"): 2.0, (2, "Y"): -4.0, (2, "R"): 4.472, (2, "Theta"): 60.0, (2, "Mean"): 1.0,
            (3, "X"): 3.0, (3, "Y"): -6.0, (3, "R"): 6.708, (3, "Theta"): 90.0, (3, "Mean"): 1.5,
        }

    def get_idn(self):
        """The upstream override (levylabinst/MCLockin.py:177-186), not a synthesized identity."""
        return {
            "vendor": "LevyLab",
            "model": "MC Lock-in",
            "serial": None,
            "firmware": "v2.15.4.4",
        }

    def _send_command(self, cmd, params=None):
        """The JSON-RPC exchange the upstream transport performs, answered from memory."""
        if cmd == "getResults":
            return {"result": {"Results (Dictionary)": [
                {"key": f"AI{lead}.Ref{self._ref_channel}.{measurement}", "value": value}
                for (lead, measurement), value in sorted(self._readings.items())]}}
        if cmd == "getStatus":
            return {"result": self._status}
        raise RuntimeError(f"the fake lock-in does not answer {cmd!r}")

    def _get_lockin(self, value, channel):
        """The upstream getResults lookup (levylabinst/MCLockin.py:210-215)."""
        key = f"AI{channel}.Ref{self._ref_channel}.{value}"
        response = self._send_command('getResults')
        results = response['result']['Results (Dictionary)']
        results_dict = {item['key']: item['value'] for item in results}
        return results_dict.get(key)

    def _get_state(self):
        """The upstream getStatus read (levylabinst/MCLockin.py:221-223)."""
        response = self._send_command('getStatus')
        return response['result']

    def close(self):
        """The ZMQInstrument.close contract without a socket."""
