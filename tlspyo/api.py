import queue
import time
from socket import AF_INET, SOCK_STREAM, socket
import pickle as pkl
from threading import Thread, Lock, Event
from multiprocessing import Process
from copy import deepcopy
import signal

from tlspyo.server import Server
from tlspyo.client import Client

from tlspyo.utils import get_from_queue, wait_event

import logging


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
        self._stopped = False

    def __del__(self):
        self.stop()

    def stop(self):
        if not self._stopped:
            self._stopped = True
            msg = pkl.dumps(('STOP', None))
            msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
            self._local_com_conn.sendall(msg)

            self._p.join()
            self._local_com_conn.close()
            self._local_com_srv.close()
            self._local_com_addr = None


class Endpoint:
    def __init__(self, ip_server, port, password, groups=None, local_com_port=2097, header_size=10, max_buf_len=4096):

        # threading for local object receiving
        self.__obj_buffer = queue.Queue()
        # self.__obj_buffer_lock = Lock()
        # self.__obj_buffer_event = Event()  # set when the buffer is not empty, cleared otherwise
        self.__socket_closed_lock = Lock() 
        self.__socket_closed_flag = False
    
        # networking (local and internet)
        if isinstance(groups, str):
            groups = (groups, )
        self._header_size = header_size
        self._max_buf_len = max_buf_len
        self._local_com_port = local_com_port
        self._local_com_srv = socket(AF_INET, SOCK_STREAM)
        self._client = Client(ip_server=ip_server,
                              port_server=port,
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

        self._stopped = False

    def __del__(self):
        self.stop()

    def _manage_received_objects(self):
        """
        Called in its own thread.
        """
        buf = b""
        while True:
            # Check if socket is still open
            with self.__socket_closed_lock:
                if self.__socket_closed_flag:
                    self._local_com_conn.close()
                    return

            buf += self._local_com_conn.recv(self._max_buf_len)
            i, j = self._process_header(buf)
            while j <= len(buf):
                stamp, cmd, obj = pkl.loads(buf[i:j])
                if cmd == "OBJ":
                    self.__obj_buffer.put(pkl.loads(obj))  # TODO: maxlen
                    # with self.__obj_buffer_lock:
                    #     self.__obj_buffer.append(pkl.loads(obj))
                    #     self.__obj_buffer_event.set()  # before releasing lock
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
        assert len(destination.keys()) > 0, f"Please specify at least one group to be notified"
        self._send_local(cmd='OBJ', dest=destination, obj=obj)

    def produce(self, obj, group):
        """
        Alias for send_object(obj=obj, destination={group: 1}).

        :param obj: object: object to send as consumable
        :param group: str: target group
        """
        assert isinstance(group, str), f"group must be a string, not {type(group)}"
        self.send_object(obj=obj, destination={group: 1})

    def notify(self, groups):
        """
        Notifies the Relay that the Endpoint is ready to retrieve consumables from destination groups.

        groups can either be:
            - a string (single group)
            - a tuple of strings (set of groups)
            - a dictionary where keys are strings (group) and values are integers (number of consumables from the group)

        When groups is a string or a tuple of strings, 1 consumable will be retrieved per corresponding group(s).
        When groups is a dictionary, each key is a destination group. For each corresponding value:
            - If the value is N < 0, all available consumables are retrieved from the group.
            - If the value is N > 0, at most N available consumables are retrieved from the group.

        In any case, the group strings must be a subset of the Endpoint's groups.

        :param groups: object: destination groups of the consumables.
        """
        if isinstance(groups, str):
            groups = {groups: 1}
        elif isinstance(groups, tuple) or isinstance(groups, list):
            groups = {dest: 1 for dest in groups}
        else:
            assert isinstance(groups, dict), f"groups must be either of: str, (str), dict."
            for k, v in groups.items():
                assert isinstance(k, str), f"groups keys must be strings."
                assert isinstance(v, int), f"groups values must be integers."
        assert len(groups.keys()) > 0, f"Please specify at least one group to be notified"
        self._send_local(cmd='NTF', dest=groups, obj=None)

    def stop(self):
        if not self._stopped:
            self._stopped = True
            # send STOP to the local server
            self._send_local(cmd='STOP', dest=None, obj=None)

            # Join the message reading thread
            with self.__socket_closed_lock:
                self.__socket_closed_flag = True
            self._t_manage_received_objects.join()

            # join Twisted process and stop local server
            self._p.join()

            self._local_com_conn.close()
            self._local_com_srv.close()
            self._local_com_addr = None

    def receive_all(self, blocking=False):
        """
        Returns all received objects in a list, from oldest to newest.

        :param blocking: bool: If True, the call blocks until objects are available. Otherwise, the list may be empty.
        :return: list: received objects
        """
        cpy = []
        elem = get_from_queue(self.__obj_buffer, blocking)
        while len(elem) > 0:
            cpy += elem
            elem = get_from_queue(self.__obj_buffer, blocking=False)
        return cpy

    def pop(self, max_items=1, blocking=False):
        """
        Returns at most max_items oldest received objects (FIFO).

        Items are returned from older to more recent.

        :param max_items: int: max number of retrieved items.
        :param blocking: bool: If True, the call blocks until at least 1 item is retrieved.
            Otherwise, the returned list may be empty.
        :return: list: returned items.
        """
        assert max_items > 0, "Value of max_items must be > 0"

        cpy = []
        elem = get_from_queue(self.__obj_buffer, blocking)
        assert len(elem) == 0 or blocking, 'Issue in pop'
        while len(elem) > 0:
            cpy += elem
            if len(cpy) >= max_items:
                break
            elem = get_from_queue(self.__obj_buffer, blocking=False)
        return cpy

    def get_last(self, max_items=1, blocking=False):
        """
        Returns at most the max_items most recently received objects, and clears receiving buffer.
       
        Items are returned from older to more recent.
        Calling this method clears the receiving buffer.
        In other words, only the most recent objects are retrieved, older objects in the buffer are deleted.
        In case this behavior is not desirable in your application, use `receive_all` or `pop` instead.
        
        :param max_items: int: maximum number of items to return
        :param blocking: bool: If True, the call blocks until at least one item is retrieved.
            Otherwise, the returned list may be empty.
        :return: list: The returned items.
        """
        cpy = []
        elem = get_from_queue(self.__obj_buffer, blocking)
        assert len(elem) == 0 or blocking, 'Issue in get_last'
        while len(elem) > 0:
            cpy += elem
            elem = get_from_queue(self.__obj_buffer, blocking=False)
        return cpy[-max_items:]
