r"""Hardware backend: open the Gemini named pipe and speak its command protocol.

The upstream class is Python 2 and imports pywin32 (Gemini/gemini.py:3-5); this module is a Python 3 port of the
same named-pipe client, keeping the upstream pywin32 calls and command strings.  It is used only with
backend="hardware".  This package is model-authored and unreviewed and is R2, so the loader refuses that backend
until a human signs ``reviewed_by`` in driver.lock.json.  The acceptance gate never imports this module and it was
never run against Gemini; pywin32 is a hardware-time dependency, not installed here.

The port keeps the upstream command strings and reply parsing: one command is written, one reply is read, and the
reply is semicolon-separated fields whose first field is an error code (Gemini/gemini.py:21-43).  The pipe name is
``\\.\pipe\gemini`` (Gemini/gemini.py:91-97) unless the deployment passes ``pipe_name``.  The upstream's blocking
ReadFile has no timeout; this port keeps that behaviour and adds no stop path of its own.
"""

from win32file import *
from win32pipe import *
from win32api import *


class GeminiPipe:
    """The Python 3 port of ``gemini:Gemini``: the same public command methods over the same named pipe."""

    class IOException(BaseException):
        pass

    class CmdError(BaseException):
        pass

    def __init__(self, pipe_name=r"\\.\pipe\gemini", **_options):
        self.pipe_name = str(pipe_name)
        self.debug = False
        self.hPipe = None

    # -- transport ------------------------------------------------------------------------------------------------
    def open(self):
        while True:
            try:
                self.hPipe = CreateFile(self.pipe_name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
            except Exception as exc:
                raise self.IOException(FormatMessage(GetLastError())) from exc
            if self.hPipe != INVALID_HANDLE_VALUE:
                break
            if GetLastError() != ERROR_PIPE_BUSY:
                raise self.IOException("the Gemini pipe is unavailable")
            if not WaitNamedPipe(self.pipe_name, 2000):
                raise self.IOException("the Gemini pipe stayed busy")
        try:
            SetNamedPipeHandleState(self.hPipe, PIPE_READMODE_MESSAGE, None, None)
        except Exception as exc:
            raise self.IOException("the Gemini pipe did not enter message-read mode") from exc
        return self

    def close(self):
        # The upstream close() is a pass (Gemini/gemini.py:88-89); keep that surface and let the process release it.
        return None

    def execute(self, cmd):
        if self.hPipe is None:
            raise self.IOException("the Gemini pipe is not open")
        payload = cmd.encode("ascii") if isinstance(cmd, str) else cmd
        try:
            WriteFile(self.hPipe, payload)
        except Exception as exc:
            raise self.IOException(FormatMessage(GetLastError())) from exc
        try:
            (hr, data) = ReadFile(self.hPipe, 1024)
        except Exception as exc:
            raise self.IOException(FormatMessage(GetLastError())) from exc
        text = data.decode("ascii", "replace") if isinstance(data, bytes) else str(data)
        if text.endswith("\0"):
            text = text[:-1]
        fields = text.strip().split(";")
        if not fields or not fields[0].isdigit():
            raise self.IOException("the Gemini reply has no error code")
        ecode = int(fields[0])
        if ecode != 0:
            raise self.CmdError(ecode)
        return fields[1:]

    def setdebug(self):
        self.debug = True

    def flush(self):
        # The upstream flush reads until a ReadFile with hr != 0; this port is not used by the driver's read/write
        # path.  Keep the method for the class surface.
        return None

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


def connect(pipe_name=r"\\.\pipe\gemini", **options):
    """Open the Gemini pipe and return the port object; called only by an explicitly allowed hardware backend."""
    client = GeminiPipe(pipe_name, **options)
    client.open()
    return client
