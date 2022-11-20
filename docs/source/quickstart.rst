TLSPYO in 5 minutes
===================

*(Note: You can do everything on a single machine by using ip_server="127.0.0.1")*

On all your machines:
---------------------

* Install ``tlspyo`` (preferably using the same version of python everywhere):

.. code-block:: bash

   pip install tlspyo

On your "server" machine:
-------------------------

* If your other machines are not in the same network, route port 7776 to this machine.
* Generate TLS credentials and broadcast your public certificate via TCP (port 7776 is used by default):

.. code-block:: bash

   python -m tlspyo --generate --broadcast

On all your "client" machines:
------------------------------

* Retrieve your public TLS certificate (via TCP, using port 7776 by default; please replace <server ip> by the ip of the "server" machine):

.. code-block:: bash

   python -m tlspyo --retrieve ip=<server ip>

On your "server" machine:
-------------------------

* Close the TLS certificate broadcasting server (e.g., close the terminal).
* Create a ``tlspyo Relay`` in a python script (adapt and execute this script):

.. code-block:: python

   from tlspyo import Relay
   import time

   if __name__=="__main__":

       my_relay = Relay(
            port=6667,
            password="<password>",  # replace <password> by a strong password of your choice
            local_com_port=3001
       )
       while True:
           time.sleep(1.0)

On your "client" machines:
--------------------------

* Create a ``tlspyo Endpoint`` that sends and receive objects from a python script (adapt and execute this script):

.. code-block:: python

   from tlspyo import Endpoint
   import time

   if __name__=="__main__":

       free_port = 3002  # adapt this if you use several Endpoints on the same machine
       groups = ("<group1>", "<group2>", "<...>")  # use group names of your choice

       my_endpoint = Endpoint(
       ip_server='<ip server>', # replace <ip server> by the ip of your server machine
       port=6667,
       password="<password>",  # same password as the Relay
       groups=groups,
       local_com_port=free_port
       )

       target_groups = ("<group1>", "<...>")  # replace by group names of your choice
       my_object = f"This object is for groups {target_groups}"

       my_endpoint.send_object(obj=my_object, destination=target_groups)

       while True:
           received_list = my_endpoint.receive_all(blocking=True)
           print(f"I am an Endpoint of groups {groups}, I received {received_list}")

On your chair:
--------------

* Contemplatively watch your ``Endpoints`` transfer your python objects to each other via your ``Relay``.