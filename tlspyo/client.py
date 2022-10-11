import logging
logging.basicConfig(level=logging.INFO)

import pickle as pkl
from twisted.internet.protocol import Protocol, ReconnectingClientFactory


class ClientProtocol(Protocol):
    def __init__(self, password, header_size=10, groups=("default", )):
        self._password = password
        self._header_size = header_size
        self._buffer = b""
        self._groups = groups

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
                    self.send_obj(cmd='OBJ', dest=('default', 'bla'), obj="Test :D")
                elif cmd == "OBJ":
                    logging.info(f"Received object.")
                # truncate the processed part of the buffer:
                self._buffer = self._buffer[j:]
                i, j = self.process_header()

    def send_obj(self, cmd='OBJ', dest=None, obj=None):
        msg = pkl.dumps((cmd, dest, obj))
        msg = bytes(f"{len(msg):<{self._header_size}}{self._password}", 'utf-8') + msg
        self.transport.write(data=msg)


class TLSClientFactory(ReconnectingClientFactory):
    protocol = ClientProtocol

    def __init__(self, password):
        self.password = password

    def startedConnecting(self, connector):
        logging.info('Started to connect.')

    def buildProtocol(self, addr):
        logging.info('Connected.')
        self.resetDelay()
        return ClientProtocol(self.password)

    def clientConnectionLost(self, connector, reason):
        logging.info(f'Lost connection.  Reason: {reason}')
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.info(f'Connection failed. Reason: {reason}')
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


class Client:
    def __init__(self, ip_server, port_server, password, header_size=10):
        self._ip_server = ip_server
        self._port_server = port_server
        self.password = password
        self.header_size = header_size

    def run(self):
        # TODO: isolate this in a process
        from twisted.internet import reactor

        reactor.connectTCP(host=self._ip_server, port=self._port_server, factory=TLSClientFactory(self.password))
        reactor.run()


if __name__ == "__main__":
    cli = Client(ip_server="127.0.0.1", port_server=8123, password="pswd")
    cli.run()
