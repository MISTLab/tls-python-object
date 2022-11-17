Command Line Interface (TLS credentials)
========================================

Once ``tlspyo`` is installed, you can generate TLS credentials via the command line.

*(Alternatively, you can achieve this programmatically using the tlspyo.credentials module.)*

Generate TLS credentials (Relay)
--------------------------------

Execute the following to generate TLS credentials on the machine that will host your ``Relay``:

.. code-block:: bash

   python -m tlspyo --generate

If you wish to customize your TLS certificate, you can instead do:

.. code-block:: bash

   python -m tlspyo --generate --custom

Broadcast TLS credentials (Relay)
---------------------------------

Once your TLS credentials have been generated, you can either retrieve the ``certificate.pem`` file manually, or broadcast it via TCP:

.. code-block:: bash

   python -m tlspyo --broadcast --port=<port>

Retrieve TLS credentials (Endpoints)
------------------------------------

On the machines that will host your ``Endpoints``, you can either retrieve your ``certificate.pem`` via TCP:

.. code-block:: bash

   python -m tlspyo --retrieve --ip=<ip> --port=<port>

Or manually copy it from the machine hosting your ``Relay`` to the folder displayed by:

.. code-block:: bash

   python -m tlspyo --credentials

You can now proceed to using the python API in a secure fashion.
