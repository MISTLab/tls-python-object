import time
import os

import OpenSSL
from twisted.python.filepath import FilePath
from twisted.internet import ssl
from twisted.internet.protocol import Protocol, ReconnectingClientFactory

from tlspyo.local_protocol_for_client import LocalProtocolForClientFactory
from tlspyo.credentials import get_default_keys_folder
from tlspyo.logs import logger


class ClientProtocol(Protocol):
    def __init__(self,
                 client,
                 password,
                 header_size=10,
                 groups=("default", )):

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
                stamp, cmd, obj = self._client.deserializer(self._buffer[i:j])
                if cmd == 'ACK':
                    try:
                        logger.debug(f"ACK received after {time.monotonic() - self._client.pending_acks[stamp][0]}s.")
                        del self._client.pending_acks[stamp]  # delete pending ACK
                    except KeyError:
                        logger.warning(f"Received ACK for stamp {stamp} not present in pending ACKs.")
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
                            logger.warning(f"Received a command in a bad state: {self._state}.")
                        if cmd == "OBJ":
                            logger.debug(f"Received object, transferring to local EndPoint.")
                            # transfer the object to the EndPoint server
                            if self._client.endpoint is not None:
                                self._client.endpoint.transport.write(self._buffer[:j])
                            else:
                                logger.warning(f"Local EndPoint is not connected, discarding object.")
                # truncate the processed part of the buffer:
                self._buffer = self._buffer[j:]
                i, j = self.process_header()

    def send_obj(self, cmd='OBJ', dest=None, obj=None):
        self._client.ack_stamp += 1
        msg = self._client.serializer((self._client.ack_stamp, cmd, dest, obj))
        msg = bytes(f"{len(msg):<{self._header_size}}{self._password}", 'utf-8') + msg
        self._client.pending_acks[self._client.ack_stamp] = (time.monotonic(), msg)
        self.transport.write(msg)

    def send_ack(self, stamp):
        msg = self._client.serializer((stamp, 'ACK', None, None))
        msg = bytes(f"{len(msg):<{self._header_size}}{self._password}", 'utf-8') + msg
        self.transport.write(msg)

    def get_state(self):
        return self._state


class TLSClientFactory(ReconnectingClientFactory):
    protocol = ClientProtocol

    def __init__(self, client):
        self.password = client.password
        self._groups = client.groups
        self._header_size = client.header_size
        self._client = client
        self.maxDelay = self._client.recon_max_delay
        self.initialDelay = self._client.recon_initial_delay
        self.factor = self._client.recon_factor
        self.jitter = self._client.recon_jitter

    def startedConnecting(self, connector):
        logger.info('Started to connect.')

    def buildProtocol(self, addr):
        logger.info('Connected.')
        self.resetDelay()
        return ClientProtocol(client=self._client,
                              password=self.password,
                              groups=self._groups,
                              header_size=self._header_size)

    def clientConnectionLost(self, connector, reason):
        logger.info(f'Lost connection.  Reason: {reason.getErrorMessage()}')
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logger.info(f'Connection failed. Reason: {reason.getErrorMessage()}')
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


class Client:
    def __init__(self,
                 ip_server,
                 port_server,
                 password,
                 serializer,
                 deserializer,
                 header_size=10,
                 groups=None,
                 local_com_port=2097,
                 security="TLS",
                 keys_dir=None,
                 hostname='default',
                 recon_max_delay=60.0,
                 recon_initial_delay=10.0,
                 recon_factor=1.5,
                 recon_jitter=0.1):

        self.serializer = serializer
        self.deserializer = deserializer

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
        self._security = security
        self._keys_dir = keys_dir
        self._hostname = hostname
        self.recon_max_delay = recon_max_delay
        self.recon_initial_delay = recon_initial_delay
        self.recon_factor = recon_factor
        self.recon_jitter = recon_jitter

    def run(self):
        """
        Main loop containing the reactor loop.

        This is run in its own process.
        """
        # from twisted.internet.interfaces import IReadDescriptor
        from twisted.internet import reactor

        # Initialize the local connection
        reactor.connectTCP(host='127.0.0.1', port=self._local_com_port, factory=LocalProtocolForClientFactory(self))

        # Initialize the Internet connection
        if self._security == "TCP":
            reactor.connectTCP(host=self._ip_server, port=self._port_server, factory=TLSClientFactory(client=self))
        elif self._security == "TLS":
            # Use default keys if none are provided
            self_signed = os.path.join(self._keys_dir, 'certificate.pem') if self._keys_dir is not None else os.path.join(get_default_keys_folder(), 'certificate.pem')
            # Authenticates the server to all potential clients for TLS communication
            try:
                certData = FilePath(self_signed).getContent()
            except OpenSSL.SSL.Error:
                raise AttributeError("The provided keys directory could not be found or does not contain the necessary keys. \
                    Make sure that you are providing a correct path, that your private key is named 'private.key' and that your public key is named 'selfsigned.crt'. \
                        You can use the script generate_certificates.py to generate the keys.")
            authority = ssl.Certificate.loadPEM(certData)            
            reactor.connectSSL(
                host=self._ip_server,
                port=self._port_server,
                factory=TLSClientFactory(client=self),
                contextFactory=ssl.optionsForClientTLS(hostname=self._hostname, trustRoot=authority)
            )
        else:
            logger.warning(f"Unsupported connection: {self._security}")
        
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
        logger.debug(f"Attempting to terminate Endpoint for {counter}th time")

        if self.check_acks() or counter > 10:
            if self._reactor is not None:
                if self.to_server is not None:
                    self.to_server.transport.loseConnection()
                logger.info(f"Succesfully terminated endpoint connections")
                self._reactor.stop()
        else:
            from twisted.internet import reactor
            reactor.callLater(1, self.close, counter+1)


if __name__ == "__main__":
    cli = Client(ip_server="127.0.0.1", port_server=8123, password="pswd")
    cli.run()
