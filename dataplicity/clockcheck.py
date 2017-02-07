"""
On RPi, threading.Event objects block indefinitely when the clock
changes, causing agent to hang. This thread kills the current
process when the clock changes. Supervisor will then restart agent,
and we can recover.

It's not nice at all. Probably the result of an OS bug. Hopefully,
there will be a better solution in future.

"""

import os
import signal
from time import sleep, time
from threading import Thread


CHECK_PERIOD = 1.0
MAX_CLOCK_DISCREPENCY = 10.0


class ClockCheckThread(Thread):
    """Thread to restart agent when the clock changes."""

    def __init__(self):
        super(ClockCheckThread, self).__init__()
        self.daemon = True
        self.running = True

    def run(self):
        """Calls `on_fail` when the system clock changes."""
        while self.running:
            start = time()
            sleep(CHECK_PERIOD)
            elapsed = time() - start

            if elapsed > MAX_CLOCK_DISCREPENCY:
                self.on_fail()

    def on_fail(self):
        """Clock has changed, kill the current process."""
        # Supervisor will restart the agent.
        pid = os.getpid()
        os.kill(pid, signal.SIGKILL)
