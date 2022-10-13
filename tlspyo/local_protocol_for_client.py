import logging
import pickle as pkl

from twisted.internet.protocol import Protocol, ClientFactory


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
        logging.info(f"Local: Connection lost: {reason}")
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
                        logging.info(f"Local: Stopping reactor.")
                        self._client.close()
                        logging.info(f"Local: Reactor stopped.")
                    elif cmd == "OBJ":
                        # send the object to the central relay
                        if self._client.server is not None:
                            self._client.server.send_obj(cmd='OBJ', dest=dest, obj=obj_bytes)
                        else:
                            logging.warning('The client is not connected to the internet server, discarding object.')
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


class LocalProtocolForClientFactory(ClientFactory):
    protocol = LocalProtocolForClient

    def __init__(self, client):
        self.client = client

    def startedConnecting(self, connector):
        logging.info('Local: Started to connect.')

    def buildProtocol(self, addr):
        logging.info('Local: Connected.')
        return LocalProtocolForClient(self.client)

    def clientConnectionLost(self, connector, reason):
        logging.info(f'Local: Client lost connection.  Reason: {reason}')

    def clientConnectionFailed(self, connector, reason):
        logging.info(f'Local: Client connection failed. Reason: {reason}')
