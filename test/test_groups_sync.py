import unittest
import time

from utils import HelperTester


def same_lists_no_order(l1, l2):
    for elt in l1:
        if elt in l2:
            l2.remove(elt)
        else:
            return False
    return len(l2) == 0


class TestGroupsSync(unittest.TestCase):

    # Set up the server and all endpoints for all tests
    def setUp(self):
        self.ht = HelperTester(deserializer_mode="synchronous")

    def test_groups_accept_all(self):
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        relay = sr(accepted_groups=None)
        ep1 = se(groups='group1')
        ep2 = se(groups=('group1', 'group2'))
        ep3 = se(groups='group3')
        ep4 = se(groups='group5')
        ep5 = se(groups=('group6', 'group5', 'group1'))
        time.sleep(1.0)  # let everyone handshake the relay so that broadcasts don't get overwritten before that

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

        # test mixed broadcasting / producing

        ep5.send_object(obj='test9', destination={'group1': 1, 'group2': 1})  # this produces to group 1 and 2
        ep5.send_object(obj='test10', destination={'group1': -1, 'group2': -1})  # this broadcasts to groups 1 and 2
        ep1.notify(groups=('group1', 'group2', 'group999'))  # note that ep1 is in group 1 only
        r = []
        while len(r) < 2:
            r += ep1.receive_all(blocking=True)
        self.assertEqual(len(r), 2, f"r:{r}")
        self.assertIn('test9', r, f"r:{r}")
        self.assertIn('test10', r, f"r:{r}")
        ep2.notify(groups=('group1', 'group2'))  # note that ep2 is in group 1 and group 2, but group 1 is empty
        r = []
        while len(r) < 3:
            r += ep2.receive_all(blocking=True)
        self.assertEqual(len(r), 3, f"r:{r}")
        self.assertTrue(same_lists_no_order(r, ['test9', 'test10', 'test10']), f"r:{r}")
        ep5.send_object(obj='test11', destination={'group1': 1})  # let us send one more consumable to group 1
        r = ep2.receive_all(blocking=True)  # now the notification sent by ep2 can be fulfilled
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test11', f"r:{r}")

        # test multiple producing / consuming

        ep5.send_object(obj='test12', destination={'group1': 10})  # this produces to group 1
        ep5.send_object(obj='test13', destination={'group2': 10})  # this produces to group 2
        ep2.notify(groups={'group1': 1})  # retrieve 1 elt in group 1
        r = []
        while len(r) < 11:  # one consumable in group1 and all consumables is group 2
            ep2.notify(groups={'group2': -1})  # ask for all elts in group 2
            r += ep2.receive_all(blocking=True)
        self.assertEqual(len(r), 11, f"r:{r}")
        self.assertTrue(same_lists_no_order(r, ['test12', ] + ['test13', ] * 10), f"r:{r}")
        r = []
        while len(r) < 9:  # all remaining consumables in group 1
            ep1.notify(groups={'group1': -1})  # ask for all elts in group 1
            r += ep1.receive_all(blocking=True)
        self.assertEqual(len(r), 9, f"r:{r}")
        self.assertTrue(same_lists_no_order(r, ['test12', ] * 9), f"r:{r}")

    def test_groups_accept_some(self):
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        accepted_groups = {
            'group1': {'max_count': 2, 'max_consumables': 2},
            'group2': {'max_count': 1, 'max_consumables': 1},
            'group3': {'max_count': 1, 'max_consumables': 0},
            'group4': {'max_count': None, 'max_consumables': None}
        }
        relay = sr(accepted_groups=accepted_groups)
        # nobody is in group 4, and groups 5 and 6 are not accepted
        ep1 = se(groups=('group6', 'group5', 'group1'))  # should not connect as group 5 and 6 are not allowed
        ep2 = se(groups='group1')  # should connect
        ep3 = se(groups=('group1', 'group2'))  # should connect
        ep4 = se(groups='group3')  # should connect
        time.sleep(1.0)  # let everyone connect so that old broadcasts are not lost for new clients
        ep5 = se(groups='group1')  # should not connect as group1 is full
        time.sleep(0.5)

        # test broadcasting

        ep5.send_object(obj='test1', destination='group1')  # should not send as ep5 is not connected
        # (the previous line should also output a warning)
        time.sleep(0.5)
        r = ep1.pop(blocking=False)  # not connected so should not receive
        self.assertEqual(len(r), 0, f"r:{r}")
        r = ep2.pop(blocking=False)  # should not receive since nothing should have been be sent
        self.assertEqual(len(r), 0, f"r:{r}")

        ep4.send_object(obj='test2', destination='group1')  # should send
        time.sleep(0.5)
        r = ep1.pop(blocking=False)  # not connected so should not receive
        self.assertEqual(len(r), 0, f"r:{r}")
        r = ep2.pop(blocking=True)  # should receive
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test2')

        ep2.produce(obj='test3', group='group2')
        ep3.notify(groups='group2')
        r = []
        while len(r) < 2:
            r += ep3.receive_all(blocking=True)
        self.assertEqual(len(r), 2, f"r:{r}")
        self.assertTrue(same_lists_no_order(r, ['test2', 'test3']), f"r:{r}")

    def tearDown(self):
        self.ht.clear()


if __name__ == '__main__':
    unittest.main()
