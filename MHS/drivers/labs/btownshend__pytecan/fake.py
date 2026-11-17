"""Fake backend of the pytecan driver: an in-memory stand-in for the Gemini named-pipe client.

Gate G7: every public method defined here exists on the upstream class ``gemini:Gemini``
(Gemini/gemini.py:8; the Python 2 source is read leniently by the gate).  The fake copies the upstream command
surface: ``execute`` writes one command and returns the semicolon-separated reply fields after the error code,
``getvar``/``getstatus``/``getversion``/``setvar``/``start_pipetting`` send the same command strings as the upstream
methods (Gemini/gemini.py:55-86), and ``open``/``close``/``flush``/``setdebug`` exist with the same names.  The
reply text, the status and version strings, and the starting variable value are test data, not device facts; each
is marked ``# placeholder`` below.  Nothing here talks to a device, and nothing here is a recording.
"""


class FakeGemini:
    """Stand-in for ``gemini:Gemini`` with the same public command surface and an in-memory reply table."""

    class IOException(BaseException):
        pass

    class CmdError(BaseException):
        pass

    debug = False
    hPipe = None

    def __init__(self, **_options):
        self._open = True
        self._status = "IDLE"                               # placeholder
        self._version = "fake-gemini-0"                     # placeholder
        self._variables = {"testvar": 4.5}                  # placeholder (the clone's example name, gemtest.py:8)
        self._running = False
        self._pending = []

    # -- transport ------------------------------------------------------------------------------------------------
    def execute(self, cmd):
        """Answer one host command as the pipe would: ``<ecode>;<field>;...``; a nonzero code raises CmdError."""
        if not self._open:
            raise self.IOException()
        if cmd == "GET_STATUS":
            reply = "0;" + self._status
        elif cmd == "GET_VERSION":
            reply = "0;" + self._version
        elif cmd.startswith("GET_VARIABLE;"):
            name = cmd.split(";", 1)[1]
            if name in self._variables:
                reply = "0;" + ("%.2f" % self._variables[name])
            else:
                reply = "14;"
        elif cmd.startswith("SET_VARIABLE;"):
            parts = cmd.split(";")
            if len(parts) != 3:
                reply = "3;"
            else:
                self._variables[parts[1]] = float(parts[2])
                reply = "0;"
        elif cmd == "START_PIPETTING":
            self._running = True
            self._status = "RUNNING"                        # placeholder
            reply = "0;"
        elif cmd == "GET_MAX_VARIABLES":
            reply = "0;" + str(len(self._variables))
        elif cmd.startswith("GET_VARIABLE_NAME;"):
            index = int(cmd.split(";", 1)[1])
            names = sorted(self._variables)
            reply = "0;" + names[index] if index < len(names) else "3;"
        else:
            reply = "1;"                                    # Invalid command (Gemini/gemini.py:19)
        fields = reply.split(";")
        ecode = int(fields[0])
        if ecode != 0:
            raise self.CmdError(ecode)
        return fields[1:]

    def setdebug(self):
        self.debug = True

    def flush(self):
        while self._pending:
            self._pending.pop(0)

    def open(self):
        self._open = True
        self.hPipe = object()                               # placeholder handle

    def close(self):
        # Gemini/gemini.py:88-89 is a pass: closing does not stop a program or close its pipe handle.
        pass

    # -- host commands --------------------------------------------------------------------------------------------
    def getvar(self, name):
        try:
            resp = self.execute("GET_VARIABLE;%s" % name)
        except self.CmdError as exc:
            if int(exc.args[0]) == 14:
                return None
            raise
        return float(resp[0])

    def getstatus(self):
        status = self.execute("GET_STATUS")
        return status[0]

    def getversion(self):
        result = self.execute("GET_VERSION")
        return result[0]

    def setvar(self, name, value):
        resp = self.execute("SET_VARIABLE;%s;%.2f" % (name, value))
        return resp

    def start_pipetting(self):
        resp = self.execute("START_PIPETTING")
        return resp
