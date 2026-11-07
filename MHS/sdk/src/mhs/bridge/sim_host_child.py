"""The child process of the isolated simulator host (``isolated_process_v1``, :mod:`mhs.bridge.sim_host`).

:class:`mhs.bridge.sim_host.ProcessHost` starts this file as a script (``<python> sim_host_child.py``) with two
pipe descriptors named in ``MHS_SIM_HOST_FDS`` (requests in, replies out) and with standard input, output and error
on ``/dev/null``: whatever the environment prints can never reach the endpoint's own streams or the protocol.  It
speaks one JSON document per line.

The first request (``init``) names the driver package directory, a package-relative ``.module:attribute`` entry, its
keyword arguments and the declared stop and read-back.  The entry is imported and called on the main thread (ROS 1
must initialise its node there) and must return the environment; the reply describes its action and observation
spaces.  After that the main thread only reads requests, and two worker threads run them, one at a time each:

* the world lane: ``step``, ``reset`` and ``close`` of the environment;
* the control lane: the declared stop and the declared read-back.

A stop first fences the host, atomically with reading whether a world call is running: after that no world call
starts here (``step`` and ``reset`` are refused, ``close`` is not), and the reply says whether one was running when
the fence was set.  Only the endpoint's safety reset (``unfence``) lifts the fence.  The stop and read-back paths
are resolved on ``env.unwrapped`` when the environment has one (a Gymnasium wrapper chain), else on the environment.

Every call into package or upstream code is made inside ``try/except BaseException``: a ``SystemExit`` (for example
``sys.exit`` after a global ``rospy.signal_shutdown``) or ``KeyboardInterrupt`` is reported as the outcome of that
call and ends nothing; after one, world calls other than ``close`` are refused.  A step or reset whose result cannot
be sent back is reported as having taken effect (``after_effect``).  The host exits when its request pipe closes:
after ``close`` that is the endpoint's normal shutdown; without a ``close`` (the endpoint is gone) the host first
runs the declared stop and then the environment's ``close``, each bounded.  Its exit is an ordinary interpreter exit,
so ``atexit`` handlers that the environment registered (cleanup of launched simulator processes) run; SIGTERM leads
to the same ordinary exit.

Standard library only, Python 3.8 syntax, and it never imports ``mhs``: the host may run under the simulator's own
interpreter (``MHS_SIM_HOST_PYTHON``; ROS Noetic ships Python 3.8).  Under the acceptance gate it applies the gate's
network and device guard (``MHS_SIM_HOST_GUARD``) before importing anything of the package, or refuses to start.
"""

import os
import sys

if __name__ == "__main__":
    # A script's directory is sys.path[0]; this one holds SDK modules named like standard ones (http, serial, ...).
    # Drop it before anything else is imported, so neither the host nor the environment can import them by accident.
    _HERE = os.path.dirname(os.path.realpath(__file__))
    if sys.path and os.path.realpath(sys.path[0] or os.curdir) == _HERE:
        del sys.path[0]

import importlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import queue  # noqa: E402
import signal  # noqa: E402
import threading  # noqa: E402
import types  # noqa: E402

PROTOCOL = "mhs-sim-host/1"
FDS_ENV = "MHS_SIM_HOST_FDS"
GUARD_ENV = "MHS_SIM_HOST_GUARD"
GUARDED_ENV = "MHS_PROCESS_GUARDED"
MAX_LINE = 16 * 1024 * 1024
MAX_DEPTH = 32
MAX_ITEMS = 1000000
#: The private package name the driver directory is imported under (never the endpoint's package name).
PACKAGE = "_mhs_sim_host_package"
_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_SPACE_NAMES = ("Discrete", "Box", "Dict", "MultiDiscrete", "MultiBinary", "Tuple")
#: Bound of each step the host takes on its own when the endpoint vanished (stop, the running call, close).
ORPHAN_BOUND_S = 10.0


class Refused(Exception):
    """A request this host refuses without calling the environment (``kind``: fenced, exited, busy, invalid)."""

    def __init__(self, kind, message):
        Exception.__init__(self, message)
        self.kind = kind


class AfterEffect(Exception):
    """The environment call returned, but its result cannot be sent back: it took effect, the outcome is unknown."""


def describe_error(exc):
    out = {"type": type(exc).__name__, "message": str(exc)[:500]}
    if isinstance(exc, Refused):
        out["refused"] = exc.kind
    if isinstance(exc, AfterEffect):
        out["after_effect"] = True
    if isinstance(exc, (SystemExit, KeyboardInterrupt)):
        out["exit"] = True
        code = getattr(exc, "code", None)
        out["code"] = code if isinstance(code, (int, str)) or code is None else repr(code)[:100]
    return out


# -- values --------------------------------------------------------------------------------------------------------
def _numpy_like(value):
    module = type(value).__module__ or ""
    return module == "numpy" or module.startswith("numpy.")


def jsonable(value, lossy=False, depth=0, budget=None):
    """A JSON value (NaN and infinities kept) of ``value``; with ``lossy`` an unknown leaf becomes a type label."""
    if budget is None:
        budget = [MAX_ITEMS]
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError("the value has too many items to send")
    if depth > MAX_DEPTH:
        raise ValueError("the value is nested too deeply to send")
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if _numpy_like(value) and callable(getattr(value, "tolist", None)):
        return jsonable(value.tolist(), lossy, depth + 1, budget)
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                if not lossy:
                    raise TypeError("mapping keys must be strings, got %s" % type(key).__name__)
                key = str(key)
            out[key] = jsonable(item, lossy, depth + 1, budget)
        return out
    if isinstance(value, (list, tuple)):
        return [jsonable(item, lossy, depth + 1, budget) for item in value]
    if lossy:
        return "<%s>" % type(value).__name__
    raise TypeError("%s cannot be sent to the endpoint" % type(value).__name__)


def scalar(value):
    """A JSON scalar (bool, int, float, str or None) of a read-back value; anything else is refused."""
    if _numpy_like(value) and callable(getattr(value, "item", None)):
        value = value.item()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError("the read-back field is a %s, not a scalar" % type(value).__name__)


def _flat(values):
    raw = values.tolist() if callable(getattr(values, "tolist", None)) else values
    out = []

    def walk(item):
        if isinstance(item, (list, tuple)):
            for element in item:
                walk(element)
        else:
            out.append(item)

    walk(raw)
    return out


def _shape(space):
    shape = getattr(space, "shape", None)
    return [int(item) for item in shape] if shape is not None else []


def space_kind(space):
    """The space family, by class name (subclasses included), as the endpoint's Gymnasium bridge reads it."""
    for cls in type(space).__mro__:
        if cls.__name__ in _SPACE_NAMES:
            return cls.__name__
    if hasattr(space, "low") and hasattr(space, "high"):
        return "Box"
    if hasattr(space, "nvec"):
        return "MultiDiscrete"
    return None


def describe_space(space, depth=0):
    if depth > 8:
        raise ValueError("spaces are nested too deeply")
    kind = space_kind(space)
    dtype = str(getattr(space, "dtype", "") or "")
    if kind == "Box":
        return {"kind": "Box", "low": [float(item) for item in _flat(space.low)],
                "high": [float(item) for item in _flat(space.high)], "shape": _shape(space), "dtype": dtype,
                "integer": dtype.startswith(("int", "uint", "bool"))}
    if kind == "Discrete":
        return {"kind": "Discrete", "n": int(space.n), "start": int(getattr(space, "start", 0) or 0)}
    if kind == "MultiDiscrete":
        start = getattr(space, "start", None)
        return {"kind": "MultiDiscrete", "nvec": [int(item) for item in _flat(space.nvec)],
                "start": [int(item) for item in _flat(start)] if start is not None else None,
                "shape": _shape(space), "dtype": dtype}
    if kind == "MultiBinary":
        n = space.n
        sizes = [int(item) for item in _flat(n)] if isinstance(n, (list, tuple)) or _numpy_like(n) else int(n)
        return {"kind": "MultiBinary", "n": sizes, "shape": _shape(space)}
    if kind == "Dict":
        members = getattr(space, "spaces", None)
        if not hasattr(members, "items"):
            raise ValueError("a Dict space without a mapping of spaces")
        pairs = []
        for key, sub in members.items():
            if not isinstance(key, str):
                raise ValueError("Dict space keys must be strings")
            pairs.append([key, describe_space(sub, depth + 1)])
        return {"kind": "Dict", "spaces": pairs}
    if kind == "Tuple":
        return {"kind": "Tuple", "spaces": [describe_space(sub, depth + 1) for sub in space.spaces]}
    raise ValueError("unsupported space %s" % type(space).__name__)


def to_native(value, space):
    """The JSON action in the real space's containers, exactly as the in-process Gymnasium bridge converts it."""
    kind = space_kind(space)
    if kind == "Discrete":
        return int(value)
    if kind in ("Box", "MultiDiscrete", "MultiBinary"):
        low = getattr(space, "low", None)
        if low is not None and _numpy_like(low):
            numpy = importlib.import_module("numpy")
            array = numpy.asarray(value, dtype=getattr(space, "dtype", None))
            shape = tuple(_shape(space))
            return array.reshape(shape) if shape else array
        return list(value)
    if kind == "Dict" and isinstance(value, dict):
        return {key: to_native(value[key], sub) for key, sub in space.spaces.items()}
    if kind == "Tuple" and isinstance(value, (list, tuple)):
        return tuple(to_native(item, sub) for item, sub in zip(value, space.spaces))
    return value


def valid_path(path):
    """A public attribute path: dot-separated identifiers that start with a letter."""
    parts = path.split(".") if isinstance(path, str) and len(path) <= 200 else []
    return bool(parts) and all(part and part[0] in _LETTERS and all(char.isalnum() or char == "_" for char in part)
                               and part.isascii() for part in parts)


# -- the channel ---------------------------------------------------------------------------------------------------
class Channel(object):
    def __init__(self, read_fd, write_fd):
        self.read_fd = read_fd
        self.write_fd = write_fd
        self.buffer = bytearray()
        self.write_lock = threading.Lock()
        self.gone = False

    def receive(self):
        """The next request, or None when the pipe closed (the endpoint closed it or is gone)."""
        while True:
            index = self.buffer.find(b"\n")
            if index >= 0:
                line = bytes(self.buffer[:index])
                del self.buffer[:index + 1]
                if not line.strip():
                    continue
                try:
                    document = json.loads(line.decode("utf-8"))
                except ValueError:
                    return {"op": "invalid"}
                return document if isinstance(document, dict) else {"op": "invalid"}
            if len(self.buffer) > MAX_LINE:
                return None
            chunk = os.read(self.read_fd, 65536)
            if not chunk:
                return None
            self.buffer += chunk

    def send(self, document):
        try:
            data = (json.dumps(document, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError) as exc:
            data = (json.dumps({"id": document.get("id"), "ok": False,
                                "error": {"type": type(exc).__name__,
                                          "message": "the reply cannot be encoded: %s" % str(exc)[:300]}})
                    + "\n").encode("utf-8")
        if len(data) > MAX_LINE:
            data = (json.dumps({"id": document.get("id"), "ok": False,
                                "error": {"type": "ValueError", "message": "the reply exceeds %d bytes" % MAX_LINE}})
                    + "\n").encode("utf-8")
        with self.write_lock:
            if self.gone:
                return
            view = memoryview(data)
            try:
                while view:
                    written = os.write(self.write_fd, view)
                    view = view[written:]
            except OSError:
                self.gone = True


# -- the host ------------------------------------------------------------------------------------------------------
class Lane(object):
    """One worker thread running one request at a time."""

    def __init__(self, name, handler, channel):
        self.name = name
        self.handler = handler
        self.channel = channel
        self.queue = queue.Queue()
        self.busy = False
        self.idle = threading.Event()
        self.idle.set()
        self.thread = threading.Thread(target=self.run, name="mhs-sim-host-" + name)
        self.thread.daemon = True
        self.thread.start()

    def submit(self, rid, op, request):
        self.busy = True
        self.idle.clear()
        self.queue.put((rid, op, request))

    def run(self):
        while True:
            item = self.queue.get()
            rid, op, request = item
            try:
                result = self.handler(op, request)
                reply = {"id": rid, "ok": True, "result": result}
            except BaseException as exc:  # noqa: BLE001 - SystemExit and KeyboardInterrupt are outcomes here
                reply = {"id": rid, "ok": False, "error": describe_error(exc)}
            self.busy = False
            self.idle.set()
            if rid is not None:
                self.channel.send(reply)


class Host(object):
    def __init__(self, channel):
        self.channel = channel
        self.lock = threading.Lock()
        self.env = None
        self.config = None
        self.fenced = False
        self.world_active = False
        self.exit_requested = None
        self.closed = False
        self.world = None
        self.control = None

    # -- start --------------------------------------------------------------------------------------------------
    def init(self, request):
        package_dir, entry = request.get("package_dir"), request.get("entry")
        kwargs = request.get("kwargs") or {}
        stop, readback = request.get("stop"), request.get("readback") or {}
        if request.get("protocol") != PROTOCOL:
            raise Refused("invalid", "protocol %r is not %r" % (request.get("protocol"), PROTOCOL))
        if not isinstance(package_dir, str) or not os.path.isdir(package_dir):
            raise Refused("invalid", "the package directory does not exist")
        if not isinstance(entry, str) or not entry.startswith(".") or ":" not in entry:
            raise Refused("invalid", "the entry must be a package-relative '.module:attribute'")
        if not isinstance(readback, dict) or not valid_path(stop) or not valid_path(readback.get("path")) or (
                readback.get("field") is not None and not valid_path(readback.get("field"))):
            raise Refused("invalid", "the stop and read-back must be public attribute paths")
        if not isinstance(kwargs, dict):
            raise Refused("invalid", "kwargs must be an object")
        self.apply_guard()
        sys.dont_write_bytecode = True
        package = types.ModuleType(PACKAGE)
        package.__path__ = [package_dir]
        package.__package__ = PACKAGE
        package.__file__ = None
        sys.modules[PACKAGE] = package
        module_name, _, attribute = entry.partition(":")
        target = importlib.import_module(module_name, PACKAGE)
        for part in attribute.split("."):
            target = getattr(target, part)
        if not callable(target):
            raise Refused("invalid", "the entry %s is not callable" % entry)
        env = target(**kwargs)
        if env is None:
            raise Refused("invalid", "the entry returned None, not an environment")
        self.env = env
        self.config = {"stop": stop, "readback": readback}
        return {"protocol": PROTOCOL, "pid": os.getpid(), "python": list(sys.version_info[:3]),
                "action_space": describe_space(env.action_space),
                "observation_space": describe_space(env.observation_space)}

    @staticmethod
    def apply_guard():
        if os.environ.get(GUARDED_ENV) != "1":
            return
        path = os.environ.get(GUARD_ENV)
        if not path or not os.path.isfile(path):
            raise Refused("invalid", "the process guard of the gate is required here but its module is missing")
        spec = importlib.util.spec_from_file_location("_mhs_sim_host_guard", path)
        if spec is None or spec.loader is None:
            raise Refused("invalid", "the process guard of the gate cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.guard_process()

    # -- lanes --------------------------------------------------------------------------------------------------
    def target(self):
        env = self.env
        unwrapped = getattr(env, "unwrapped", None)
        return env if unwrapped is None else unwrapped

    def resolve(self, path):
        value = self.target()
        for part in path.split("."):
            value = getattr(value, part)
        if not callable(value):
            raise Refused("invalid", "%s is not callable" % path)
        return value

    def world_call(self, op, request):
        with self.lock:
            if self.exit_requested is not None and op != "close":
                raise Refused("exited", "the environment requested interpreter exit earlier (%s); only close is "
                              "accepted" % self.exit_requested)
            if op in ("step", "reset") and self.fenced:
                raise Refused("fenced", "a stop fenced this host; world calls wait for the endpoint's safety reset")
            if op not in ("step", "reset", "close"):
                raise Refused("invalid", "unknown world call %r" % op)
            self.world_active = True
        try:
            if op == "step":
                action = to_native(request.get("action"), self.env.action_space)
                result = self.env.step(action)
                try:
                    if not isinstance(result, tuple) or len(result) not in (4, 5):
                        raise TypeError("env.step returned %s, not a 4- or 5-tuple" % type(result).__name__)
                    items = list(result)
                    return {"result": [jsonable(item) for item in items[:-1]] + [jsonable(items[-1], lossy=True)]}
                except Exception as exc:  # noqa: BLE001 - the step ran: its effect is real, its result unknown
                    raise AfterEffect("env.step returned, but its result cannot be sent: %s: %s"
                                      % (type(exc).__name__, str(exc)[:300]))
            if op == "reset":
                result = self.env.reset(**(request.get("kwargs") or {}))
                try:
                    if isinstance(result, tuple) and len(result) == 2:
                        return {"result": [jsonable(result[0]), jsonable(result[1], lossy=True)], "pair": True}
                    return {"result": jsonable(result), "pair": False}
                except Exception as exc:  # noqa: BLE001
                    raise AfterEffect("env.reset returned, but its result cannot be sent: %s: %s"
                                      % (type(exc).__name__, str(exc)[:300]))
            close = getattr(self.env, "close", None)
            try:
                if callable(close):
                    close()
            finally:
                with self.lock:
                    self.closed = True
            return {"closed": True}
        except (SystemExit, KeyboardInterrupt) as exc:
            with self.lock:
                self.exit_requested = "%s(%r)" % (type(exc).__name__, getattr(exc, "code", None))
            raise
        finally:
            with self.lock:
                self.world_active = False

    def stop(self):
        with self.lock:
            self.fenced = True
            active = self.world_active
        self.resolve(self.config["stop"])()
        return active

    def control_call(self, op, request):
        if op == "stop":
            return {"world_active": self.stop()}
        if op == "readback":
            readback = self.config["readback"]
            value = self.resolve(readback["path"])()
            field = readback.get("field")
            if field:
                for part in field.split("."):
                    value = value[part] if isinstance(value, dict) else getattr(value, part)
            return {"value": scalar(value)}
        raise Refused("invalid", "unknown control call %r" % op)

    # -- serving ------------------------------------------------------------------------------------------------
    def serve(self):
        first = self.channel.receive()
        if first is None:
            return
        rid = first.get("id")
        if first.get("op") != "init":
            self.channel.send({"id": rid, "ok": False, "error": describe_error(Refused("invalid", "init first"))})
            return
        try:
            result = self.init(first)
        except BaseException as exc:  # noqa: BLE001 - a failed construction (SystemExit included) is an outcome
            self.channel.send({"id": rid, "ok": False, "error": describe_error(exc)})
            return
        self.channel.send({"id": rid, "ok": True, "result": result})
        self.world = Lane("world", self.world_call, self.channel)
        self.control = Lane("control", self.control_call, self.channel)
        while True:
            request = self.channel.receive()
            if request is None:
                with self.lock:
                    closed = self.closed
                if not closed:
                    self.orphaned()
                return
            self.dispatch(request)

    def dispatch(self, request):
        rid, op = request.get("id"), request.get("op")
        if op in ("step", "reset", "close"):
            lane = self.world
        elif op in ("stop", "readback"):
            lane = self.control
        elif op == "unfence":
            with self.lock:
                self.fenced = False
                active = self.world_active
            self.channel.send({"id": rid, "ok": True, "result": {"fenced": False, "world_active": active}})
            return
        elif op == "ping":
            with self.lock:
                state = {"fenced": self.fenced, "world_active": self.world_active,
                         "exit_requested": self.exit_requested, "closed": self.closed}
            self.channel.send({"id": rid, "ok": True, "result": state})
            return
        else:
            error = describe_error(Refused("invalid", "unknown op %r" % (op,)))
            self.channel.send({"id": rid, "ok": False, "error": error})
            return
        if lane.busy:
            error = describe_error(Refused("busy", "the %s lane is still running a call" % lane.name))
            self.channel.send({"id": rid, "ok": False, "error": error})
            return
        lane.submit(rid, op, request)

    def orphaned(self):
        """The endpoint vanished without closing: stop the simulator, let a running call end, close; each bounded."""
        if self.control is not None and not self.control.busy:
            self.control.submit(None, "stop", {})
            self.control.idle.wait(ORPHAN_BOUND_S)
        if self.world is not None:
            self.world.idle.wait(ORPHAN_BOUND_S)
            if not self.world.busy:
                self.world.submit(None, "close", {})
                self.world.idle.wait(ORPHAN_BOUND_S)


def _terminate(signum, frame):
    raise SystemExit(128 + signum)


def main():
    fds = os.environ.get(FDS_ENV, "")
    try:
        read_fd, write_fd = (int(item) for item in fds.split(","))
    except ValueError:
        sys.stderr.write("mhs sim host: %s is not set; this file is started by mhs.bridge.sim_host\n" % FDS_ENV)
        return 2
    signal.signal(signal.SIGTERM, _terminate)
    host = Host(Channel(read_fd, write_fd))
    try:
        host.serve()
    except SystemExit:
        # SIGTERM (the endpoint's close bound passed): an ordinary exit, so atexit cleanup still runs.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
