Durus_ is an object database for Python.  It allows multiple
clients to operate on a single database via a wire protocol, in
addition to allowing one process at a time to directly access
a database file.

Duruses implements an extended server with these enhancements:

- Serve multiple databases with one server process.  Operate on
  multiple databases with one connection.

- Asynchronous server, using cogen_ to offer platform-specific
  performance enhancements.

A `development version`_ is available.

.. _Durus: http://mems-exchange.org/software/durus/

.. _development version:
   http://github.com/11craft/duruses/zipball/master#egg=duruses-dev
