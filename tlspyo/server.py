import os
import time
from collections import deque

import OpenSSL
from twisted.internet.protocol import Protocol, Factory
from twisted.internet import ssl

from tlspyo.local_protocol_for_server import LocalProtocolForServerFactory
from tlspyo.credentials import get_default_keys_folder
from tlspyo.logs import logger


class ServerProtocol(Protocol):

    def __init__(self, server):
        self._server = server
        self._identifier = None
        self._state = "HANDSHAKE"
        self._buffer = b""
        self._password = self._server.password
        self._len_password = len(bytes(self._password, encoding='utf8'))
        self._header_size = self._server.header_size

    def connectionMade(self):
        assert self._state == "HANDSHAKE", f"Bad state: {self._state}"
        self.send_obj(cmd="HELLO")

    def connectionLost(self, reason):
        logger.info(f"Connection lost: {reason.getErrorMessage()}")
        if self._server.has_client(self._identifier):
            self._server.delete_client(self._identifier)
        assert not self._server.has_client(self._identifier)
        self._identifier = None
        self._state = "DEAD"

    def process_header(self):
        i = self._header_size + self._len_password
        if len(self._buffer) < i:
            return 0, len(self._buffer) + 1, None
        try:
            data_len = int(self._buffer[:self._header_size])
        except ValueError:
            logger.info(f"Invalid request.")
            self._state = "KILLED"
            self.transport.abortConnection()
            return 0, len(self._buffer) + 1, None
        j = i + data_len
        psw = self._buffer[self._header_size:i]
        psw = psw.decode('utf8')
        if psw != self._password:
            logger.info(f"Invalid password: {psw}")
            self._state = "KILLED"
            self.transport.abortConnection()
        return i, j, psw

    def dataReceived(self, data):
        try:
            self._buffer += data
            i = self._header_size + self._len_password
            if len(self._buffer) >= i:
                i, j, psw = self.process_header()
                if self._state == "KILLED":  # invalid password or request
                    return
                while len(self._buffer) >= j:
                    stamp, cmd, dest, obj = self._server.deserializer(self._buffer[i:j])
                    if cmd == 'ACK':
                        try:
                            del self._server.pending_acks[stamp]  # delete pending ACK
                        except KeyError:
                            logger.warning(f"Received ACK for stamp {stamp} not present in pending ACKs.")
                    else:
                        self.send_ack(stamp)  # send ACK
                        if isinstance(dest, str):
                            dest = (dest, )
                        if cmd == "HELLO":
                            groups = obj
                            if isinstance(groups, str):
                                groups = (groups,)
                            if self._server.check_new_client(groups=groups):
                                logger.info(f"New client with groups {groups}.")
                                self._identifier = self._server.add_client(groups=groups, client=self)
                                self._state = "ALIVE"
                                self.retrieve_broadcast()
                            else:
                                self._state = "CLOSED"
                                self.transport.loseConnection()
                        elif self._state == "ALIVE":
                            if cmd == "OBJ":
                                logger.debug(f"Received object from client {self._identifier} for groups {dest}.")
                                self.forward_obj_to_dest(obj=obj, dest=dest)
                            elif cmd == "NTF":
                                logger.debug(f"Received notification from client {self._identifier} for destination {dest}.")
                                self.retrieve_consumables(groups=dest)
                            else:
                                logger.warning(f"Invalid command: {cmd}")
                                self._state = "CLOSED"
                                self.transport.loseConnection()
                    # truncate the processed part of the buffer:
                    self._buffer = self._buffer[j:]
                    i, j, psw = self.process_header()
                    if self._state == "KILLED":
                        return
        except Exception as e:
            logger.warning(f"Killing connection because of unhandled exception: {e}")
            self._state = "KILLED"
            self.transport.abortConnection()
            raise e

    def send_obj(self, cmd='OBJ', obj=None):
        self._server.ack_stamp += 1
        msg = self._server.serializer((self._server.ack_stamp, cmd, obj))
        msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
        self._server.pending_acks[self._server.ack_stamp] = (time.monotonic(), msg)
        self.transport.write(msg)

    def send_ack(self, stamp):
        msg = self._server.serializer((stamp, 'ACK', None))
        msg = bytes(f"{len(msg):<{self._header_size}}", 'utf-8') + msg
        self.transport.write(msg)

    def retrieve_broadcast(self):
        if self._identifier is not None:
            for _, d_group in self._server.group_info.items():
                if self._identifier in d_group['ids']:
                    to_broadcast = d_group['to_broadcast']
                    if to_broadcast is not None:
                        logger.debug("Sending object {to_broadcast} from retrieve broadcast")
                        self.send_obj(cmd='OBJ', obj=to_broadcast)

    def retrieve_consumables(self, groups):
        if self._identifier is not None:
            for origin, n in groups.items():  # for each requested origin and requested number of consumables
                if origin in self._server.group_info.keys():
                    d_group = self._server.group_info[origin]
                    if self._identifier in d_group['ids']:
                        if n > 0:
                            # add pending consumables from this group for this client
                            d_group['pending_consumers'][self._identifier] += n
                            logger.debug(f"Pending consumables for client {self._identifier} from group {origin}: {d_group['pending_consumers'][self._identifier]}")
                            # retrieve available pending consumables
                            self.dispatch_pending_consumables(origin)
                        elif n < 0:
                            # send all available consumables from this group to this client
                            self.send_all_consumables(origin)

    def dispatch_pending_consumables(self, group):
        # retrieve at most n available consumables from this group
        logger.debug(f"Dispatching consumables from group {group}.")
        if group in self._server.group_info.keys():
            d_group = self._server.group_info[group]
            to_consume = d_group['to_consume']
            pending_consumers = d_group['pending_consumers']
            for id in pending_consumers.keys():
                while pending_consumers[id] > 0 and len(to_consume) > 0:
                    pending_consumers[id] -= 1
                    obj = to_consume.popleft()
                    logger.debug(f"Sending a consumable to client {id} from group {group} (remaining: {pending_consumers[id]}).")
                    self._server.to_clients[id].send_obj(cmd='OBJ', obj=obj)
        else:
            logger.warning(f"Group {group} is not registered in the server.")

    def send_all_consumables(self, group):
        # retrieve all available consumables from this group
        if group in self._server.group_info.keys():
            d_group = self._server.group_info[group]
            to_consume = d_group['to_consume']
            pending_consumers = d_group['pending_consumers']
            while len(to_consume) > 0:
                logger.debug(f'Sending a consumable to client {self._identifier} from group {group}.')
                obj = to_consume.popleft()
                self.send_obj(cmd='OBJ', obj=obj)

    def forward_obj_to_dest(self, obj, dest):
        if dest is not None:
            assert isinstance(dest, dict), f"destination is a {type(dest)}; must be a dict."
            for group, value in dest.items():
                if self._server.try_add_group(group):
                    d_g = self._server.group_info[group]
                    if value < 0:
                        # broadcast object to group
                        d_g['to_broadcast'] = obj
                        ids = d_g['ids']
                        for id_cli in ids:
                            logger.debug(f"Sending object from group {group} to identifier {id_cli}.")
                            self._server.to_clients[id_cli].send_obj(cmd='OBJ', obj=obj)
                    elif value > 0:
                        # add object to group's consumables
                        logger.debug(f"Adding {value} copies of the consumable to group {group}.")
                        for _ in range(value):
                            d_g['to_consume'].append(obj)
                        self.dispatch_pending_consumables(group)

    def get_state(self):
        return self._state


class ServerProtocolFactory(Factory):

    protocol = ServerProtocol

    def __init__(self, server):
        self.server = server

    def buildProtocol(self, addr):
        logger.info('Connected.')
        return ServerProtocol(self.server)


class Server:
    def __init__(self,
                 port,
                 password,
                 serializer,
                 deserializer,
                 accepted_groups=None,
                 header_size=10,
                 local_com_port=2097,
                 security="TLS",
                 keys_dir=None):

        self.serializer = serializer
        self.deserializer = deserializer

        self._port = port
        self._local_com_port = local_com_port
        assert self._local_com_port != self._port, f"Internet and local ports are the same ({self._port})."
        self.password = password
        self.header_size = header_size
        self._accepted_groups = accepted_groups
        self.to_clients = {}  # dict of identifiers to protocols toward clients
        self.group_info = {}  # dictionary of group names to dicts of group info
        self._id_cpt = 0
        self.ack_stamp = 0
        self.pending_acks = {}  # this contains copies of sent commands until corresponding ACKs are received
        self._reactor = None
        self._listener = None
        self._security = security
        self._keys_dir = keys_dir

    def run(self):
        """
        Main loop containing the reactor loop.

        This is run in its own process.
        """
        # from twisted.internet.interfaces import IReadDescriptor
        from twisted.internet import reactor

        # Start local communication
        reactor.connectTCP(host='127.0.0.1', port=self._local_com_port, factory=LocalProtocolForServerFactory(self))

        # Start relay server
        factory = ServerProtocolFactory(self)
        if self._security == "TCP":
            logger.info(f"Listening on TCP to port {self._port}")
            reactor.listenTCP(self._port, factory)
        elif self._security == "TLS":
            # Use default keys if none are provided
            private_key = os.path.join(self._keys_dir, 'key.pem') if self._keys_dir is not None else os.path.join(get_default_keys_folder(), 'key.pem')
            self_signed = os.path.join(self._keys_dir, 'certificate.pem') if self._keys_dir is not None else os.path.join(get_default_keys_folder(), 'certificate.pem')
            # Authenticates the server to all potential clients for TLS communication
            try:
                context = ssl.DefaultOpenSSLContextFactory(private_key, self_signed)
            except OpenSSL.SSL.Error:
                raise AttributeError("The provided keys directory could not be found or does not contain the necessary keys. \
                    Make sure that you are providing a correct path, that your private key is named 'private.key' and that your public key is named 'selfsigned.crt'. \
                    You can use the script generate_certificates.py to generate the keys.")
            logger.info(f"Listening on TLS to port {self._port}, with credentials {private_key} and {self_signed}")
            reactor.listenSSL(self._port, factory, context)
        else:
            logger.warning(f"Unsupported connection: {self._security}")
            return

        self._reactor = reactor
        self._reactor.run()  # main Twisted reactor loop
        self._reactor = None  # remove when done

    def add_accepted_group(self, group, max_count=None, max_consumables=None):
        """
        Adds a new group name to accepted group names

        :param group: str: name of the new group
        :param max_count: maximum number of simultaneous clients in this group
        :param max_consumables: max number of consumables for this group
        """
        if self._accepted_groups is None:
            self._accepted_groups = {}
        self._accepted_groups[group] = {'max_count': max_count,
                                        'max_consumables': max_consumables}

    def check_new_client(self, groups):
        """
        Checks whether a client can be added to requested groups.

        :param groups: list of strings: requested groups for this client
        :return authorization: bool: whether the client can be added
        """
        if self._accepted_groups is not None:
            for group in groups:
                if group not in self._accepted_groups.keys():
                    logger.info(f"Invalid group {group}.")
                    return False
                if group in self.group_info.keys():
                    max_count = self._accepted_groups[group]['max_count']
                    if max_count is not None and len(self.group_info[group]['ids']) >= max_count:
                        logger.info(f"Cannot add more clients to group {group}.")
                        return False
        return True

    def add_client(self, groups, client):
        identifier = self._id_cpt
        self._id_cpt += 1
        self.to_clients[identifier] = client
        for group in groups:
            if self.try_add_group(group):
                logger.debug(f"Adding client {identifier} to group {group}.")
                self.group_info[group]['ids'].append(identifier)
                self.group_info[group]['pending_consumers'][identifier] = 0
        return identifier

    def try_add_group(self, group):
        """
        Adds group if valid.

        :param group: string: requested group
        :return success: bool: whether the group is valid
        """
        if self._accepted_groups is not None:
            if group not in self._accepted_groups.keys():
                logger.info(f"Invalid group {group}.")
                return False
        self.add_group(group)
        return True

    def add_group(self, group, max_consumables=None):
        if group not in self.group_info.keys():
            logger.debug(f"Adding group {group} to relay")
            self.group_info[group] = {'ids': [],  # ids of the clients present in this group
                                      'to_broadcast': None,  # object to broadcast
                                      'to_consume': deque(maxlen=max_consumables) if max_consumables is not None else deque(),  # queue of objects to consume
                                      'pending_consumers': {}  # dict mapping client ids to number of remaining consumables to send from this group
                                      }

    def delete_client(self, identifier):
        for group, d_group in self.group_info.items():
            idents = d_group['ids']
            if identifier in idents:
                logger.debug(f"Removing client {identifier} from group {group}.")
                idents.remove(identifier)
                del d_group['pending_consumers'][identifier]
        logger.debug(f"Removing client {identifier} from list of clients.")
        del self.to_clients[identifier]

    def has_client(self, identifier):
        return identifier in self.to_clients

    def check_acks(self):
        """Returns true if we are not waiting for acknowledgements.

        Returns:
            bool: Whether the dictionary of pending acknowledgements is empty.
        """
        res = len(self.pending_acks.keys()) == 0 
        return res

    def close(self, counter):

        # Check if we are allowed to leave by looking at acknowledgements
        logger.debug(f"Attempting to terminate Relay for {counter}th time")

        if self.check_acks() or counter > 10:
            if self._reactor is not None:
                identifiers = list(self.to_clients.keys())
                for identifier in identifiers:
                    self.to_clients[identifier].transport.loseConnection()
                    self.delete_client(identifier)
                logger.info(f"Succesfully terminated relay connections")
                self._reactor.stop()
        else:
            from twisted.internet import reactor
            reactor.callLater(1, self.close, counter+1)
        

if __name__ == "__main__":
    pass
