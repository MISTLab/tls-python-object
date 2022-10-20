from tlspyo import Relay, Endpoint


TEST_RELAY_PORT = 22222
TEST_LOCAL_PORT_START = 33333
TEST_PASSWORD = "Xdha8&89a;/.a,][||=-/.,?><"
TEST_RELAY_IP = '127.0.0.1'
TEST_HEADER_SIZE = 12


class HelperTester:
    def __init__(self):
        self.next_local_port = TEST_LOCAL_PORT_START
        self.endpoints = []
        self.relays = []

    def spawn_endpoint(self, groups):
        ep = Endpoint(
            ip_server=TEST_RELAY_IP,
            port=TEST_RELAY_PORT,
            password=TEST_PASSWORD,
            groups=groups,
            local_com_port=self.next_local_port,
            header_size=TEST_HEADER_SIZE
        )
        self.next_local_port += 1
        self.endpoints.append(ep)
        return ep

    def spawn_relay(self, accepted_groups):
        re = Relay(
            port=TEST_RELAY_PORT,
            password=TEST_PASSWORD,
            accepted_groups=accepted_groups,
            local_com_port=self.next_local_port,
            header_size=TEST_HEADER_SIZE
        )
        self.next_local_port += 1
        self.relays.append(re)
        return re

    def clear(self):
        for ep in self.endpoints:
            ep.stop()
        for re in self.relays:
            re.stop()
