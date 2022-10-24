# tlspyo
**A library for secure transfer of python objects over the network**

This library provides an easy-to-use API to transfer python objects over the network in a safe, efficient way. It provides a flexible interface to manage communication between multiple nodes with different roles over a network. It was designed to allow for efficient development of learning infrastructure but is modular enough to be used for any projet where secure and efficient network transfers between multiple computers is required. **Tlspyo** is used in large projects involving hyperparameter tuning and deep reinforcement learning at the MIST Lab.

## Getting Started <a name="getting_started"></a>
Transferring objects using this library is done using two types of objects: 
* A **Relay** is the center point of all communication and is used for the management of the transfer of objects to different groups in different ways. The relay must always be up at any time for communication to be succesful between endpoints.
* An **Endpoint** represents one of the nodes in your network. It can behave in a multitude of ways including broadcasting objects to whole groups or producing objects that can be consumed by other endpoints. an Endpoint can be set up to serve as a producer, a consumer, a compute node...

After installing **tlspyo** using `pip install tlspyo`, you can get started with the following simple example that explains some of the behavior of this library.

### A simple Producer-Consumer example <a name="producer_consumer_example"></a>
In this set up, one of the nodes in your network will be used to produce objets while the other will be used to consume objects by printing them.

The following code creates the objects which you can use to transfer objects between node in your network. Here, everything is run locally but different ports are used to simulate talking to another computer on the network.
```
# Initialize a Relay to allow connectivity between Endpoints
re = Relay(
    port=3000,
    password="VerySecurePassword",
    accepted_groups="group_1, group_2",
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
```
 A nice thing about this library is that all communication is done behind the scenes. The above calls have all launched processes in the background which handle connection between Endpoints through the Relay so that you don't have to handle any blocking calls except when you want to!

 Let's now send some objects from the producer. As you may have noticed, we created two different groups here. We put the producer in "group_1" and the consumer in "group_2". Every Endpoint can be created as being part of any number of groups. When communicating between Endpoints, you can use those groups to make sure the right endpoints get the right objects.

 There are two ways for endpoints to send objects:
 * **Broadcasting** is used to send an an object to every endpoint in a given group.
    ```
    # Producer broadcasts an object to any and all consumer in the destination group "group_2"
    prod.broadcast("I AM BROADCASTED OBJECT", "group_2")
    ```
 * **Producing** is used to send an object to a common queue between endpoints of a given group. The endpoints of the receiving group can then **Notify** the relay to get access to a given number of objects that have been put in that shared queue. This queue behaves as FIFO and objects can only be consumed by one of the receiving endpoint when they have been produced.

    ```
    # Producer sends an object to the shared queue of destination group "group_2"
    prod.produce("I AM A PRODUCED OBJECT", "group_2")
    # Consumer notifies the Relay that it wants one object destined for "group_2"
    cons.notify({"group_2":1})
    ```

Once objects reach the consumer Endpoint, they are stored in a local queue from which you can retrieve objects whenever you want. To do this, there are multiple options:
* To retrieve from the local queue in a FIFO fashion, use `cons.pop(blocking=blocking, max_items=max_items)`.
* To retrieve the most recent item in the local queue and discard the rest, use `cons.get_last(blocking=blocking, max_items=max_items)`.
* To get all items that are currently in the local queue, use `cons.retrieve_all(blocking=blocking)`. 

**Notes:** 
* All calls above return a list of objects. If no objects are returned, the result will be an empty list.
* If `blocking` is true, all methods above will block until one item is received.
* Use `max_items` to specify a maximum number of items to be returned.

**Full Example using the produce/notify API:**
```
from tlspyo import Relay, Endpoint

# Initialize a Relay to allow connectivity between Endpoints
re = Relay(
    port=3000,
    password="VerySecurePassword",
    accepted_groups="group_1, group_2",
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
print(res)
```

There you go! You have now sent your first object over the network using **tlspyo**. You can check out the documentation for more details about the API.

## Security <a name="security"></a>
This library was designed as a safe option to easily transfer any python object over the network using serialization. There are two layers of security:
* This library uses TLS which means that all communication between the Endpoints and the Relay is encrypted.
* Every object transfer is protected using a password known to both the Relay and the Endpoint. No object is deserialized without verification of the password. This ensures that anyone posing as an endpoint will never be able to send undesired objects through your Relay.

This library ships with some default keys and certificates to ensure communication is possible out of the box. However, we recommend you generate your own keys. A script is provided to help you do so:
```
from tlspyo.generate_certificates import gen_cert
gen_cert() 
```
 This will generate two files: private.key and selfsigned.crt in a new folder called keys. Make sure to specify this directory next when starting the Relay:
```
re = Relay(
    port=3000,
    password="VerySecurePassword",
    accepted_groups="group_1, group_2",
    local_com_port=3001,
    header_size=12,
    keys_dir="PATH_TO_MY_KEYS"
)
 ```