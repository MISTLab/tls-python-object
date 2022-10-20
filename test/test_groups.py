import unittest
from utils import HelperTester


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

        # test broadcasting

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
        r = ep2.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test4', f"r:{r}")
        r = ep4.pop(blocking=True)
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

        ep1.send_object(obj='test5', destination='group3')
        ep1.send_object(obj='test6', destination='group3')
        r = ep3.get_last(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        if r[0] == 'test5':
            r = ep3.get_last(blocking=True)
            self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test6', f"r:{r}")

        # test producing

        ep1.produce(obj='test7', group='group3')
        ep3.notify(groups='group3')
        r = ep3.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test7', f"r:{r}")

        ep1.send_object(obj='test8', destination={'group1': 3})
        ep1.notify(groups='group1')
        ep2.notify(groups='group1')
        ep5.notify(groups='group1')
        r = ep1.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test8', f"r:{r}")
        r = ep2.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test8', f"r:{r}")
        r = ep5.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test8', f"r:{r}")

    def tearDown(self):
        self.ht.clear()


if __name__ == '__main__':
    unittest.main()
