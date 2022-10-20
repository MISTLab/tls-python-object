import logging
import pickle as pkl
import time

from twisted.internet import task, defer
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
        assert self._state == "HANDSHAKE", f"Bad state: {self._state}"
        self._client.to_server = self

    def connectionLost(self, reason):
        self._state = "DEAD"
        self._client.to_server = None

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

    def send_ack(self, stamp):
        msg = pkl.dumps((stamp, 'ACK', None, None))
        msg = bytes(f"{len(msg):<{self._header_size}}{self._password}", 'utf-8') + msg
        self.transport.write(data=msg)

    def get_state(self):
        return self._state


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
        logging.info(f'Lost connection.  Reason: {reason.getErrorMessage()}')
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.info(f'Connection failed. Reason: {reason.getErrorMessage()}')
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
        self.to_server = None  # to communicate with the central relay
        self.endpoint = None  # to communicate with endpoint
        self.store = []
        self.ack_stamp = 0
        self.pending_acks = {}  # this contains copies of sent commands until corresponding ACKs are received

    def run(self):
        """
        Main loop containing the reactor loop.

        This is run in its own process.
        """
        # from twisted.internet.interfaces import IReadDescriptor
        from twisted.internet import reactor

        # Initialize the connections 
        reactor.connectTCP(host='127.0.0.1', port=self._local_com_port, factory=LocalProtocolForClientFactory(self))
        reactor.connectTCP(host=self._ip_server, port=self._port_server, factory=TLSClientFactory(client=self))
        
        # Start the reactor
        self._reactor = reactor
        reactor.run()

        # When done, deallocate reactor memory
        self._reactor = None

    def check_acks(self):
        """Returns true if we are not waiting for acknowledgements.

        Returns:
            bool: Whether the dictionary of pending acknowledgements is empty.
        """
        res = len(self.pending_acks.keys()) == 0 
        return res

    def close(self, counter):

        # Check if we are allowed to leave by looking at acknowledgements
        logging.debug(f"Attempting to terminate Endpoint for {counter}th time")

        if self.check_acks():
            if self._reactor is not None:
                if self.to_server is not None:
                    self.to_server.transport.loseConnection()
                logging.info(f"Succesfully terminated endpoint connections")
                self._reactor.stop()
        else:
            from twisted.internet import reactor
            reactor.callLater(1, self.close, counter+1)


if __name__ == "__main__":
    cli = Client(ip_server="127.0.0.1", port_server=8123, password="pswd")
    cli.run()
