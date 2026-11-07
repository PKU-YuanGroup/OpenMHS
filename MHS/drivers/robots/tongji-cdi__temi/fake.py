"""Fake backend of the Temi driver: an in-memory stand-in for temi.api:Temi.

Gate G7: every public method defined here exists on ``Temi`` in the clone at the pinned commit
ec0a395405df1583d3357fd944b0c43396b30a7c (``src/temi/api.py``), with the upstream parameter names and defaults:
``connect(tries=3, interval=5)``, ``disconnect()``, ``register(event, callback, oneshot=False)``,
``unregister(event, callback)``, ``command(command, timeout=None, **kwargs)`` and ``run()``.  Like the upstream
client, ``command()`` is a coroutine that sends one request and returns the reply carrying the same id
(``src/temi/api.py:84-109``).

The values below are test data: a canned answer, a successful goto and an empty task list.  Nothing here talks to
a robot or a network.  The commands the driver sent are kept in ``_commands`` and the underscore hooks let a test
force a native failure, a failed goto or a missing answer.
"""

import asyncio
import uuid


class _FakeSocket:
    """The socket object ``connect()`` stores in ``temisocket`` (the upstream client stores a websockets client)."""

    def __init__(self):
        self.open = True


class FakeTemi:
    def __init__(self, uri=None, logger=None, loglevel="DEBUG"):
        self.uri = uri
        self.logger = logger
        self.loglevel = loglevel
        self.temisocket = None
        self.tasks = []                                      # placeholder: empty task list
        self.callbacks = {}
        self._commands = []                                  # (command, keyword arguments) the driver sent
        self._answer = "yes"                                 # placeholder: canned speech-recognition reply
        self._goto_success = True                            # placeholder: canned goto result
        self._fail_next = None                               # one-shot native failure for a test
        self._spoken = []
        self._question = None
        self._location = None
        self._url = None
        self._stop_count = 0

    async def connect(self, tries=3, interval=5):            # placeholder defaults: upstream signature
        self.temisocket = _FakeSocket()

    async def disconnect(self):
        if self.temisocket is not None and self.temisocket.open:
            self.temisocket.open = False

    def register(self, event, callback, oneshot=False):
        if event not in self.callbacks:
            self.callbacks[event] = {"oneshot": set(), "repeat": set()}
        if oneshot:
            self.callbacks[event]["oneshot"].add(callback)
        else:
            self.callbacks[event]["repeat"].add(callback)

    def unregister(self, event, callback):
        if callback in self.callbacks[event]["oneshot"]:
            self.callbacks[event]["oneshot"].remove(callback)
        elif callback in self.callbacks[event]["repeat"]:
            self.callbacks[event]["repeat"].remove(callback)

    async def command(self, command, timeout=None, **kwargs):
        self._commands.append((command, dict(kwargs)))
        if self._fail_next is not None:
            message, self._fail_next = self._fail_next, None
            raise RuntimeError(message)
        reply = {"id": str(uuid.uuid4())}
        if command == "speak":
            self._spoken.append(kwargs.get("sentence"))
        elif command == "ask":
            self._question = kwargs.get("sentence")
            if self._answer is not None:
                reply["answer"] = self._answer
        elif command == "goto":
            self._location = kwargs.get("location")
            reply["success"] = self._goto_success
        elif command == "interface":
            self._url = kwargs.get("url")
        elif command == "stop":
            self._stop_count += 1
        return reply

    async def run(self):
        results = await asyncio.gather(*self.tasks)
        self.tasks = []
        if len(results) == 1:
            return results[0]
        return results

    # -- hooks for test_driver.py (not Temi members, never used by the driver) ---------------------------------
    def _fail_next_command(self, message):
        """The next command raises ``RuntimeError(message)``, like a failing native call."""
        self._fail_next = message

    def _set_goto_success(self, value):
        """The next goto replies with this ``success`` value."""
        self._goto_success = bool(value)

    def _set_answer(self, answer):
        """The next ask replies with this answer (``None`` omits the answer field)."""
        self._answer = answer
