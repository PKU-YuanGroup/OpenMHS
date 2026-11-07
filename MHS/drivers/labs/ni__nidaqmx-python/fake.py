"""Fake backend of the NI-DAQmx driver: an in-memory stand-in for nidaqmx.task._task:Task.

Gate G7: every public member defined here exists on the upstream class nidaqmx.task._task:Task
(generated/nidaqmx/task/_task.py:64).  ``channel_names`` (177-181), ``is_task_done`` (379-392), ``read`` (523),
``start`` (1207), ``stop`` (1227) and ``close`` (364) are its members; the signatures mirror the upstream ones,
where ``read`` takes the number of samples and a timeout.

The starting values are test data, not device facts (each one is marked ``# placeholder``): they are the state of
this stand-in only, never a Fact, a Limit or a reference.  A software-timed read of the real device returns the
voltage it sampled; this stand-in returns the same fixed voltage every time, so reading the state twice gives the
same state.  Nothing here talks to a device.
"""


class FakeTask:
    def __init__(self, **_options):
        self._channels = ["Dev1/ai0"]    # placeholder test data: the one configured virtual channel
        self._volts = 1.25               # placeholder test data: the voltage a read returns
        self._done = True                # placeholder test data: a task that was never started is done
        self._closed = False

    @property
    def channel_names(self):
        """List[str]: the names of the virtual channels in the task (upstream line 177-181)."""
        return list(self._channels)

    def is_task_done(self):
        """bool: whether the measurement completed (upstream line 379-392)."""
        return self._done

    def read(self, number_of_samples_per_channel=None, timeout=10.0):
        """The samples of one read: a scalar when no sample count is given, a list otherwise (upstream line 523)."""
        if number_of_samples_per_channel is None:
            self._done = True
            return self._volts
        count = int(number_of_samples_per_channel)
        self._done = True
        return [self._volts] * count     # placeholder test data: the same fixed sample, count times

    def start(self):
        """Start the task: it is no longer done until the measurement finishes (upstream line 1207)."""
        self._done = False

    def stop(self):
        """Stop the task: it returns to the state before start (upstream line 1227)."""
        self._done = True

    def close(self):
        """Clear the task and release its resources (upstream line 364)."""
        self._closed = True
