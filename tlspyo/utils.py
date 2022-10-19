import signal
import queue

def wait_event(event):
    """
    Workaround for an Event bug on Windows.

    See: https://bugs.python.org/issue35935
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    event.wait()


def get_from_queue(q, blocking=False):
    try:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        return [q.get(block=blocking)]
    except queue.Empty:
        return []
