import pickle as pkl

from twisted.internet.protocol import Protocol, ClientFactory

from tlspyo.logs import logger


class LocalProtocolForClient(Protocol):

    def __init__(self, client):
        self._client = client
        self._state = "INIT"
        self._buffer = b""
        self._header_size = self._client.header_size
        self._identifier = None

    def connectionMade(self):
        self._client.endpoint = self
        self._state = "ALIVE"

    def connectionLost(self, reason):
        self._client.endpoint = None
        self._state = "DEAD"

    def dataReceived(self, data):
        try:
            self._buffer += data
            i = self._header_size
            if len(self._buffer) >= i:
                i, j = self.process_header()
                while len(self._buffer) >= j:
                    cmd, dest, obj_bytes = pkl.loads(self._buffer[i:j])
                    if cmd == "STOP":
                        self.transport.loseConnection()
                        self._client.close(1)
                    elif cmd in ("OBJ", "NTF"):
                        # send the object to the central relay
                        if self._client.to_server is not None and self._state == "ALIVE" and self._client.to_server.get_state() == "ALIVE":
                            self._client.to_server.send_obj(cmd=cmd, dest=dest, obj=obj_bytes)
                        else:
                            logger.warning('The client is not connected to the Internet server, storing message.')
                            self._client.store.append((cmd, dest, obj_bytes))
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


class LocalProtocolForClientFactory(ClientFactory):
    protocol = LocalProtocolForClient

    def __init__(self, client):
        self.client = client

    def startedConnecting(self, connector):
        logger.info('Local for client: Started to connect.')

    def buildProtocol(self, addr):
        logger.info('Local for client: Connected.')
        return LocalProtocolForClient(self.client)

    def clientConnectionLost(self, connector, reason):
        logger.info(f'Local for client: lost connection.  Reason: {reason.getErrorMessage()}')

    def clientConnectionFailed(self, connector, reason):
        logger.info(f'Local for client: connection failed. Reason: {reason.getErrorMessage()}')
