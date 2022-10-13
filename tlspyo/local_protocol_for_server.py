import logging
import pickle as pkl

from twisted.internet.protocol import Protocol, ClientFactory


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
            logging.info(f"Local: New client with groups {groups}.")
            self._identifier = self._server.add_client(groups=groups, client=self)
            self._state = "ALIVE"
        else:
            logging.info(f"Local: Connection could not be validated.")
            self._state = "CLOSED"
            self.transport.abortConnection()

    def connectionLost(self, reason):
        logging.info(f"Local: Connection lost: {reason}")
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
                        logging.info(f"Local: Stopping reactor.")
                        self._server.close()
                        logging.info(f"Local: Reactor stopped.")
                    else:
                        logging.info(f"Local: Invalid command: {cmd}")
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

    def process_header(self):
        i = self._header_size
        if len(self._buffer) < i:
            return 0, len(self._buffer) + 1
        data_len = int(self._buffer[:self._header_size])
        j = i + data_len
        return i, j


class LocalProtocolForServerFactory(ClientFactory):
    protocol = LocalProtocolForServer

    def __init__(self, server):
        self.server = server

    def startedConnecting(self, connector):
        logging.info('Local: Started to connect.')

    def buildProtocol(self, addr):
        logging.info('Local: Connected.')
        return LocalProtocolForServer(self.server)

    def clientConnectionLost(self, connector, reason):
        logging.info(f'Local: Client lost connection.  Reason: {reason}')

    def clientConnectionFailed(self, connector, reason):
        logging.info(f'Local: Client connection failed. Reason: {reason}')
