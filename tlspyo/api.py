import queue
from socket import AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, socket
import pickle as pkl
from threading import Thread, Lock
from multiprocessing import Process
import os

from tlspyo.server import Server
from tlspyo.client import Client

from tlspyo.utils import get_from_queue


__docformat__ = "google"


DEFAULT_SECURITY = "TLS"
DEFAULT_SERIALIZER = pkl.dumps
DEFAULT_DESERIALIZER = pkl.loads


class Relay:
    def __init__(self,
                 port: int,
                 password: str,
                 accepted_groups=None,
                 local_com_port: int = 2096,
                 header_size: int = 10,
                 security: str = DEFAULT_SECURITY,
                 keys_dir: str = None,
                 serializer=None,
                 deserializer=None):
        """
        ``tlspyo`` Relay.

        Endpoints connect to a central Relay, which allows them to communicate in `tlspyo`.
        When used on the Internet, the machine running the Relay must be directly visible from the Internet.
        (Usually, if the machine is behind an Internet box/router, this involves port forwarding.)
        WHEN USING `tlspyo` ON THE INTERNET, IT IS IMPORTANT TO USE TLS SECURITY (default).
        In particular, you will want to choose a strong password, and use your own TLS credentials.
        See the Command Line Interface section of the documentation to generate your TLS credentials.

        Args:
            port (int): port of the Relay
            password (str): password of the Relay
            accepted_groups (object): groups accepted by the Relay.
                If None, the Relay accepts any group;
                Else, must be a dictionary where keys are groups and values are dictionaries with the following entries:

                    - 'max_count': max number of connected clients in the group (None for unlimited)
                    - 'max_consumables': max number of pending consumables in the group (None for unlimited)

            local_com_port (int): local port used for internal communication with Twisted.
            header_size (int): bytes to read at once from socket buffers (the default should work for most cases)
            security (str): one of (None, "TLS");
                None disables TLS, do not use None on a public network unless you know what you are doing!
            serializer (callable): custom serializer that outputs a bytestring from a python object
            deserializer (callable): custom deserializer that outputs a python object from a bytestring
        """

        assert security in (None, "TLS"), f"Unsupported security: {security}"

        if security is None:
            security = "TCP"
        elif security == "SSL":
            security = "TLS"

        assert accepted_groups is None or isinstance(accepted_groups, dict), "Invalid format for accepted_groups."

        self._header_size = header_size
        self._local_com_port = local_com_port
        self._local_com_srv = socket(AF_INET, SOCK_STREAM)
        self._local_com_srv.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self._local_com_srv.bind(('127.0.0.1', self._local_com_port))
        self._local_com_srv.listen()

        keys_dir = os.path.abspath(keys_dir) if keys_dir is not None else keys_dir
        serializer = serializer if serializer is not None else DEFAULT_SERIALIZER
        deserializer = deserializer if deserializer is not None else DEFAULT_DESERIALIZER

        self._server = Server(port=port,
                              password=password,
                              serializer=serializer,
                              deserializer=deserializer,
                              accepted_groups=accepted_groups,
                              local_com_port=local_com_port,
                              header_size=header_size,
                              security=security,
                              keys_dir=keys_dir)
        self._p = Process(target=self._server.run, args=())
        self._p.start()
        self._local_com_conn, self._local_com_addr = self._local_com_srv.accept()
        self._send_local('TEST')

        self._stop_lock = Lock()
        self._stopped = False

    def __del__(self):
        self.stop()

    def _send_local(self, cmd):
        msg = self._server.serializer((cmd, None))
        msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
        self._local_com_conn.sendall(msg)

    def stop(self):
        """
        Stop the Relay.
        """
        try:
            with self._stop_lock:
                if not self._stopped:
                    self._send_local('STOP')

                    self._p.join()
                    self._local_com_conn.close()
                    self._local_com_srv.close()
                    self._local_com_addr = None
                    self._stopped = True
        except KeyboardInterrupt as e:
            self.stop()
            raise e


class Endpoint:
    def __init__(self,
                 ip_server: str,
                 port: int,
                 password: str,
                 groups=None,
                 local_com_port: int = 2097,
                 header_size: int = 10,
                 max_buf_len: int = 4096,
                 security: str = DEFAULT_SECURITY,
                 keys_dir: str = None,
                 hostname: str = "default",
                 serializer=None,
                 deserializer=None,
                 recon_max_delay=60.0,
                 recon_initial_delay=10.0,
                 recon_factor=1.5,
                 recon_jitter=0.1,
                 deserializer_mode="asynchronous"):
        """
        ``tlspyo`` Endpoint.

        Endpoints in tlspyo are python objects that can securely send and receive Python object over the network.
        They communicate via the Relay, and should use TLS security (default) on public networks.
        See the Command Line Interface section of the documentation to generate your TLS credentials.

        Args:
            ip_server (str): the IP address of the Relay (set to '127.0.0.1' for local testing)
            port (int): the port of the Relay (use the same number for the Relay, it must be > 1024)
            password (str): password of the Relay (use the same for the Relay, the stronger, the better)
            groups (tuple of str, or str): groups in which this Endpoint is
            local_com_port (int): local port used for internal communication with Twisted
            header_size (int): number of bytes used for the header (the default should be OK for most cases)
            max_buf_len (int): max bytes to read at once from socket buffers (the default should be OK for most cases)
            security (str): one of (None, "TLS");
                None disables TLS, do not use None on a public network unless you know what you are doing!
            serializer (callable): custom serializer that outputs a bytestring from a python object
            deserializer (callable): custom deserializer that outputs a python object from a bytestring
            recon_max_delay (float): in case of network failure, maximum delay between reconnection attempts
            recon_initial_delay (float): in case of network failure, initial delay between reconnection attempts
            recon_factor (float): in case of network failure, delay will increase by this factor between attempts
            recon_jitter (float): in case of network failure, jitter factor of the delay between attempts
            deserializer_mode (str): one of ("synchronous", "asynchronous"); ("sync", "async") are also accepted;
                in asynchronous mode, objects are deserialized by the receiver thread as soon as they arrive, such that
                they become available to the calling thread as soon as it needs to retrieve them;
                in synchronous mode, objects are deserialized by the calling thread upon object retrieval;
                synchronous mode removes the need for potentially useless, randomly timed deserialization in the
                background, at the cost of performing deserialization upon object retrieval instead
        """

        assert security in (None, "TLS"), f"Unsupported security: {security}"

        if security is None:
            security = "TCP"
        elif security == "SSL":
            security = "TLS"

        # threading for local object receiving
        self.__obj_buffer = queue.Queue()
        self.__socket_closed_lock = Lock() 
        self.__socket_closed_flag = False
    
        # networking (local and internet)
        if isinstance(groups, str):
            groups = (groups, )
        self._header_size = header_size
        self._max_buf_len = max_buf_len
        self._local_com_port = local_com_port
        self._local_com_srv = socket(AF_INET, SOCK_STREAM)
        self._local_com_srv.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

        self._deserialize_locally = deserializer_mode in ("synchronous", "sync")

        keys_dir = os.path.abspath(keys_dir) if keys_dir is not None else keys_dir
        serializer = serializer if serializer is not None else DEFAULT_SERIALIZER
        deserializer = deserializer if deserializer is not None else DEFAULT_DESERIALIZER

        self._client = Client(ip_server=ip_server,
                              port_server=port,
                              password=password,
                              serializer=serializer,
                              deserializer=deserializer,
                              groups=groups,
                              local_com_port=local_com_port,
                              header_size=header_size,
                              security=security,
                              keys_dir=keys_dir,
                              hostname=hostname,
                              recon_max_delay=recon_max_delay,
                              recon_initial_delay=recon_initial_delay,
                              recon_factor=recon_factor,
                              recon_jitter=recon_jitter)

        # start local server and Twisted process
        self._local_com_srv.bind(('127.0.0.1', self._local_com_port))
        self._local_com_srv.listen()
        self._p = Process(target=self._client.run, args=())
        self._p.start()
        self._local_com_conn, self._local_com_addr = self._local_com_srv.accept()
        self._send_local(cmd='TEST')

        self._t_manage_received_objects = Thread(target=self._manage_received_objects, daemon=True)
        self._t_manage_received_objects.start()

        self._stop_lock = Lock()
        self._stopped = False

    def __del__(self):
        self.stop()

    def _deserialize(self, obj):
        return self._client.deserializer(obj)

    def _manage_received_objects(self):
        """
        Called in its own thread.
        """
        buf = b""
        while True:
            # Check if socket is still open
            with self.__socket_closed_lock:
                if self.__socket_closed_flag:
                    return

            buf += self._local_com_conn.recv(self._max_buf_len)
            i, j = self._process_header(buf)
            while j <= len(buf):
                stamp, cmd, obj = self._deserialize(buf[i:j])
                if cmd == "OBJ":
                    to_put = obj if self._deserialize_locally else self._deserialize(obj)
                    self.__obj_buffer.put(to_put)  # TODO: maxlen
                buf = buf[j:]
                i, j = self._process_header(buf)

    def _process_header(self, buf):
        i = self._header_size
        if len(buf) < i:
            return 0, len(buf) + 1
        data_len = int(buf[:self._header_size])
        j = i + data_len
        return i, j

    def _send_local(self, cmd, dest=None, obj=None):
        msg = self._client.serializer((cmd, dest, self._client.serializer(obj)))
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

        When destination is a dictionary, each key is a destination group.

        For each corresponding value:
            - if the value is N < 0, the object is broadcast to the group
            - if the value is N > 0, N objects are sent to the group to be consumed. To consume an object, the Endpoint first needs to signal itself as idle for the corresponding group with Endpoint.notify().

        Args:
            obj (object): object to broadcast to destination
            destination (object): destination group(s)
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

        Args:
            obj (object): object to send as consumable
            group (str): target group
        """
        assert isinstance(group, str), f"group must be a string, not {type(group)}"
        self.send_object(obj=obj, destination={group: 1})

    def broadcast(self, obj, group):
        """Alias for send_object(obj=obj, destination={group: -1})

        Note that broadcasting an object overrides the previous brodcast object

        Args:
            obj (object): object to send to be broadcast to entire group
            group (str): destination group to which the object should be broadcast.
        """
        assert isinstance(group, str), f"group must be a string, not {type(group)}"
        self.send_object(obj=obj, destination={group: -1})

    def notify(self, groups):
        """
        Notifies the Relay that the Endpoint is ready to retrieve consumables from destination groups.

        groups can either be:
            - a string (single group)
            - a tuple of strings (set of groups)
            - a dictionary where keys are strings (group) and values are integers (number of consumables from the group)

        When groups is a string or a tuple of strings, 1 consumable will be retrieved per corresponding group(s).
        When groups is a dictionary, each key is a destination group.

        For each corresponding value:
            - if the value is N < 0, all available consumables are retrieved from the group
            - if the value is N > 0, at most N available consumables are retrieved from the group

        In any case, the group strings must be a subset of the Endpoint's groups.

        Args:
            groups (object): destination groups of the consumables.
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
        """
        Stop the Endpoint.
        """
        try:
            with self._stop_lock:
                if not self._stopped:
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
                    self._stopped = True
        except KeyboardInterrupt as e:
            self.stop()
            raise e

    def _process_received_list(self, received_list):
        if self._deserialize_locally:
            for i, obj in enumerate(received_list):
                received_list[i] = self._deserialize(obj)
        return received_list

    def receive_all(self, blocking=False):
        """
        Returns all received objects in a list, from oldest to newest.

        Args:
            blocking (bool): If True, the call blocks until objects are available. Otherwise, the list may be empty.

        Returns:
            list: received objects
        """
        cpy = []
        elem = get_from_queue(self.__obj_buffer, blocking)
        while len(elem) > 0:
            cpy += elem
            elem = get_from_queue(self.__obj_buffer, blocking=False)
        cpy = self._process_received_list(cpy)
        return cpy

    def pop(self, max_items=1, blocking=False):
        """
        Returns at most max_items oldest received objects (FIFO).

        Items are returned from older to more recent.

        Args:
            max_items (int): max number of retrieved items.
            blocking (bool): If True, the call blocks until at least 1 item is retrieved.
                Otherwise, the returned list may be empty.

        Returns:
            list: returned items.
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
        cpy = self._process_received_list(cpy)
        return cpy

    def get_last(self, max_items=1, blocking=False):
        """
        Returns at most the max_items most recently received objects, and clears receiving buffer.
       
        Items are returned from older to more recent.
        Calling this method clears the receiving buffer.
        In other words, only the most recent objects are retrieved, older objects in the buffer are deleted.
        In case this behavior is not desirable in your application, use `receive_all` or `pop` instead.

        Args:
            max_items (int): maximum number of items to return
            blocking (bool): If True, the call blocks until at least one item is retrieved.
                Otherwise, the returned list may be empty.

        Returns:
            list: The returned items.
        """
        cpy = []
        elem = get_from_queue(self.__obj_buffer, blocking)
        assert len(elem) != 0 or not blocking, 'Issue in get_last'
        while len(elem) > 0:
            cpy += elem
            elem = get_from_queue(self.__obj_buffer, blocking=False)
        cpy = self._process_received_list(cpy[-max_items:])
        return cpy
