# import signal
import queue


# try:
#     signal.signal(signal.SIGINT, signal.SIG_DFL)
# except Exception as e:
#     pass


def wait_event(event):
    """
    Workaround for an Event bug on Windows.

    See: https://bugs.python.org/issue35935
    """
    event.wait()


def get_from_queue(q, blocking=False):
    try:
        return [q.get(block=blocking)]
    except queue.Empty:
        return []
