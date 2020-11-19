import logging
import select
import time
import threading


READ_EVENTS = select.POLLIN | select.POLLPRI  # Data in , priority data in
ERROR_EVENTS = select.POLLERR | select.POLLHUP  #  Error or hang up


TARGET_QUEUE_FULL = 0
TARGET_ACCEPTED = 1
TARGET_QUEUED = 2


log = logging.getLogger("agent")


class EventTarget:
    def __init__(self, fd, group, queue_size=0, max_queue_time=5):
        """Create event target.

        Args:
            fd (Socket/file/file descriptor): A file descriptor or an object with fileno() (such as a socket or file)
            group (str): A group to use when queueing.
            queue_size (int, optional): [description]. Defaults to 0.
        """
        self.fd = fd
        self.group = group
        self.queue_size = queue_size
        self.max_queue_time = max_queue_time
        self._created_time = time.time()

    def fileno(self):
        """Get the file descriptor number.

        Returns:
            [int]: A file descriptor
        """
        if hasattr(self.fd, "fileno"):
            return self.fd.fileno()
        else:
            return self.fd

    def expired(self):
        """Check if a queued target has expired."""
        return time.time() > self._created_time + self.max_queue_time

    def on_data_available(self):
        """Socket / file has data."""

    def on_error(self):
        """Socket / file is in an error state."""

    def on_hang_up(self):
        """Socket / file has closed."""

    def on_queue_full(self):
        """Target was rejected because the queue was full."""

    def on_expired(self):
        """Target expired while waiting for queue."""


class Group(object):
    """Defines a group of similar event targets."""

    def __init__(self, max_size, queue_size=0):
        """Create a Group.

        Args:
            max_size (int): Maximum number targets in a group.
            queue_size (int, optional): Number of additional targets that may be queued. Defaults to 0.
        """
        self.max_size = max_size
        self.queue_size = queue_size
        self.size = 0
        self.queue = []

    @property
    def full(self):
        """Check if the group is full."""
        return self.size == self.max_size


class EventLoop(threading.Thread):
    """A single thread which polls file descriptors and dispatches events."""

    def __init__(self, exit_event):
        """Create an event loop.

        Args:
            exit_event (Event): A threading event that indicates the service is closing.
        """
        self.exit_event = exit_event
        self._poll = select.poll()
        self._lock = threading.RLock()
        self._targets = {}
        self._groups = {}
        super(EventLoop, self).__init__()
        self.daemon = True

    def add_group(self, name, size, queue_size):
        """Add a target group.

        Args:
            name (str): Name of group used as identifier.
            size (int): Size of group before queueing.
            queue_size (int): Maximum number of targets that can be queued before rejection.
        """
        self._groups[name] = Group(size, queue_size)

    def add_target(self, event_target):
        """Add a target to the vent loop

        Args:
            event_target (EventTarget): An event target object.
        """
        with self._lock:
            fileno = event_target.fileno()
            group = self._groups[event_target.group]
            if group is not None:
                if group.full:
                    if len(group.queue) < group.max_queue_size:
                        group.queue.append(event_target)
                        return TARGET_QUEUED  # Target is queued for later
                    else:
                        event_target.on_queue_full()
                        return TARGET_QUEUE_FULL  # Queue full and target was not added

            self._targets[fileno] = event_target
            self._poll.register(fileno, READ_EVENTS | ERROR_EVENTS)
            self._groups[event_target.group].size += 1
        return TARGET_ACCEPTED  # Target was added

    def flush_queue(self):
        """Add any queued targets to the event loop."""
        with self._lock:
            for group in self._groups.values():
                expired = []
                queue = []
                for target in group.queue:
                    if target.expired:
                        expired.append(target)
                    else:
                        queue.append(target)
                for target in expired:
                    try:
                        target.on_expired()
                    except Exception as error:
                        log.exception("error in %r expired()", target)
                group.queue[:] = queue
                while group.queue and group.size < group.max_size:
                    if self.add_target(group.queue[-1]) == TARGET_ACCEPTED:
                        group.queue.pop()

    def remove_target(self, event_target):
        """Remove a target from the event loop.
        
        Args:
            event_target (EventTarget): An event target object.

        """
        with self._lock:
            fileno = event_target.fileno()
            target = self._targets.pop(fileno, None)
            if target is not None:
                self._poll.unregister(fileno)
                self._groups[event_target.group].size -= 1

    def run(self):
        """Polls and dispatches events."""

        while not self.exit_event.is_set():
            try:
                poll_result = self._poll.poll(1000)
            except Exception as error:
                log.error("error in poll", error)
                time.sleep(1)  # We don't want to get stuck in a spin-loop
                continue
            self.flush_queue()
            if not poll_result:
                continue
            for fileno, event_mask in poll_result:
                with self._lock:
                    try:
                        target = self._targets[fileno]
                    except KeyError:
                        del self._targets[fileno]
                        continue
                if event_mask & READ_EVENTS:
                    try:
                        target.on_data_available()
                    except Exception as error:
                        log.exception("error in %r on_data_available")
                if event_mask & select.POLLERR:
                    try:
                        target.on_error()
                    except Exception as error:
                        log.exception("error in %r on_error")
                if event_mask & select.POLLHUP:
                    try:
                        target.on_hang_up()
                    except Exception as error:
                        log.exception("error in %r on_hang_up")

