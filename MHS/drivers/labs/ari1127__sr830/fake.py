"""Fake SCPI transport of the SR830 driver: a stateful text transport, not a replay.

The gate and the conformance suite send many different request sequences, each on a fresh transport, so a strict
transcript cannot serve them.  This fake keeps one plain attribute per setting, answers the query of each with the
current value, and applies every write to its own state, so a write is observable in the next read.  The command
words and argument forms are the ones the clone writes in ``SR830.py``; a query the driver never sends is not
answered.  All numbers here are test data (each is marked ``# placeholder``), not device facts.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Nothing
here talks to an instrument.
"""


class FakeSr830:
    def __init__(self, **_options):
        # The measured values are placeholders; R and Theta are consistent with X and Y only by construction.
        self.x = -1.5e-3  # placeholder
        self.y = 2.0e-3  # placeholder
        self.r = 2.5e-3  # placeholder
        self.theta = 126.86989765  # placeholder
        self.frequency = 1000.0  # placeholder
        self.amplitude = 0.1  # placeholder
        self.phase = 0.0  # placeholder
        self.harmonic = 1  # placeholder
        self.reference_source = 1  # placeholder
        self.trigger_shape = 0  # placeholder
        self.aux_output_1 = 0.0  # placeholder
        self.aux_output_2 = 0.0  # placeholder
        self.input_source = 0  # placeholder
        self.coupling = 0  # placeholder
        self.grounding = 0  # placeholder
        self.line_filter = 0  # placeholder
        self.reserve = 0  # placeholder
        self.filter_slope = 0  # placeholder
        self.sync_filter = 0  # placeholder
        self.time_constant_index = 6  # placeholder
        self.sensitivity_index = 17  # placeholder
        self.display_1 = "0,0"  # placeholder
        self.display_2 = "0,0"  # placeholder
        self.expand_1 = "0,0"  # placeholder
        self.expand_2 = "0,0"  # placeholder
        self.written = []
        self._pending = []

    # -- transport surface -------------------------------------------------------
    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        text = line.strip()
        if "?" in text:
            self._pending.append(self._reply(text))
            return
        command, _, argument = text.partition(" ")
        argument = argument.strip()
        if command == "FREQ":
            self.frequency = float(argument)
        elif command == "SLVL":
            self.amplitude = float(argument)
        elif command == "PHAS":
            self.phase = float(argument)
        elif command == "FMOD":
            self.reference_source = int(argument)
        elif command == "ISRC":
            self.input_source = int(argument)
        elif command == "ICPL":
            self.coupling = int(argument)
        elif command == "IGND":
            self.grounding = int(argument)
        elif command == "ILIN":
            self.line_filter = int(argument)
        elif command == "RMOD":
            self.reserve = int(argument)
        elif command == "OFLT":
            self.time_constant_index = int(argument)
        elif command == "SENS":
            self.sensitivity_index = int(argument)
        elif command == "AUXV":
            index, _, value = argument.partition(",")
            if index.strip() == "1":
                self.aux_output_1 = float(value)
            elif index.strip() == "2":
                self.aux_output_2 = float(value)
            else:
                raise ValueError(f"AUXV has no output {index.strip()!r}")
        else:
            raise ValueError(f"the fake does not implement the write {text!r}")

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        reply = self._pending.pop(0)
        if reply is None:
            raise TimeoutError("the fake does not implement this query")
        return reply

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    # -- replies -----------------------------------------------------------------
    def _reply(self, text):
        replies = {
            "FREQ?": self._number(self.frequency),
            "SLVL?": self._number(self.amplitude),
            "PHAS?": self._number(self.phase),
            "HARM?": str(self.harmonic),
            "FMOD?": str(self.reference_source),
            "RSLP?": str(self.trigger_shape),
            "AUXV? 1": self._number(self.aux_output_1),
            "AUXV? 2": self._number(self.aux_output_2),
            "ISRC?": str(self.input_source),
            "ICPL?": str(self.coupling),
            "IGND?": str(self.grounding),
            "ILIN?": str(self.line_filter),
            "RMOD?": str(self.reserve),
            "OFSL?": str(self.filter_slope),
            "SYNC?": str(self.sync_filter),
            "OFLT?": str(self.time_constant_index),
            "SENS?": str(self.sensitivity_index),
            "OUTP? 1": self._number(self.x),
            "OUTP? 2": self._number(self.y),
            "OUTP? 3": self._number(self.r),
            "OUTP? 4": self._number(self.theta),
            "SNAP?1,2,3,4": ",".join(self._number(value) for value in
                                    (self.x, self.y, self.r, self.theta)),
            "DDEF? 1": self.display_1,
            "DDEF? 2": self.display_2,
            "OEXP? 1": self.expand_1,
            "OEXP? 2": self.expand_2,
        }
        return replies.get(text)

    @staticmethod
    def _number(value):
        return repr(float(value))
