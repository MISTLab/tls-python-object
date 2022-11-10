import pickle as pkl

from twisted.internet.protocol import Protocol, ClientFactory

from tlspyo.logs import logger


class LocalProtocolForServer(Protocol):

    def __init__(self, server):
        self._server = server
        self._state = "INIT"
        self._buffer = b""
        self._header_size = self._server.header_size
        self._identifier = None

    def connectionMade(self):
        assert self._state == "INIT", f"Bad state: {self._state}"
        self._state = "ALIVE"

    def connectionLost(self, reason):
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
                        self.transport.loseConnection()
                        self._server.close(1)
                    elif cmd == 'TEST':
                        pass
                    else:
                        logger.warning(f"Local: Invalid command: {cmd}")
                        self._state = "CLOSED"
                        self.transport.abortConnection()
                    # truncate the processed part of the buffer:
                    self._buffer = self._buffer[j:]
                    i, j = self.process_header()
        except Exception as e:
            logger.warning(f"Local: Unhandled exception: {e}")
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
        logger.info('Local for server: Started to connect.')

    def buildProtocol(self, addr):
        logger.info('Local for server: Connected.')
        return LocalProtocolForServer(self.server)

    def clientConnectionLost(self, connector, reason):
        logger.info(f'Local for server: lost connection.  Reason: {reason.getErrorMessage()}')

    def clientConnectionFailed(self, connector, reason):
        logger.info(f'Local for server: Client connection failed. Reason: {reason.getErrorMessage()}')
