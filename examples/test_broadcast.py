from pydoc import Helper
import unittest
from threading import Thread
import queue

from tlspyo.api import Endpoint, Relay
import time

RELAY_PORT = 2000
LOCAL_PORT = 3000
PASSWORD = 'P4ssw0rd'
TIMEOUT_SERVER = 10
IP_SERVER = '127.0.0.1'


class HelperTester:
    def __init__(self, queue, queue2):
        self.queue = queue
        self.queue2 = queue2

    def producer_process(self):
        # Create an endpoint
        ep = create_endpoint('producer', 3000)

        # Send a counter 50 times to the consumer group
        cpt = 0
        while cpt < 50:
            ep.produce(obj=cpt, group='consumer1')
            cpt += 1

        # Stop the endpoint
        _ = self.queue2.get()
        ep.stop()

    def relay_process(self):
        """
        Function to launch the server. Needs to be called from a separate process.
        """
        re = Relay(port=RELAY_PORT,
                   password=PASSWORD,
                   accepted_groups=None)

        # Run server while tests are running
        _ = self.queue.get()  
        re.stop()


def create_endpoint(group, local_port):
    ep = Endpoint(
        ip_server=IP_SERVER,
        port_server=RELAY_PORT,
        password=PASSWORD,
        groups=group,
        local_com_port=local_port
    )
    return ep


class TestBroadcastObjects(unittest.TestCase):

    # Set up the server and all endpoints for all tests
    def setUp(self):

        # Create a lock and a flag to communicate with the server thread
        self.queue = queue.Queue()
        self.queue2 = queue.Queue()
        self.helper_tester = HelperTester(self.queue, self.queue2)

        # Launch the server
        relay_t = Thread(target=self.helper_tester.relay_process, args=())
        relay_t.start()

    def test_consumer(self):
        # Launch producer endpoint
        endpoint_t = Thread(target=self.helper_tester.producer_process, args=())
        endpoint_t.start()

        # Create consumer endpoint
        ep = create_endpoint('consumer1', 3001)

        # Consume what is produced for us by pair
        cpt = 0
        while cpt < 50:
            # print('Notifying')
            ep.notify(groups={"consumer1": 5})
            # print('Starting to pop')
            res = ep.pop(max_items=1, blocking=True)
            # print(f"res:{res}")
            self.assertEqual(res[0], cpt)
            # print(cpt)
            cpt += 1

        # Stop the endpoint
        ep.stop()
        # Notice to stop the server
        self.queue.put("Done")
        self.queue2.put("DONE")

    # def test_2(self):
    #     pass

    # def test_3(self):
    #     pass

    # Stop the server and all endpoints
    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
