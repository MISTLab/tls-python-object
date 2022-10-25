from tlspyo import Relay, Endpoint

if __name__ == "__main__":
    # Initialize a Relay to allow connectivity between Endpoints
    re = Relay(
        port=3000,
        password="VerySecurePassword",
        accepted_groups=None,
        local_com_port=3001,
        header_size=12 # Depends on the size of the objects you are sending
    )

    # Initialize the Producer endpoint
    prod = Endpoint(
        ip_server='127.0.0.1', # Using localhost 
        port=3000, # Must be same port as relay to ensure communication
        password="VerySecurePassword",
        groups="group_1",
        local_com_port=3002, # Must be a different port to simulate communication on different machines
        header_size=12
    )

    # Initialize the Consumer endpoint
    cons = Endpoint(
        ip_server='127.0.0.1', # Using localhost 
        port=3000, # Must be same port as relay to ensure communication
        password="VerySecurePassword",
        groups="group_2",
        local_com_port=3003, # Must be a different port to simulate communication on different machines
        header_size=12
    ) 

    # Producer sends an object to the shared queue of destination group "group_2"
    prod.produce("I AM A PRODUCED OBJECT", "group_2")
    # Consumer notifies the Relay that it wants one object destined for "group_2"
    cons.notify({"group_2":1})

    # Consumer retrieves this object in a blocking call
    res = cons.pop(blocking=True) 
    print(res[0]) # Print the first (and only) result from the local queue
    prod.stop()
    cons.stop()
    re.stop()