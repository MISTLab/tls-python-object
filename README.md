# tls-python-object (tlspyo)

:computer: :globe_with_meridians: :computer: **A library for secure transfer of python objects over network.**

[![Python package](https://github.com/MISTLab/tls-python-object/actions/workflows/python-package.yml/badge.svg)](https://github.com/MISTLab/tls-python-object/actions/workflows/python-package.yml)

`tlspyo` provides a simple API to transfer python objects in a robust and safe way via [TLS](https://en.wikipedia.org/wiki/Transport_Layer_Security), between several machines (and/or processes) called `Endpoints`.

- `Endpoints` are part of one to several groups,
- Arbitrarily many `Endpoints` connect together via a central `Relay`,
- Each `Endpoint` can *broadcast* or *produce* python objects to the desired groups.

:information_source: _Please carefully read the [Security](#security) section before using `tlspyo` anywhere other than your own secure private network._


## Principle

`tlspyo` provides two classes: `Relay` and  `Endpoint`.

* The `Relay` is the center point of all communication between `Endpoints`,
* An `Endpoint` is a node in your network. It connects to the `Relay` and is part of one to several `groups`.

`Endpoints` can do a multitude of things, including:
- *broadcast* python objects to whole groups of `Endpoints`,
- *retrieve* the objects broadcast to the group(s) it is part of,
- *produce* a single object that will be consumed by a single `Endpoint` of a target group,
- *notify* the `Relay` that it is ready to consume a produced object and wait until it receives it.

By default, `tlspyo` relies on Transport Layer Security (TLS) to secure object transfers over network.

## Example usage

```python
from tlspyo import Relay, Endpoint

if __name__ == "__main__":

    # Create a relay to allow connectivity between endpoints

    re = Relay(
        port=3000,  # this must be the same on your Relay and Endpoints
        password="VerySecurePassword",  # this must be the same on Relay and Endpoints, AND be strong
        local_com_port=3001  # this needs to be non-overlapping if Relays/Endpoints live on the same machine
    )

    # Create an Endpoint in group "producers" (arbitrary name)

    prod = Endpoint(
        ip_server='127.0.0.1',  # IP of the Relay (here: localhost)
        port=3000,  # must be same port as the Relay
        password="VerySecurePassword",  # must be same (strong) password as the Relay
        groups="producers",  # this endpoint is part of the group "producers"
        local_com_port=3002  # must be unique
    )

    # Create a bunch of other Endpoints in group "consumers" (arbitrary name)

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
        res = cons_1.receive_all(blocking=True)
    print(f"Consumer 1 has received: {res}") # Print the first (and only) result from the local queue

    # Consumer 2 is able to retrieve only the broadcast object:
    res = cons_2.receive_all(blocking=True)
    print(f"Consumer 2 has received: {res}")  # Print the first (and only) result from the local queue

    # Let us close everyone gracefully:
    prod.stop()
    cons_1.stop()
    cons_2.stop()
    re.stop()
```

## Getting started

:information_source: _The machine hosting your `Relay` must be visible to the machines hosting your `Endpoints` through port `<port>`, via its public IP `<ip>`.
When using `tlspyo` over the Internet, this typically requires you to configure your router such that it forwards port `<port>` to the IP of the machine hosting your `Relay` on your local network._


### Installation
From PyPI:
```bash
pip install tlspyo
```

### TLS setup:

:information_source: _You can skip this section if you do not want to use TLS.
For instance if you use `tlspyo` on your own private secure network.
When using `tlspyo` over the Internet, you should of course use TLS (read the [security](#security) section if you do not understand why)._

- **Generate TLS credentials:**

`tlspyo` makes the process of generating your TLS credentials straightforward.

:arrow_forward: On the machine that will host your `Relay`, execute the following command line:
```bash
python -m tlspyo --generate
```
This will generate two files in the `tlspyo/credentials` data directory: `key.pem` and `certificate.pem`.

:information_source: _In case you wish to customize your TLS certificate, add the `--custom` option in the previous command line._

Now, your need to retrieve your `certificate.pem` on the machines that will host your `Endpoints`
_(note: you can skip the following steps if your `Endpoints` are on the same machine as your `Relay`)._

This can be achieved via either of the following methods:

- **METHOD 1: manually copy the public certificate (more secure):**

:arrow_forward: On the machines that will host your `Endpoints`, execute:
```bash
python -m tlspyo --credentials
```
This creates and displays the target folder where you need to copy the `certificate.pem` that you generated on the machine that will host the `Relay` (the source folder was displayed when you executed `--generate`).

- **METHOD 2: transfer the public certificate via TCP (not secure):**

:warning: _This method is not secure.
In particular, a man-in-the-middle can impersonate the certificate-broadcasting server and send you a fraudulent TLS certificate.
Use with caution._

:arrow_forward: On the machine that will host your `Relay`, start a certificate-broadcasting server:
```bash
python -m tlspyo --broadcast --port=<port>
```
where `<port>` is a port though which other machines will attempt to retrieve your certificate via TCP.

:arrow_forward: On the machines that will host your `Endpoints`, execute:
```bash
python -m tlspyo --retrieve --ip=<ip> --port=<port>
```
where `<ip>` is the public IP of the certificate-broadcasting machine, and `<port>` is the same as previously.

And you are all set! :sunglasses:

_You can now stop the certificate-broadcasting server by closing the terminal where it runs._






### A Simple Producer-Consumer Example

Let us now see how to make basic usage of `tlspyo`.
In this example, we will create a `Relay` and two `Endpoints` on the same machine, and have them transfer objects via `localhost`.
The full script for this example can be found [here](https://github.com/MISTLab/tls-python-object/blob/main/examples/example_doc.py).

Import the `Relay` and `Endpoint` classes:
```python
from tlspyo import Relay, Endpoint
```

#### Relay

Every `tlspyo` application requires a central `Relay`.

The `Relay` lives on a machine that can be reached by all `Endpoints`.
Typically, you will want this machine to be accessible to your `Endpoints` via your private local network, or via the Internet through [port forwarding](https://en.wikipedia.org/wiki/Port_forwarding).
**Note however that, before you make your `Relay` visible to the Internet via, e.g., port forwarding, it is important that you read the [Security](#security) section.**

Creating a `Relay` is straightforward:
```python
# Initialize a relay to allow connectivity between endpoints

re = Relay(
    port=3000,  # this must be the same on your Relay and Endpoints
    password="VerySecurePassword",  # this must be the same on Relay and Endpoints, AND be strong
    local_com_port=3001,  # this needs to be non-overlapping if Relays/Endpoints live on the same machine
    connection="TLS"  # this is the default; replace by "TCP" if you do not want to use TLS
)
```
As soon as your `Relay` is created, it is up and running.
Behind the scenes, it is now waiting for TLS connections from `Endpoints`.
This is done in a background process that listens to `port` 3000 in this example.
This process also communicates with your `Relay` via `local_com_port` 3001 in this example.

Usually, you can ignore `local_com_port` and leave it to the default, unless you use several `Endpoints/Relay` on the same machine, which we will do.

#### Endpoints
Now that our `Relay` is ready, let us create a bunch of `Endpoints`.
This is also pretty straightforward:
```python
# Initialize a producer endpoint

prod = Endpoint(
    ip_server='127.0.0.1', # IP of the Relay (here: localhost)
    port=3000, # must be same port as the Relay
    password="VerySecurePassword", # must be same (strong) password as the Relay
    groups="producers",  # this endpoint is part of the group "producers"
    local_com_port=3002,  # must be unique
    connection="TLS"  # this is the default; replace by "TCP" if you do not want to use TLS
)

# Initialize  consumer endpoints

cons_1 = Endpoint(
    ip_server='127.0.0.1',
    port=3000,
    password="VerySecurePassword",
    groups="consumers",  # this endpoint is part of group "consumers"
    local_com_port=3003,  # must be unique
    connection="TLS"
) 

cons_2 = Endpoint(
    ip_server='127.0.0.1',
    port=3000,
    password="VerySecurePassword",
    groups="consumers",  # this endpoint is part of group "consumers"
    local_com_port=3004,  # must be unique
    connection="TLS"
) 
```
 A nice thing about `tlspyo` is that all communication is handled behind the scenes.
 The above calls have all launched processes in the background which handle connection and communication between `Endpoints` through the `Relay`.

 Let us now send some objects from the producer to the consumers.
 As you may have noticed, we created two different groups here.
 We put the producer in a group that we have named "producers", and the consumers in another group that we have called "consumers".
 Note that `Endpoint` can be created as being part of any number of groups (`groups` can take a list of strings).
 When communicating between endpoints, you can use those groups to make sure the right endpoints receive the right objects.

 There are two ways for `Endpoints` to send objects in `tlspyo`:
 * **Broadcasting** is used to send an object to all endpoint in a given group.
Furthermore, when an `Endpoint` connects to the `Relay`, it receives the last object that was broadcast to each of his groups.
    ```python
    # Producer broadcasts an object to any and all endpoint in the destination group "consumers"
    prod.broadcast("I HAVE BEEN BROADCAST", "consumers")
    ```
 * **Producing** is used to send an object to a queue (FIFO) that is shared between all `Endpoints` of a given group.
The endpoints of the receiving group must **Notify** the `Relay` to get access to an object that has been put in that shared queue.

    ```python
    # Producer sends an object to the shared queue of destination group "consumers"
    prod.produce("I HAVE BEEN PRODUCED", "consumers")

    # Consumer notifies the Relay that it wants one produced object destined for "consumers"
    cons_1.notify("consumers")
    ```

Once objects reach the consumer endpoint, they are stored in a local queue from which you can retrieve objects whenever you want. To do this, there are multiple options:
* To retrieve from the local queue in a FIFO fashion, use `pop(blocking=blocking, max_items=max_items)`.
* To retrieve the most recent item(s) in the local queue and discard the rest, use `get_last(blocking=blocking, max_items=max_items)`.
* To get all items that are currently in the local queue, use `receive_all(blocking=blocking)`. 

:information_source: _Notes:_
* _All calls above return a list of objects. If no objects are returned, the result will be an empty list._
* _If `blocking` is `True`, all methods above will block until at least one item is received (default to `False`)._
* _In`pop` and `get_last`, use `max_items` to specify a maximum number of items to be returned (defaults to 1)._

Now, let our consumers retrieve their loot:
```python
# Consumer 1 is able to retrieve the broadcast AND the consumed object:
 res = []
 while len(res) < 2:
     res = cons_1.receive_all(blocking=True)
 print(f"Consumer 1 has received: {res}") # Print the first (and only) result from the local queue

 # Consumer 2 is able to retrieve only the broadcast object:
 res = cons_2.receive_all(blocking=True)
 print(f"Consumer 2 has received: {res}")  # Print the first (and only) result from the local queue
```
 which prints:
```terminal
Consumer 1 has received: ['I HAVE BEEN BROADCAST', 'I HAVE BEEN PRODUCED']
Consumer 2 has received: ['I HAVE BEEN BROADCAST']
```

Once we are done, we can `stop` all `Endpoints`, and then the `Relay` for the sake of a graceful exit:
```python
# Let us close everyone gracefully:
 prod.stop()
 cons_1.stop()
 cons_2.stop()
 re.stop()
```

There you go! You have now sent your first object over the network using `tlspyo`.

Please check out the [API documentation](https://github.com/MISTLab/tls-python-object/blob/main/tlspyo/api.py) for more advanced usage.

## Security

### DISCLAIMER
We are doing our best to make `tlspyo` reasonably secure **when used correctly**, but we provide ABSOLUTELY NO GUARANTEE that it is in any sense.
We are a small open-source community, and we greatly appreciate your contribution to tackle any potentially unreasonable security concerns or important missing information.
Please submit a detailed issue if you are aware of any important exploit not covered in this section.

### Implementation

`tlspyo` relies on the [Twisted](https://twisted.org) framework regarding [TLS](https://en.wikipedia.org/wiki/Transport_Layer_Security) implementation and network management.

### Important to know

:warning: Objects transferred by `tlspyo` are serialized with `pickle` by default, so that you can transfer most python objects easily.

If you use `tlspyo` (or any similar approach) on a machine that is visible from a public network, failing to follow the security instructions provided thereafter could make you vulnerable to [dangerous exploits](https://davidhamann.de/2020/04/05/exploiting-python-pickle/).
This is because unpickling untrusted pickled objects (i.e., pickled objects created by a malicious user) can lead to arbitrary code execution on your machine.

To prevent this from happening, `tlspyo` provides two interdependent layers of security:
* `Endpoints` authenticate your `Relay` via [TLS](https://en.wikipedia.org/wiki/Transport_Layer_Security), which must use [your own secret key and public certificate](#tls-setup).
This ensures your `Endpoints` are indeed talking to your `Relay` and not to some [man-in-the-middle](https://en.wikipedia.org/wiki/Man-in-the-middle_attack), **provided you keep your secret key secure**.
This also prevents anyone else from [eavesdropping](https://en.wikipedia.org/wiki/Eavesdropping) thanks to TLS encryption.
* Every object transfer is protected by a password known to both the `Relay` and the `Endpoints` (the `password` argument).
No object is deserialized without verification of the password.
This ensures that anyone posing as an endpoint will never be able to send undesired objects through your relay **unless they know your password**.

If a malicious user successfully posed as your `Relay`, your `Endpoint` would send them messages that they could decrypt, including your password (this is prevented by TLS when using your own secret key and public certificate).
If they successfully posed as your `Endpoint` they could send malicious pickled objects to your `Relay` (this is prevented by them not knowing your password).

In a nutshell, you want your password to be as strong as possible, and your TLS secret key to be kept... well, secret :lock:

## External links

`tlspyo` is an open-source project hosted at [Polytechnique Montreal - MISTlab](https://mistlab.ca).
We use it in various projects, ranging from parallel [meta-learning](https://github.com/Portiloop) to data transfer between multiple [learning robots](https://github.com/trackmania-rl/tmrl).

`tlspyo` relies on [Twisted](https://twisted.org) to manage network robustness and security.

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