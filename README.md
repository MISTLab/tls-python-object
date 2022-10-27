# tlspyo
**A library for secure transfer of python objects over the network**

This library provides an easy-to-use API to transfer python objects over the network in a safe, efficient way. It provides a flexible interface to manage communication between multiple nodes with different roles over a network. It was designed to allow for efficient development of learning infrastructure in Python but is modular enough to be used for any projet where communication between multiple computers is required. **Tlspyo** is used in several projects at the MIST Lab for [hyperparameter-tuning](https://github.com/Portiloop) and [deep reinforcement learning](https://github.com/trackmania-rl/tmrl) using multiple learning agents.

## Getting Started
Transferring objects using this library is done using two types of objects: 
* A **relay** is the center point of all communication and is used to manage the transfer of objects to different groups of endpoints in different ways. The relay must always be up at any time for communication to be succesful between endpoints.
* An **endpoint** represents one of the nodes in your network. It can behave in a multitude of ways including broadcasting objects to whole groups or producing objects that can be consumed by other endpoints. An endpoint can be set up to serve as a producer, a consumer, a compute node...

After installing **tlspyo** using `pip install tlspyo`, you can get started with the following simple example that explains some of the behavior of this library.

### A Simple Producer-Consumer Example 
In this set up, one of the nodes in your network will be used to produce objets while the other will be used to consume objects by printing them.

The following code creates the objects which you can use to transfer objects between node in your network. Here, everything is run locally but different ports are used to simulate talking to another computer on the network.
```python
# Initialize a relay to allow connectivity between endpoints
re = Relay(
    port=3000,
    password="VerySecurePassword",
    accepted_groups=None,
    local_com_port=3001,
    header_size=12 # Depends on the size of the objects you are sending
)

# Initialize the producer endpoint
prod = Endpoint(
    ip_server='127.0.0.1', # Using localhost 
    port=3000, # Must be same port as relay to ensure communication
    password="VerySecurePassword",
    groups="group_1",
    local_com_port=3002, # Must be a different port to simulate communication on different machines
    header_size=12
)

# Initialize the consumer endpoint
cons = Endpoint(
    ip_server='127.0.0.1', # Using localhost 
    port=3000, # Must be same port as relay to ensure communication
    password="VerySecurePassword",
    groups="group_2",
    local_com_port=3003, # Must be a different port to simulate communication on different machines
    header_size=12
) 
```
 A nice thing about this library is that all communication is handled behind the scenes. The above calls have all launched processes in the background which handle connection between endpoints through the relay so that you don't have to make any blocking calls except when you want to!

 Let's now send some objects from the producer. As you may have noticed, we created two different groups here. We put the producer in "group_1" and the consumer in "group_2". Every endpoint can be created as being part of any number of groups. When communicating between endpoints, you can use those groups to make sure the right endpoints get the right objects.

 There are two ways for endpoints to send objects:
 * **Broadcasting** is used to send an an object to every endpoint in a given group.
    ```python
    # Producer broadcasts an object to any and all consumer in the destination group "group_2"
    prod.broadcast("I AM BROADCASTED OBJECT", "group_2")
    ```
 * **Producing** is used to send an object to a queue that is shared between all endpoints of a given group. The endpoints of the receiving group can then **Notify** the relay to get access to a certain number of objects that have been put in that shared queue. This queue behaves as FIFO and objects can only be consumed by one of the receiving endpoint when they have been produced.

    ```python
    # Producer sends an object to the shared queue of destination group "group_2"
    prod.produce("I AM A PRODUCED OBJECT", "group_2")
    # Consumer notifies the Relay that it wants one object destined for "group_2"
    cons.notify({"group_2":1})
    ```

Once objects reach the consumer endpoint, they are stored in a local queue from which you can retrieve objects whenever you want. To do this, there are multiple options:
* To retrieve from the local queue in a FIFO fashion, use `cons.pop(blocking=blocking, max_items=max_items)`.
* To retrieve the most recent item in the local queue and discard the rest, use `cons.get_last(blocking=blocking, max_items=max_items)`.
* To get all items that are currently in the local queue, use `cons.retrieve_all(blocking=blocking)`. 

**Notes:** 
* All calls above return a list of objects. If no objects are returned, the result will be an empty list.
* If `blocking` is true, all methods above will block until one item is received.
* Use `max_items` to specify a maximum number of items to be returned.

When you are done with your communication needs, do not forget to stop all endpoints and relays to make sure your program dies peacefully. Note that once the relay is stopped, all communication between endpoints will fail so make sure that your relay is up whenever you are trying to communicate.
```python
prod.stop()
cons.stop()
re.stop()
```

**Full Example using the produce/notify API:**
```python
from tlspyo import Relay, Endpoint

# Spawning processes in python must be protected by this if statement to avoid recursively spawning child processes.
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
```

There you go! You have now sent your first object over the network using **tlspyo**. You can check out the documentation for more details about the API.

## Security
This library was designed as a safe option to easily transfer any python object over the network using serialization. There are two layers of security:
* This library uses TLS which means that all communication between the endpoints and the relay is encrypted.
* Every object transfer is protected using a password known to both the relay and the endpoint. No object is deserialized without verification of the password. This ensures that anyone posing as an endpoint will never be able to send undesired objects through your relay unless they know the password.

This library ships with some default keys and certificates to ensure communication is possible out of the box. However, we recommend you generate your own keys. To do so, use the following command:
```bash
openssl req -newkey rsa:2048 -nodes -keyout key.pem -x509 -days 365 -out certificate.pem
```
You will be asked some questions and a certificate and a private key will be generated. Make sure to take careful note of the **common name/hostname** that you choose as you must specify it when you want to initialize an endpoint. These two need to be stored in the same directory which must be specified when initializing the relay and all endpoints. Make sure that these certificates match or authentication of your endpoints to your relay will fail. 
```python
re = Relay(
    port=3000,
    password="VerySecurePassword",
    accepted_groups=None,
    local_com_port=3001,
    header_size=12,
    keys_dir="PATH_TO_MY_KEYS" # Change this
)

re = Relay(
    port=3000,
    password="VerySecurePassword",
    accepted_groups=None,
    local_com_port=3001,
    header_size=12,
    keys_dir="PATH_TO_YOUR_KEYS", # Change this
    hostname="YOUR_HOSTNAME" # Change this
)
 ```

**:warning:IMPORTANT NOTE:warning:**
This library uses pickle to serialize objects before sending them over the network. Someone who knows your password and has access to your relay public IP address could send some malevolent pickled object which could execute arbitrary code on your machine. **Please make sure to keep your password and your key/certificate pair safe!**

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


## License

Distributed under the MIT License. See `LICENSE.txt` for more information.