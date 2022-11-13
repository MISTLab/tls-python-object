import unittest
import time
import pickle as pkl

from utils import HelperTester


def same_lists_no_order(l1, l2):
    for elt in l1:
        if elt in l2:
            l2.remove(elt)
        else:
            return False
    return len(l2) == 0


def custom_serializer(obj):
    return b"header" + pkl.dumps(["TEST", pkl.dumps(obj)])


def custom_deserializer(bytestring):
    assert len(bytestring) > len(b"header")
    assert bytestring[:len(b"header")] == b"header"
    bytestring = bytestring[len(b"header"):]
    tmp = pkl.loads(bytestring)
    assert isinstance(tmp, list)
    assert len(tmp) == 2
    assert tmp[0] == "TEST"
    obj = pkl.loads(tmp[1])
    return obj


class TestGroups(unittest.TestCase):

    # Set up the server and all endpoints for all tests
    def setUp(self):
        self.ht = HelperTester(serializer=custom_serializer, deserializer=custom_deserializer)

    def test_groups_accept_all(self):
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        relay = sr(accepted_groups=None)
        ep1 = se(groups='group1')
        ep2 = se(groups='group2')
        time.sleep(1.0)  # let everyone handshake the relay so that broadcasts don't get overwritten before that

        # broadcasting

        ep1.send_object(obj='test1', destination='group2')
        r = ep2.pop(blocking=True)
        self.assertEqual(len(r), 1, f"r:{r}")
        self.assertEqual(r[0], 'test1', f"r:{r}")

    def tearDown(self):
        self.ht.clear()


if __name__ == '__main__':
    unittest.main()
