import logging
logging.basicConfig(level=logging.INFO)

import pickle as pkl
from multiprocessing import Process
from threading import Thread, Lock
from socket import socket, AF_INET, SOCK_STREAM

from twisted.internet.protocol import Protocol, ReconnectingClientFactory

from local_protocol_for_client import LocalProtocolForClientFactory


class ClientProtocol(Protocol):
    def __init__(self, client, password, header_size=10, groups=("default", )):
        self._password = password
        self._header_size = header_size
        self._buffer = b""
        self._groups = groups
        self._client = client
        self._state = "HANDSHAKE"

    def connectionMade(self):
        logging.info(f"Connection made.")
        assert self._state == "HANDSHAKE", f"Bad state: {self._state}"
        self._client.server = self

    def connectionLost(self, reason):
        logging.info(f"Connection lost: {reason}")
        self._state = "DEAD"
        self._client.server = None

    def process_header(self):
        i = self._header_size
        if len(self._buffer) < i:
            return 0, len(self._buffer) + 1
        data_len = int(self._buffer[:self._header_size])
        j = i + data_len
        return i, j

    def dataReceived(self, data):
        self._buffer += data
        if len(self._buffer) >= self._header_size:
            i, j = self.process_header()
            while len(self._buffer) >= j:
                cmd, obj = pkl.loads(self._buffer[i:j])
                if cmd == "HELLO":
                    self.send_obj(cmd='HELLO', obj=self._groups)
                    self._state = "ALIVE"
                elif cmd == "OBJ":
                    logging.info(f"Received object, transferring to local EndPoint.")
                    # transfer the object to the EndPoint server
                    if self._client.endpoint is not None:
                        self._client.endpoint.transport.write(data=self._buffer[:j])
                    else:
                        logging.warning(f"Local EndPoint is not connected, discarding object.")
                # truncate the processed part of the buffer:
                self._buffer = self._buffer[j:]
                i, j = self.process_header()

    def send_obj(self, cmd='OBJ', dest=None, obj=None):
        msg = pkl.dumps((cmd, dest, obj))
        msg = bytes(f"{len(msg):<{self._header_size}}{self._password}", 'utf-8') + msg
        self.transport.write(data=msg)


class TLSClientFactory(ReconnectingClientFactory):
    protocol = ClientProtocol

    def __init__(self, client):
        self.password = client.password
        self._groups = client.groups
        self._header_size = client.header_size
        self._client = client

    def startedConnecting(self, connector):
        logging.info('Started to connect.')

    def buildProtocol(self, addr):
        logging.info('Connected.')
        self.resetDelay()
        return ClientProtocol(client=self._client, password=self.password, groups=self._groups, header_size=self._header_size)

    def clientConnectionLost(self, connector, reason):
        logging.info(f'Lost connection.  Reason: {reason}')
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.info(f'Connection failed. Reason: {reason}')
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


class Client:
    def __init__(self, ip_server, port_server, password, header_size=10, groups=None, local_com_port=2097):
        self.groups = groups
        self._ip_server = ip_server
        self._port_server = port_server
        self._local_com_port = local_com_port
        self.password = password
        self.header_size = header_size
        self._reactor = None
        self.server = None  # to communicate with the central relay
        self.endpoint = None  # to communicate with endpoint

    def run(self):
        """
        Main loop containing the reactor loop.

        This is run in its own process.
        """
        from twisted.internet.interfaces import IReadDescriptor
        from twisted.internet import reactor

        reactor.connectTCP(host='127.0.0.1', port=self._local_com_port, factory=LocalProtocolForClientFactory(self))
        reactor.connectTCP(host=self._ip_server, port=self._port_server, factory=TLSClientFactory(client=self))
        self._reactor = reactor
        self._reactor.run()  # main Twisted reactor loop

    def close(self):
        if self._reactor is not None:
            self._reactor.stop()


class EndPoint:
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

    def _send_local(self, cmd, dest, obj):
        msg = pkl.dumps((cmd, dest, obj))
        msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
        self._local_com_conn.sendall(msg)

    def send_object(self, obj, destination):
        self._send_local(self, cmd='OBJ', dest=destination, obj=obj)

    def stop(self):
        # send STOP to the local server
        self._send_local(self, cmd='STOP', dest=None, obj=None)

        # join Twisted process and stop local server
        self._p.join()
        self._local_com_conn.close()
        self._local_com_addr = None


if __name__ == "__main__":
    cli = Client(ip_server="127.0.0.1", port_server=8123, password="pswd")
    cli.run()
