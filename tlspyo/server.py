import logging
logging.basicConfig(level=logging.INFO)

import math
import pickle as pkl
from multiprocessing import Process
from socket import socket, AF_INET, SOCK_STREAM

from twisted.internet.protocol import Protocol, Factory
from twisted.internet.endpoints import TCP4ServerEndpoint

from local_protocol_for_server import LocalProtocolForServerFactory


class ServerProtocol(Protocol):

    def __init__(self, server):
        self._server = server
        self._identifier = None
        self._state = "HANDSHAKE"
        self._buffer = b""
        self._password = self._server.password
        self._len_password = len(bytes(self._password, encoding='utf8'))
        self._header_size = self._server.header_size

    def connectionMade(self):
        assert self._state == "HANDSHAKE", f"Bad state: {self._state}"
        self.send_obj(cmd="HELLO")

    def connectionLost(self, reason):
        logging.info(f"Connection lost: {reason}")
        if self._server.has_client(self._identifier):
            self._server.delete_client(self._identifier)
        assert not self._server.has_client(self._identifier)
        self._identifier = None
        self._state = "DEAD"

    def process_header(self):
        i = self._header_size + self._len_password
        if len(self._buffer) < i:
            return 0, len(self._buffer) + 1, None
        data_len = int(self._buffer[:self._header_size])
        j = i + data_len
        psw = self._buffer[self._header_size:i]
        psw = psw.decode('utf8')
        if psw != self._password:
            logging.info(f"Invalid password: {psw}")
            self._state = "KILLED"
            self.transport.abortConnection()
        return i, j, psw

    def dataReceived(self, data):
        try:
            self._buffer += data
            i = self._header_size + self._len_password
            if len(self._buffer) >= i:
                i, j, psw = self.process_header()
                if self._state == "KILLED":
                    return
                while len(self._buffer) >= j:
                    cmd, dest, obj = pkl.loads(self._buffer[i:j])
                    if cmd == "OBJ":
                        logging.info(f"Received object from client {self._identifier} for groups {dest}.")
                        self.forward_obj_to_groups(obj=obj, groups=dest)
                    elif cmd == "HELLO":
                        groups = obj
                        if isinstance(groups, str):
                            groups = (groups, )
                        elif groups is None:
                            groups = ('__default', )
                        if self._server.check_new_client(groups=groups):
                            logging.info(f"New client with groups {groups}.")
                            self._identifier = self._server.add_client(groups=groups, client=self)
                            self._state = "ALIVE"
                        else:
                            self._state = "CLOSED"
                            self.transport.loseConnection()
                    else:
                        logging.info(f"Invalid command: {cmd}")
                        self._state = "CLOSED"
                        self.transport.loseConnection()
                    # truncate the processed part of the buffer:
                    self._buffer = self._buffer[j:]
                    i, j, psw = self.process_header()
                    if self._state == "KILLED":
                        return
        except Exception as e:
            logging.info(f"Unhandled exception: {e}")
            self._state = "KILLED"
            self.transport.abortConnection()
            raise e

    def send_obj(self, cmd='OBJ', obj=None):
        msg = pkl.dumps((cmd, obj))
        msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
        self.transport.write(data=msg)

    def forward_obj_to_groups(self, obj, groups):
        if groups is not None:
            for group in groups:
                for g, ids in self._server.groups.items():
                    if g == group:
                        for id_cli in ids:
                            self._server.clients[id_cli].send_obj(cmd='OBJ', obj=obj)


class ServerProtocolFactory(Factory):

    protocol = ServerProtocol

    def __init__(self, server):
        self.server = server

    def buildProtocol(self, addr):
        logging.info('Connected.')
        return ServerProtocol(self.server)


class Server:
    def __init__(self, port, password, accepted_groups=None, header_size=10, local_com_port=2097):
        self._port = port
        self._local_com_port = local_com_port
        assert self._local_com_port != self._port, f"Internet and local ports are the same ({self._port})."
        self.password = password
        self.header_size = header_size
        self._accepted_groups = accepted_groups
        self.clients = {}  # dict of identifiers to clients
        self.groups = {}  # dictionary of groups to lists of clients idxs within each group
        self._id_cpt = 0
        self._reactor = None

    def run(self):
        """
        Main loop containing the reactor loop.

        This is run in its own process.
        """
        from twisted.internet.interfaces import IReadDescriptor
        from twisted.internet import reactor

        endpoint = TCP4ServerEndpoint(reactor, self._port)
        endpoint.listen(ServerProtocolFactory(self))  # we pass the instance of Server to the Factory
        reactor.connectTCP(host='127.0.0.1', port=self._local_com_port, factory=LocalProtocolForServerFactory(self))
        self._reactor = reactor
        self._reactor.run()  # main Twisted reactor loop

    def add_accepted_group(self, group, max_count=math.inf):
        """
        Adds a new group name to accepted group names

        :param group: str: name of the new group
        :param max_count: maximum number of simultaneous clients in this group
        """
        if self._accepted_groups is None:
            self._accepted_groups = {}
        self._accepted_groups[group] = {'max_count': max_count}
        self._accepted_groups['__server'] = {'max_count': 1}

    def check_new_client(self, groups):
        """
        Checks whether a client can be added to requested groups.

        :param groups: list of strings: requested groups for this client
        :return authorization: bool: whether the client can be added
        """
        if self._accepted_groups is not None:
            for group in groups:
                if group not in self._accepted_groups.keys():
                    logging.info(f"Invalid group {group}.")
                    return False
                if group in self.groups.keys():
                    max_count = self._accepted_groups[group]['max_count']
                    if len(self.groups[group]) >= max_count:
                        logging.info(f"Cannot add more clients to group {group}.")
                        return False
        return True

    def add_client(self, groups, client):
        identifier = self._id_cpt
        self._id_cpt += 1
        logging.info(f"Adding client {identifier} to list of clients.")
        self.clients[identifier] = client
        for group in groups:
            if group not in self.groups.keys():
                self.groups[group] = []
            logging.info(f"Adding client {identifier} to group {group}.")
            self.groups[group].append(identifier)
        return identifier

    def delete_client(self, identifier):
        for group, idents in self.groups.items():
            if identifier in idents:
                logging.info(f"Removing client {identifier} from group {group}.")
                idents.remove(identifier)
        logging.info(f"Removing client {identifier} from list of clients.")
        del self.clients[identifier]

    def has_client(self, identifier):
        return identifier in self.clients

    def close(self):
        if self._reactor is not None:
            identifiers = list(self.clients.keys())
            for identifier in identifiers:
                self.clients[identifier].transport.loseConnection()
                self.delete_client(identifier)
            self._reactor.stop()
            self._reactor = None


class CentralRelay:
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


if __name__ == "__main__":
    import time
    relay = CentralRelay(port=8123, password="pswd", accepted_groups=None)
    time.sleep(5)
    # relay.stop()
    # time.sleep(1)
