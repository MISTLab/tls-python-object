from pydoc import Helper
import unittest
from threading import Thread, Lock
import queue

from tlspyo.api import Endpoint, Relay
import time

RELAY_PORT = 22222
LOCAL_PORT_START = 33333
PASSWORD = "Xdha8&89a;/.a,][||=-/.,?><"
RELAY_IP = '127.0.0.1'
HEADER_SIZE = 12


class HelperTester:
    def __init__(self):
        self.next_local_port = LOCAL_PORT_START

    def spawn_endpoint(self, groups):
        ep = Endpoint(
            ip_server=RELAY_IP,
            port=RELAY_PORT,
            password=PASSWORD,
            groups=groups,
            local_com_port=self.next_local_port,
            header_size=HEADER_SIZE
        )
        self.next_local_port += 1
        return ep

    def spawn_relay(self, accepted_groups):
        re = Relay(
            port=RELAY_PORT,
            password=PASSWORD,
            accepted_groups=accepted_groups,
            local_com_port=self.next_local_port,
            header_size=HEADER_SIZE
        )
        self.next_local_port += 1
        return re


class TestGroups(unittest.TestCase):

    # Set up the server and all endpoints for all tests
    def setUp(self):
        self.ht = HelperTester()

    def test_groups_accept_all(self):
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        relay = sr(accepted_groups=None)
        ep1 = se(groups='group1')
        ep2 = se(groups=('group1', 'group2'))
        ep3 = se(groups='group3')
        ep4 = se(groups='group5')
        ep5 = se(groups=('group6', 'group5', 'group1'))

        ep5.send_object(obj='test1', destination='group1')
        r = ep1.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test1', f"r:{r}")

        ep5.send_object(obj='test2', destination='group1')
        r = ep1.receive_all(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test2', f"r:{r}")

        ep2.send_object(obj='test3', destination='group1')
        r = ep1.receive_all(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test3', f"r:{r}")
        r = []
        while len(r) < 3:
            r += ep2.receive_all(blocking=True)
        self.assertEqual(len(r), 3, f"r:{r}")
        self.assertEqual(r[0], 'test1', f"r:{r}")
        self.assertEqual(r[1], 'test2', f"r:{r}")
        self.assertEqual(r[2], 'test3', f"r:{r}")

        ep1.send_object(obj='test4', destination=('group1', 'group5', 'group6'))
        r = ep1.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test4', f"r:{r}")
        r = []
        while len(r) < 6:
            r += ep5.receive_all(blocking=True)
        self.assertEqual(len(r), 6, f"r:{r}")
        self.assertEqual(r[0], 'test1', f"r:{r}")
        self.assertEqual(r[1], 'test2', f"r:{r}")
        self.assertEqual(r[2], 'test3', f"r:{r}")
        self.assertEqual(r[3], 'test4', f"r:{r}")
        self.assertEqual(r[4], 'test4', f"r:{r}")
        self.assertEqual(r[5], 'test4', f"r:{r}")
        r = ep4.get_last(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test4', f"r:{r}")

        ep1.send_object(obj='test5', destination='group3')
        ep1.send_object(obj='test6', destination='group3')
        r = ep3.get_last(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        if r[0] == 'test5':
            r = ep3.get_last(blocking=True)
            self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test6', f"r:{r}")

        ep1.stop()
        ep2.stop()
        ep3.stop()
        ep4.stop()
        ep5.stop()
        relay.stop()

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
