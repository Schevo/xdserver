Durus_ is an object database for Python.  It allows multiple clients
to operate on a single database via a wire protocol, and allows one
process at a time to directly access a database file.

.. _Durus: http://mems-exchange.org/software/durus/

xdserver is an extended server for Durus providing these enhancements:

- Serve multiple databases with one server process.  Operate on
  multiple databases with one connection.

- Asynchronous server, using cogen_ to offer platform-specific
  performance enhancements.

.. _cogen: http://code.google.com/p/cogen/
