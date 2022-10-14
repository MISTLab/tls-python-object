from socket import AF_INET, SOCK_STREAM, socket
import pickle as pkl
from threading import Thread, Lock
from multiprocessing import Process
from copy import deepcopy

from server import Server
from client import Client


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
    def __init__(self, ip_server, port_server, password, groups=None, local_com_port=2097, header_size=10):

        # threading for local object receiving
        self.__obj_buffer = []
        self.__obj_buffer_lock = Lock()

        # networking (local and internet)
        if isinstance(groups, str):
            groups = (groups, )
        self._header_size = header_size
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

    def _manage_received_objects(self):
        """
        Called in its own thread.
        """
        buf = b""
        while True:
            buf += self._local_com_conn.recv(4096)
            i, j = self._process_header(buf)
            if j <= len(buf):
                stamp, cmd, obj = pkl.loads(buf[i:j])
                if cmd == "OBJ":
                    with self.__obj_buffer_lock:
                        self.__obj_buffer.append(pkl.loads(obj))
                buf = buf[j:]

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

    def receive_all(self):
        with self.__obj_buffer_lock:
            cpy = deepcopy(self.__obj_buffer)
            self.__obj_buffer = []
        return cpy

    def pop(self, max_items=1):
        """
        Returns at most max_items oldest received objects.

        :param max_items:int: desired max number of items.
        :return: list: mThe returned items
        """
        with self.__obj_buffer_lock:
            if len(self.__obj_buffer) >= max_items:
                cpy = deepcopy(self.__obj_buffer[:max_items])
                self.__obj_buffer = self.__obj_buffer[max_items:]
            else:
                cpy = deepcopy(self.__obj_buffer)
                self.__obj_buffer = []
        return cpy

    def pop_lifo(self, max_items=1, clear=False):
        """
        Returns at most max_items from the object buffer using a LIFO stack implementation.
        :param max_items:int: maximum number of items to return
        :param clear:bool: Indicates whether the buffer should be cleared when called.
        :return: list: The returned items
        """
        with self.__obj_buffer_lock:
            if len(self.__obj_buffer) >= max_items:
                cpy = deepcopy(self.__obj_buffer[-max_items:])
                if clear:
                    self.__obj_buffer = []
                else:
                    self.__obj_buffer = self.__obj_buffer[:-max_items]
            else:
                cpy = deepcopy(self.__obj_buffer)
                self.__obj_buffer = []
        return cpy


if __name__ == '__main__':
    from argparse import ArgumentParser
    import time

    parser = ArgumentParser()
    parser.add_argument('--endpoint', dest='endpoint', action='store_true', default=False, help='Start as endpoint.')
    parser.add_argument('--relay', dest='relay', action='store_true', default=True, help='Start as relay.')
    parser.add_argument('--password', dest='password', type=str, default="pswd", help='Server password.')
    parser.add_argument('--port', dest='port', type=int, default=2098, help='Server port.')
    parser.add_argument('--ip', dest='ip', default="127.0.0.1", type=str, help='Server IP.')
    parser.add_argument('--local_port', dest='local_port', type=int, default=3000, help='Local port.')

    args = parser.parse_args()

    if args.endpoint:
        group = str(args.local_port)
        ep = Endpoint(ip_server=args.ip,
                      port_server=args.port,
                      password=args.password,
                      groups=group,
                      local_com_port=args.local_port)
        cpt = 1
        time.sleep(2)
        while True:
            obj_s = 'salut' + str(cpt) + 'from' + group
            cpt += 1
            dest_s = "3001" if args.local_port == 3000 else "3000"
            # ep.send_object(obj_s, destination=dest_s)
            ep.produce(obj=obj_s, group=dest_s)
            ep.notify(origins={group: -1})

            time.sleep(2)
            print(f"{group} received: {ep.receive_all()}")
            # time.sleep(2)

    else:
        re = Relay(port=args.port,
                   password=args.password,
                   accepted_groups=None)
        while True:
            time.sleep(1)
