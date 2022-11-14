from tlspyo import Relay, Endpoint

if __name__ == "__main__":

    # Initialize a relay to allow connectivity between endpoints

    re = Relay(
        port=3000,  # this must be the same on your Relay and Endpoints
        password="VerySecurePassword",  # this must be the same on Relay and Endpoints, AND be strong
        local_com_port=3001  # this needs to be non-overlapping if Relays/Endpoints live on the same machine
    )

    # Initialize a producer endpoint

    prod = Endpoint(
        ip_server='127.0.0.1',  # IP of the Relay (here: localhost)
        port=3000,  # must be same port as the Relay
        password="VerySecurePassword",  # must be same (strong) password as the Relay
        groups="producers",  # this endpoint is part of the group "producers"
        local_com_port=3002  # must be unique
    )

    # Initialize  consumer endpoints

    cons_1 = Endpoint(
        ip_server='127.0.0.1',
        port=3000,
        password="VerySecurePassword",
        groups="consumers",  # this endpoint is part of group "consumers"
        local_com_port=3003  # must be unique
    )

    cons_2 = Endpoint(
        ip_server='127.0.0.1',
        port=3000,
        password="VerySecurePassword",
        groups="consumers",  # this endpoint is part of group "consumers"
        local_com_port=3004,  # must be unique
    )

    # Producer broadcasts an object to any and all endpoint in the destination group "consumers"
    prod.broadcast("I HAVE BEEN BROADCAST", "consumers")

    # Producer sends an object to the shared queue of destination group "consumers"
    prod.produce("I HAVE BEEN PRODUCED", "consumers")

    # Consumer 1 notifies the Relay that it wants one produced object destined for "consumers"
    cons_1.notify("consumers")

    # Consumer 1 is able to retrieve the broadcast AND the consumed object:
    res = []
    while len(res) < 2:
        res += cons_1.receive_all(blocking=True)
    print(f"Consumer 1 has received: {res}") # Print the first (and only) result from the local queue

    # Consumer 2 is able to retrieve only the broadcast object:
    res = cons_2.receive_all(blocking=True)
    print(f"Consumer 2 has received: {res}")  # Print the first (and only) result from the local queue

    # Let us close everyone gracefully:
    prod.stop()
    cons_1.stop()
    cons_2.stop()
    re.stop()
