import unittest
from utils import HelperTester

NUM_OBJECTS = 10

class TestAPI(unittest.TestCase):

    # Set up the server and all endpoints for all tests
    def setUp(self):
        self.ht = HelperTester()

    def test_read_with_pop(self):
        '''
        Checks pop functionality with broadcast
        '''
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        _ = sr(accepted_groups=None) # Starts a relay that accepts all groups
        prod = se(groups='group1')
        cons = se(groups='group2')

        # Checks for weird asynchronous behaviour when nothing has been sent yet
        res = cons.pop(blocking=False)
        self.assertEqual(len(res), 0)        

        # Sends objects to a consumer 
        for i in range(NUM_OBJECTS):
            prod.send_object(f"object {i}", destination='group2')

        # Check that objects are received and popped in the right order
        for i in range(NUM_OBJECTS):
            res = cons.pop(max_items=1, blocking=True)
            self.assertEqual(res[0], f"object {i}")

        # Checks for weird values for max_items
        self.assertRaises(AssertionError, lambda : cons.pop(max_items=-1, blocking=False))
        self.assertRaises(AssertionError, lambda : cons.pop(max_items=0, blocking=False))


    def test_produce_notify(self):
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        _ = sr(accepted_groups=None) # Starts a relay that accepts all groups
        prod1 = se(groups='prod1')
        cons1 = se(groups='cons1')
        prod2 = se(groups='prod2')
        cons2 = se(groups='cons2')

        # Check that productions are received in right order by one consumer
        cons1.notify(groups={'cons1': 2})        
        prod1.produce("I'M FIRST", group='cons1')
        prod1.produce("I'M SECOND", group='cons1')
        res = [cons1.pop(blocking=True)[0] for _ in range(2)]
        self.assertEqual(["I'M FIRST", "I'M SECOND"], res)

        # Check that there is no crossover and that elements are sent to right groups
        cons1.notify("cons1")
        cons2.notify("cons2")
        prod1.produce("I'M FOR CONS1", group='cons1')
        prod2.produce("I'M FOR CONS2", group='cons2')
        res1 = cons1.pop(blocking=True)
        res2 = cons2.pop(blocking=True)
        self.assertEqual(res1[0], "I'M FOR CONS1")
        self.assertEqual(res2[0], "I'M FOR CONS2")

        # Check for inputs of notify
        self.assertRaises(AssertionError, lambda: cons1.notify(()))
        self.assertRaises(AssertionError, lambda: cons1.notify([]))
        self.assertRaises(AssertionError, lambda: cons1.notify({"": 0.5}))
        self.assertRaises(AssertionError, lambda: cons1.notify({3: "group3"}))
        self.assertRaises(AssertionError, lambda: cons1.notify(42))
        self.assertRaises(AssertionError, lambda: cons1.notify({}))

        # Check for inputs of produce
        self.assertRaises(AssertionError, lambda: prod1.produce("TEST", 0))
        self.assertRaises(AssertionError, lambda: prod1.produce("TEST", 0.5))
        self.assertRaises(AssertionError, lambda: prod1.produce("TEST", {}))
        self.assertRaises(AssertionError, lambda: prod1.produce("TEST", ()))

        # Check for inputs of send_object
        self.assertRaises(AssertionError, lambda: prod1.send_object("TEST", ()))
        self.assertRaises(AssertionError, lambda: prod1.send_object("TEST", []))
        self.assertRaises(AssertionError, lambda: prod1.send_object("TEST", {"": 0.5}))
        self.assertRaises(AssertionError, lambda: prod1.send_object("TEST", {3: "group3"}))
        self.assertRaises(AssertionError, lambda: prod1.send_object("TEST", 42))
        self.assertRaises(AssertionError, lambda: prod1.send_object("TEST", {}))


    def test_read_with_receive(self):
        '''
        Checks receive all functionality with broadcast.
        '''
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        _ = sr(accepted_groups=None) # Starts a relay that accepts all groups
        prod = se(groups='group1')
        cons = se(groups='group2')

        # Tests that no object are received before they are sent (Weird asynchronous behaviour)
        res = cons.receive_all(blocking=False)
        self.assertEqual(len(res), 0)

        # Producer sends objects
        for i in range(NUM_OBJECTS):
            prod.send_object(f"object {i}", destination='group2')

        # Tests that we have received all objects after a reasonable delay
        res = cons.receive_all(blocking=True)
        # Checks that we have received all objects 
        self.assertEqual(len(res), NUM_OBJECTS)

        # Checks that we have received all objects in the right order
        for i in range(NUM_OBJECTS):
            self.assertEqual(res[i], f"object {i}")


    def test_read_with_get_last(self):
        '''
        Checks get_last functionality with broadcast.
        '''
        sr = self.ht.spawn_relay
        se = self.ht.spawn_endpoint
        _ = sr(accepted_groups=None) # Starts a relay that accepts all groups
        prod = se(groups='group1')
        cons = se(groups='group2')

        # Producer sends objects
        for i in range(NUM_OBJECTS):
            prod.send_object(f"object {i}", destination='group2')

        # Tests that we have received all objects after a reasonable delay
        res = cons.get_last(max_items=5, blocking=True)
        # Checks that we have received all objects 
        self.assertEqual(len(res), 5)

        # Checks that we have received all objects in the right order
        for i in range(1, 6):
            self.assertEqual(res[-i], f"object {10-i}")
        

    def tearDown(self):
        self.ht.clear()


if __name__ == '__main__':
    unittest.main(verbosity=2)
