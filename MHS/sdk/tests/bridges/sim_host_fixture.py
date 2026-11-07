"""A synthetic environment that the isolated simulator host imports in its child process (tests only).

Standard library only, and it imports nothing of ``mhs`` or ``tests``: the host loads this directory as a private
package.  ``make(**options)`` builds a world that advances only inside a step; ``conn.pause()`` stops it and
``conn.properties()`` reads it back.  The options are switches for the test cases (construction failures, exits,
delays, a stop that does not take effect, a step that unpauses at its end, loud output, an event log).
"""

import importlib.util
import os
import socket
import sys
import time


class Box:
    def __init__(self, low, high):
        self.low, self.high, self.shape, self.dtype = list(low), list(high), (len(low),), "float64"


class Properties:
    def __init__(self, paused):
        self.paused = paused
        self.success = True


class Conn:
    def __init__(self, env):
        self.env = env
        self.paused = False
        self.pauses = 0

    def pause(self):
        self.env.log("pause")
        self.pauses += 1
        if self.env.options.get("stop_error"):
            raise RuntimeError("the pause service failed")
        if self.env.options.get("stop_exit"):
            raise SystemExit(7)
        if self.env.options.get("stop_hang"):
            time.sleep(float(self.env.options["stop_hang"]))
        if not self.env.options.get("ignore_stop"):
            self.paused = True

    def properties(self):
        self.env.log("readback")
        return Properties(self.paused)

    def dictionary(self):
        return {"paused": self.paused, "nested": {"paused": self.paused}}

    def vector(self):
        return {"paused": [self.paused]}


class Env:
    def __init__(self, **options):
        self.options = options
        self.conn = Conn(self)
        self.position = [0.0, 0.0]
        self.steps = 0
        self.action_space = Box([-1.0, -1.0], [1.0, 1.0])
        self.observation_space = Box([float("-inf")] * 3, [float("inf")] * 3)
        construct = options.get("construct")
        if construct == "raise":
            raise ValueError("the simulator could not be launched")
        if construct == "exit":
            raise SystemExit(3)
        if construct == "hang":
            time.sleep(60)
        if construct == "network":
            socket.create_connection(("192.0.2.1", 80), timeout=0.5)
        self.log("constructed")

    def log(self, event):
        path = self.options.get("log")
        if path:
            with open(path, "a") as handle:
                handle.write(event + "\n")

    def observation(self):
        return [self.position[0], self.position[1], float(self.steps)]

    def reset(self, seed=None, options=None):
        self.log("reset")
        self.position = [0.0, 0.0]
        info = {"seed": seed, "options": options,
                "mhs_modules": sorted(name for name in sys.modules if name == "mhs" or name.startswith("mhs.")),
                "sdk_bridge_dir_importable": importlib.util.find_spec("gym_async") is not None}
        return self.observation(), info

    def step(self, action):
        self.log("step")
        what = self.options.get("step")
        self.conn.paused = False          # the world runs while a step runs
        if self.options.get("loud"):
            sys.stdout.write("x" * 200000 + "\n")
            sys.stderr.write("y" * 200000 + "\n")
            os.write(1, b"raw stdout line\n")
        delay = float(self.options.get("step_delay") or 0.0)
        if delay:
            time.sleep(delay)
        if what == "raise":
            raise ValueError("the step failed")
        if what == "exit":
            raise SystemExit(4)
        if what == "die":
            os._exit(9)
        self.position = [p + 0.1 * float(a) for p, a in zip(self.position, action)]
        self.steps += 1
        if self.options.get("unpause_at_end"):
            self.conn.paused = False      # resumes the world as it ends, after any stop it did not see
        else:
            self.conn.paused = True       # like a pause-after-step environment
        observation = self.observation()
        if what == "bad_result":
            observation = object()
        return observation, -abs(self.position[0]), False, False, {"steps": self.steps, "object": object()}

    def close(self):
        self.log("close")
        if self.options.get("close") == "hang":
            time.sleep(60)
        if self.options.get("close") == "exit":
            raise SystemExit(0)


class Wrapper:
    """A Gymnasium-style wrapper: the host resolves the stop and read-back paths on ``unwrapped``."""

    def __init__(self, env):
        self.env = env
        self.action_space = env.action_space
        self.observation_space = env.observation_space
        self.unwrapped = env

    def reset(self, **kwargs):
        return self.env.reset(**kwargs)

    def step(self, action):
        return self.env.step(action)

    def close(self):
        return self.env.close()


def make(**options):
    return Env(**options)


def make_wrapped(**options):
    return Wrapper(Env(**options))
