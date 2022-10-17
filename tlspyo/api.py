import time
from socket import AF_INET, SOCK_STREAM, socket
import pickle as pkl
from threading import Thread, Lock, Event
from multiprocessing import Process
from copy import deepcopy
import signal

from tlspyo.server import Server
from tlspyo.client import Client


class Relay:
    def __init__(self, port, password, accepted_groups=None, local_com_port=2097, header_size=10):
        self._header_size = header_size
        self._local_com_port = local_com_port
        self._local_com_srv = socket(AF_INET, SOCK_STREAM)
        self._local_com_srv.bind(('127.0.0.1', self._local_com_port))
        self._local_com_srv.listen()
        self._server = Server(port=port,
                              password=password,
                              accepted_groups=accepted_groups,
                              local_com_port=local_com_port,
                              header_size=header_size)
        self._p = Process(target=self._server.run, args=())
        self._p.start()
        self._local_com_conn, self._local_com_addr = self._local_com_srv.accept()

    def stop(self):
        msg = pkl.dumps(('STOP', None))
        msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
        self._local_com_conn.sendall(msg)

        self._p.join()
        self._local_com_conn.close()
        self._local_com_addr = None


class Endpoint:
    def __init__(self, ip_server, port_server, password, groups=None, local_com_port=2097, header_size=10, max_buf_len=4096):

        # threading for local object receiving
        self.__obj_buffer = []
        self.__obj_buffer_lock = Lock()
        self.__obj_buffer_event = Event()  # set when the buffer is not empty, cleared otherwise

        # networking (local and internet)
        if isinstance(groups, str):
            groups = (groups, )
        self._header_size = header_size
        self._max_buf_len = max_buf_len
        self._local_com_port = local_com_port
        self._local_com_srv = socket(AF_INET, SOCK_STREAM)
        self._client = Client(ip_server=ip_server,
                              port_server=port_server,
                              password=password,
                              groups=groups,
                              local_com_port=local_com_port,
                              header_size=header_size)

        # start local server and Twisted process
        self._local_com_srv.bind(('127.0.0.1', self._local_com_port))
        self._local_com_srv.listen()
        self._p = Process(target=self._client.run, args=())
        self._p.start()
        self._local_com_conn, self._local_com_addr = self._local_com_srv.accept()

        self._t_manage_received_objects = Thread(target=self._manage_received_objects, daemon=True)
        self._t_manage_received_objects.start()

        # TODO: change this for a proper handshake with the local socket:
        time.sleep(1.0)  # let things connect

    def __wait_event(self, granularity=0.1):
        """
        Workaround for an Event bug on Windows.

        See: https://bugs.python.org/issue35935
        """
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.__obj_buffer_event.wait()

    def _manage_received_objects(self):
        """
        Called in its own thread.
        """
        buf = b""
        while True:
            buf += self._local_com_conn.recv(self._max_buf_len)
            i, j = self._process_header(buf)
            while j <= len(buf):
                stamp, cmd, obj = pkl.loads(buf[i:j])
                if cmd == "OBJ":
                    with self.__obj_buffer_lock:
                        self.__obj_buffer.append(pkl.loads(obj))
                        self.__obj_buffer_event.set()  # before releasing lock
                buf = buf[j:]
                i, j = self._process_header(buf)

    def _process_header(self, buf):
        i = self._header_size
        if len(buf) < i:
            return 0, len(buf) + 1
        data_len = int(buf[:self._header_size])
        j = i + data_len
        return i, j

    def _send_local(self, cmd, dest, obj):
        msg = pkl.dumps((cmd, dest, pkl.dumps(obj)))
        msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
        self._local_com_conn.sendall(msg)

    def send_object(self, obj, destination):
        """
        Either broadcast object to destination group(s) or send it as a consumable.

        obj can be any picklable python object.
        destination can either be:
            - a string (single group)
            - a tuple of strings (set of groups)
            - a dictionary where keys are strings (group) and values are integers (number of copies for the group)

        When destination is a string or a tuple of strings, the object will be broadcast to corresponding group(s).
        When destination is a dictionary, each key is a destination group. For each corresponding value:
            - If the value is N < 0, the object is broadcast to the group.
            - If the value is N > 0, N objects are sent to the group to be consumed. To consume an object, the Endpoint
                first needs to signal itself as idle for the corresponding group with Endpoint.notify().

        :param obj: object: picklable object to broadcast to destination
        :param destination: object: destination group(s)
        """
        if isinstance(destination, str):
            destination = {destination: -1}
        elif isinstance(destination, tuple) or isinstance(destination, list):
            destination = {dest: -1 for dest in destination}
        else:
            assert isinstance(destination, dict), f"destination must be either of: str, (str), dict."
            for k, v in destination.items():
                assert isinstance(k, str), f"destination keys must be strings."
                assert isinstance(v, int), f"destination values must be integers."
        self._send_local(cmd='OBJ', dest=destination, obj=obj)

    def produce(self, obj, group):
        """
        Alias for send_object(obj=obj, destination={group: 1}).

        :param obj: object: object to send as consumable
        :param group: str: target group
        """
        assert isinstance(group, str), f"group must be a string, not {type(group)}"
        self.send_object(obj=obj, destination={group: 1})

    def notify(self, origins):
        """
        Notifies the Relay that the Endpoint is ready to retrieve consumables from origins.

        origins can either be:
            - a string (single group)
            - a tuple of strings (set of groups)
            - a dictionary where keys are strings (group) and values are integers (number of consumables from the group)

        When origins is a string or a tuple of strings, 1 consumable will be retrieved per corresponding group(s).
        When origins is a dictionary, each key is an origin group. For each corresponding value:
            - If the value is N < 0, all available consumables are retrieved from the group.
            - If the value is N > 0, at most N available consumables are retrieved from the group.

        In any case, the group strings must be a subset of the Endpoint's groups.

        :param origins: object: origins of the consumables.
        """
        if isinstance(origins, str):
            origins = {origins: 1}
        elif isinstance(origins, tuple) or isinstance(origins, list):
            origins = {dest: 1 for dest in origins}
        else:
            assert isinstance(origins, dict), f"origins must be either of: str, (str), dict."
            for k, v in origins.items():
                assert isinstance(k, str), f"origins keys must be strings."
                assert isinstance(v, int), f"origins values must be integers."
        self._send_local(cmd='NTF', dest=origins, obj=None)

    def stop(self):
        # send STOP to the local server
        self._send_local(cmd='STOP', dest=None, obj=None)

        # join Twisted process and stop local server
        self._p.join()
        self._local_com_conn.close()
        self._local_com_addr = None

    def receive_all(self, blocking=False):
        """
        Returns all received objects in a list, from oldest to newest.

        :param blocking: bool: If True, the call blocks until objects are available. Otherwise, the list may be empty.
        :return: list: received objects
        """
        if blocking:
            self.__wait_event()

        with self.__obj_buffer_lock:
            assert not blocking or len(self.__obj_buffer) > 0, f'The buffer is unexpectedly empty.'
            cpy = deepcopy(self.__obj_buffer)
            self.__obj_buffer = []
            self.__obj_buffer_event.clear()  # before releasing lock

        return cpy

    def pop(self, max_items=1, blocking=False):
        """
        Returns at most max_items oldest received objects.

        :param max_items:int: desired max number of items.
        :param blocking: bool: If True, the call blocks until max_items are retrieved.
            Otherwise, the list may be empty or contain less than max_items.
        :return: list: returned items
        """
        cpy = []
        while True:
            if blocking:
                self.__wait_event()
            with self.__obj_buffer_lock:
                assert not blocking or len(self.__obj_buffer) > 0, f'The buffer is unexpectedly empty.'
                if len(self.__obj_buffer) >= max_items:
                    cpy += deepcopy(self.__obj_buffer[:max_items])
                    self.__obj_buffer = self.__obj_buffer[max_items:]
                else:
                    cpy += deepcopy(self.__obj_buffer)
                    self.__obj_buffer = []
                if len(self.__obj_buffer) == 0:
                    self.__obj_buffer_event.clear()  # before releasing lock
            if not blocking or len(cpy) >= max_items:
                break
        return cpy

    def pop_lifo(self, max_items=1, clear=False, blocking=False):
        """
        Returns at most max_items from the object buffer using a LIFO stack implementation.
        :param max_items:int: maximum number of items to return
        :param clear:bool: Indicates whether the buffer should be cleared when called.
        :param blocking: bool: If True, the call blocks until max_items are retrieved.
            Otherwise, the list may be empty or contain less than max_items.
        :return: list: The returned items
        """
        cpy = []
        while True:
            if blocking:
                self.__wait_event()
            with self.__obj_buffer_lock:
                if len(self.__obj_buffer) >= max_items:
                    cpy += deepcopy(self.__obj_buffer[-max_items:])
                    if clear:
                        self.__obj_buffer = []
                    else:
                        self.__obj_buffer = self.__obj_buffer[:-max_items]
                else:
                    cpy += deepcopy(self.__obj_buffer)
                    self.__obj_buffer = []
                if len(self.__obj_buffer) == 0:
                    self.__obj_buffer_event.clear()  # before releasing lock
            if not blocking or len(cpy) >= max_items:
                break
        return cpy
