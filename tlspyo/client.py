import logging
import pickle as pkl
import time

from twisted.internet.protocol import Protocol, ReconnectingClientFactory
from tlspyo.local_protocol_for_client import LocalProtocolForClientFactory


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
                stamp, cmd, obj = pkl.loads(self._buffer[i:j])
                if cmd == 'ACK':
                    try:
                        logging.info(f"ACK received after {time.monotonic() - self._client.pending_acks[stamp][0]}s.")
                        del self._client.pending_acks[stamp]  # delete pending ACK
                    except KeyError:
                        logging.warning(f"Received ACK for stamp {stamp} not present in pending ACKs.")
                else:
                    self.send_ack(stamp)  # send ACK
                    if cmd == "HELLO":
                        self.send_obj(cmd='HELLO', obj=self._groups)
                        self._state = "ALIVE"
                        while len(self._client.store) > 0:
                            # send buffered commands to the server
                            cmd, dest, obj = self._client.store[0]
                            self.send_obj(cmd=cmd, dest=dest, obj=obj)  # send buffered command
                            self._client.store = self._client.store[1:]  # remove buffered command from store
                    else:
                        if self._state != "ALIVE":
                            logging.warning(f"Received a command in a bad state: {self._state}.")
                        if cmd == "OBJ":
                            logging.debug(f"Received object, transferring to local EndPoint.")
                            # transfer the object to the EndPoint server
                            if self._client.endpoint is not None:
                                self._client.endpoint.transport.write(data=self._buffer[:j])
                            else:
                                logging.warning(f"Local EndPoint is not connected, discarding object.")
                # truncate the processed part of the buffer:
                self._buffer = self._buffer[j:]
                i, j = self.process_header()

    def send_obj(self, cmd='OBJ', dest=None, obj=None):
        self._client.ack_stamp += 1
        msg = pkl.dumps((self._client.ack_stamp, cmd, dest, obj))
        msg = bytes(f"{len(msg):<{self._header_size}}{self._password}", 'utf-8') + msg
        self._client.pending_acks[self._client.ack_stamp] = (time.monotonic(), msg)
        self.transport.write(data=msg)
        print(f"|||||||||||||||| Sending object {pkl.loads(obj) if isinstance(obj, bytes) else obj}")


    def send_ack(self, stamp):
        msg = pkl.dumps((stamp, 'ACK', None, None))
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
        self.store = []
        self.ack_stamp = 0
        self.pending_acks = {}  # this contains copies of sent commands until corresponding ACKs are received

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
        if self.server is not None:
            self.server.transport.loseConnection()
            
        if self._reactor is not None:
            self._reactor.stop()


if __name__ == "__main__":
    cli = Client(ip_server="127.0.0.1", port_server=8123, password="pswd")
    cli.run()
