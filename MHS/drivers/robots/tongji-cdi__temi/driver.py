"""OpenMHS driver for gh.tongji-cdi/temi: the Temi telepresence robot over its WebSocket API.

The upstream package is a small asyncio client (``temi.api:Temi``).  Its constructor takes the WebSocket URI of the
Temi-side Android server (``src/temi/api.py:9-11``, ``src/temi/README.md:2-3``); ``connect()`` opens the event socket
(``src/temi/api.py:36-52``) and ``command()`` sends one JSON request and waits for the reply carrying the same id
(``src/temi/api.py:84-109``).  The API is command-only: the documented calls are speak, ask, goto, turn and a screen
tilt, and the clone documents no getter (``src/temi/README.md:45-62``).  This driver therefore binds actions only.

* ``x-cap.tongji-cdi.goto.v1`` -- go to a saved location; the reply says whether Temi reached it
  (``src/temi/README.md:50-68``);
* ``x-cap.tongji-cdi.speak.v1`` -- say a sentence (``src/temi/README.md:16-31``);
* ``x-cap.tongji-cdi.ask.v1`` -- ask a question and return the recognized answer (``src/temi/README.md:33-48``);
* ``x-cap.tongji-cdi.interface.v1`` -- show a URL on the screen (the example at ``src/temi/api.py:142``);
* ``x-cap.tongji-cdi.stop.v1`` -- the safe-state action: send the stop command.  The README says a goto that times
  out may keep walking and that the caller can then command Temi to stop (``README.md:37-43``), but it does not
  name the stop command; this package sends ``{"command": "stop"}`` and RESULT.json records that inference.

Turn and raise_head are not bound: the README states no unit or range for turn and no unit for the screen tilt
(``README.md:57-61``), so a numeric input would need a unit and a bound the clone does not state.

The upstream API has no getter, so there are no ``@read`` parameters and no limits: no numeric input is exposed.
Temi is a mobile base and the driver is R2.  This package is model-authored and unreviewed: the loader refuses its
hardware backend until a human signs ``reviewed_by``, and the gate checks the fake backend only.  Nothing here ran
on a robot.  The pinned commit is ec0a395405df1583d3357fd944b0c43396b30a7c.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop


class TemiRobot(Driver):
    device_id = "temi"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    native = "temi.api:Temi"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTemi"}
    vendor, model = "Temi", "Temi telepresence robot"
    display_name = "Temi robot (temi.api:Temi)"
    tags = ["mobile base", "telepresence", "navigation", "speech", "websocket", "asyncio"]
    facts = [
        Fact("The README describes the package as an unofficial Python library for remote-controlling the Temi "
             "robot via WebSocket", source="vendor_doc", ref="README.md:2"),
        Fact("A Temi-side Android application creates a WebSocket server at ws://TEMI_IP:8175 and waits for "
             "connections from the Python API", source="vendor_doc", ref="src/temi/README.md:2-3"),
        Fact("The client is constructed with the WebSocket URI of the Temi server: Temi(uri)",
             source="upstream_code", ref="src/temi/api.py:9-11"),
        Fact("connect() retries with a default of 3 tries and 5 s between tries, then raises",
             source="upstream_code", ref="src/temi/api.py:36-52"),
        Fact("Every command is a JSON object with a command name and a generated UUID id, and the reply must carry "
             "the same id", source="vendor_doc", ref="src/temi/README.md:5-14"),
        Fact("command() sends the JSON over a new WebSocket connection and waits for a reply with the same id",
             source="upstream_code", ref="src/temi/api.py:84-109"),
        Fact("The speak command takes a sentence and is answered with the id only",
             source="vendor_doc", ref="src/temi/README.md:16-31"),
        Fact("The ask command speaks a sentence and answers with the recognized reply in an answer field",
             source="vendor_doc", ref="src/temi/README.md:33-48"),
        Fact("The goto command names a saved location and answers with success true when Temi reached it and false "
             "otherwise", source="vendor_doc", ref="src/temi/README.md:50-68"),
        Fact("The API format documents raise_head with an angle field",
             source="vendor_doc", ref="src/temi/README.md:70-84"),
        Fact("The README lists turn by an angle and states no unit or range for it",
             source="vendor_doc", ref="README.md:57-59"),
        Fact("The README states a screen tilt range of -25 to 55, gives no unit and then shows a turn call",
             source="vendor_doc", ref="README.md:60-61"),
        Fact("The README says every command supports a timeout and that a goto which timed out may keep walking, "
             "after which the caller can command Temi to stop", source="vendor_doc", ref="README.md:37-43"),
        Fact("The example opens a URL with interface(url=...)",
             source="upstream_code", ref="src/temi/api.py:142"),
        Fact("run() gathers the tasks queued by the command templates",
             source="upstream_code", ref="src/temi/api.py:119-124"),
        Fact("disconnect() closes the socket if it is still open",
             source="upstream_code", ref="src/temi/api.py:54-57"),
    ]
    safe_state = ("Temi has been sent the stop command; the runtime latch refuses further commands until an "
                  "operator reset")

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.tongji-cdi.goto.v1",
            description="Go to a saved location and report whether Temi says it reached it",
            input={"location": Field("string",
                                     description="Name of a location saved on the Temi map")},
            output={"location": Field("string", description="The location Temi was sent to"),
                    "reached": Field("boolean", description="True when Temi replied success")})
    async def goto(self, location):
        reply = await self.native.command("goto", location=location)
        if reply.get("success") is not True:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"Temi reported that it did not reach location {location!r}",
                               native_code=reply.get("success"))
        return {"location": location, "reached": True}

    @action(name="x-cap.tongji-cdi.speak.v1",
            description="Say a sentence out loud",
            input={"sentence": Field("string", description="Sentence Temi should speak")},
            output={"sentence": Field("string", description="The sentence Temi was told to speak")})
    async def speak(self, sentence):
        await self.native.command("speak", sentence=sentence)
        return {"sentence": sentence}

    @action(name="x-cap.tongji-cdi.ask.v1",
            description="Ask a question, wait for the recognized answer and return it",
            input={"sentence": Field("string", description="Question Temi should ask")},
            output={"question": Field("string", description="The question Temi was told to ask"),
                    "answer": Field("string", description="The answer Temi recognized")})
    async def ask(self, sentence):
        reply = await self.native.command("ask", sentence=sentence)
        answer = reply.get("answer")
        if not isinstance(answer, str) or not answer:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"Temi replied to ask without an answer: {reply!r}")
        return {"question": sentence, "answer": answer}

    @action(name="x-cap.tongji-cdi.interface.v1",
            description="Show a URL on Temi's screen",
            input={"url": Field("string", description="URL to open on the screen")},
            output={"url": Field("string", description="The URL Temi was told to open")})
    async def interface(self, url):
        await self.native.command("interface", url=url)
        return {"url": url}

    @action(name="x-cap.tongji-cdi.stop.v1", safe_state=True,
            description="Stop all motion with the Temi stop command; it takes no input",
            output={"stopped": Field("boolean", description="True once the stop command was sent")})
    async def stop_motion(self):
        await self.native.command("stop")
        return {"stopped": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="command")
    async def emergency_stop(self):
        """The native stop: send the Temi stop command (the safe-state action below does the same)."""
        await self.native.command("stop")

    async def setup(self):
        await self.native.connect()

    async def teardown(self):
        await self.native.disconnect()
