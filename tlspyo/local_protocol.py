import socket
import errno
import logging
import pickle as pkl

from twisted.python.failure import Failure
from twisted.internet.protocol import Protocol, ReconnectingClientFactory


class SocketDescriptor(object):

    poem = ''

    def __init__(self, connected_socket):
        self.sock = connected_socket

    def fileno(self):
        try:
            return self.sock.fileno()
        except socket.error:
            return -1

    def connectionLost(self, reason):
        pass

    def doRead(self):
        chunks = b''

        while True:
            try:
                bytesread = self.sock.recv(1024)
                if not bytesread:
                    break
                else:
                    chunks += bytesread
            except socket.error as e:
                if e.args[0] == errno.EWOULDBLOCK:
                    break
                return Failure(e)

        if not chunks:
            print('DEBUG Task finished')
            return
        else:
            print(f'DEBUG: received {len(chunks)} bytes')

        self.poem += chunks.decode('utf8')

    def logPrefix(self):
        return 'local'

    # def format_addr(self):
    #     host, port = self.address
    #     return '%s:%s' % (host or '127.0.0.1', port)


class LocalProtocolForServer(Protocol):

    def __init__(self, server):
        self._server = server
        self._state = "INIT"
        self._buffer = b""
        self._password = self._server.password
        self._len_password = len(bytes(self._password, encoding='utf8'))
        self._header_size = self._server.header_size
        self._identifier = None

    def connectionMade(self):
        assert self._state == "INIT", f"Bad state: {self._state}"
        groups = ('__server',)
        if self._server.check_new_client(groups=groups):
            logging.info(f"New client with groups {groups}.")
            self._identifier = self._server.add_client(groups=groups, client=self)
            self._state = "ALIVE"
        else:
            logging.info(f"Local connection could not be validated.")
            self._state = "CLOSED"
            self.transport.abortConnection()

    def connectionLost(self, reason):
        logging.info(f"Connection lost: {reason}")
        if self._server.has_client(self._identifier):
            self._server.delete_client(self._identifier)
        assert not self._server.has_client(self._identifier)
        self._identifier = None
        self._state = "DEAD"

    def dataReceived(self, data):
        try:
            self._buffer += data
            i = self._header_size
            if len(self._buffer) >= i:
                i, j = self.process_header()
                while len(self._buffer) >= j:
                    cmd, _ = pkl.loads(self._buffer[i:j])
                    if cmd == "STOP":
                        self._server.reactor.stop()  # stop the defined reactor
                    else:
                        logging.info(f"Invalid command: {cmd}")
                        self._state = "CLOSED"
                        self.transport.abortConnection()
                    # truncate the processed part of the buffer:
                    self._buffer = self._buffer[j:]
                    i, j = self.process_header()
        except Exception as e:
            logging.info(f"Local: Unhandled exception: {e}")
            self._state = "KILLED"
            self.transport.abortConnection()
            raise e

    # def send_obj(self, cmd='OBJ', obj=None):
    #     msg = pkl.dumps((cmd, obj))
    #     msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
    #     self.transport.write(data=msg)

    def process_header(self):
        i = self._header_size
        if len(self._buffer) < i:
            return 0, len(self._buffer) + 1
        data_len = int(self._buffer[:self._header_size])
        j = i + data_len
        return i, j


class LocalProtocolForServerFactory(ReconnectingClientFactory):
    protocol = LocalProtocolForServer

    def __init__(self, server):
        self.server = server

    def startedConnecting(self, connector):
        logging.info('Local: Started to connect.')

    def buildProtocol(self, addr):
        logging.info('Local: Connected.')
        self.resetDelay()
        return LocalProtocolForServer(self.server)

    def clientConnectionLost(self, connector, reason):
        logging.info(f'Lost connection.  Reason: {reason}')
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.info(f'Connection failed. Reason: {reason}')
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)
