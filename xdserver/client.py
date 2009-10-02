__all__ = [
    'Client',
    'ClientStorage',
    ]

import sys

from argparse import ArgumentParser

from durus.connection import Connection
from durus.error import (
    ConflictError, DurusKeyError, ProtocolError, ReadConflictError)
from durus.serialize import split_oids
from durus.storage import Storage
from durus.storage_server import (
    SocketAddress,
    STATUS_OKAY, STATUS_KEYERROR, STATUS_INVALID,
    )
from durus.utils import (
    iteritems,
    as_bytes, join_bytes,
    int4_to_str,
    read, read_int4, write, write_all, write_int4, write_int4_str,
    )

from xdserver.server import DEFAULT_HOST, DEFAULT_PORT, PROTOCOL


class Client(object):
    """Connects to a xdserver server.

    :param host: Host name or IP address of server to connect to.
    :type host: string
    :param port: Port server is listening on.
    :type port: integer
    """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.address = SocketAddress.new((host, port))
        self.socket = self.address.get_connected_socket()
        assert self.socket, 'Could not connect to %s' % (self.address)
        if self.server_protocol() != PROTOCOL:
            raise ProtocolError("Protocol version mismatch.")

    # Server commands.

    def disconnect(self):
        """Disconnect from the server."""
        if self.socket is not None:
            write(self.socket, '.')
            self.socket.close()
            self.socket = None

    def list_all(self):
        """List all databases available on the server.

        :rtype: list of strings
        """
        write(self.socket, 'A')
        return list(self._enumerate_database_names())

    def list_open(self):
        """List open databases on server.

        :rtype: List of strings
        """
        write(self.socket, 'E')
        return list(self._enumerate_database_names())

    def _enumerate_database_names(self):
        count = read_int4(self.socket)
        while count > 0:
            count -= 1
            length = read_int4(self.socket)
            database_name = read(self.socket, length)
            yield database_name

    def quit(self):
        """Shut down the server process and disconnect.

        .. todo::

           Determine if it is necessary to keep "quit" in the protocol
           or if a server should only be shut down by process control
           on the system that the server is running on.
        """
        write(self.socket, 'Q')
        self.disconnect()

    def server_protocol(self):
        """Get the protocol used by the server.

        :rtype: 4-byte string
        """
        write(self.socket, 'V')
        return read(self.socket, 4)

    # Database commands.

    def _write_database_name(self, db_name):
        write_int4(self.socket, len(db_name))
        write(self.socket, db_name)

    def close(self, db_name):
        """Close the named database.

        :param db_name: Name of database to close.
        :ptype db_name: string
        """
        write(self.socket, 'X')
        self._write_database_name(db_name)

    def destroy(self, db_name):
        """Destroy the named database.

        :param db_name: Name of database to destroy.
        :ptype db_name: string

        .. note::

           The database will not be destroyed if it is currently open.

        .. warning::

           This will permanently delete the file containing the
           database on the server.
        """
        write(self.socket, 'D')
        self._write_database_name(db_name)

    def open(self, db_name):
        """Open the named database.

        :param db_name: Name of database to open.
        :ptype db_name: string
        """
        write(self.socket, 'O')
        self._write_database_name(db_name)

    def storage(self, db_name):
        """Return a Durus storage object for the named database.

        The database is opened on the server if it was not open
        already.

        :param db_name: Name of database to return storage object for.
        :ptype db_name: string
        :rtype: :class:`ClientStorage`
        """
        self.open(db_name)
        return ClientStorage(self, db_name)


class ClientStorage(Storage):
    """Durus storage for a xdserver database.

    Follows the :class:`durus.storage.Storage` API.

    Please use :meth:`~Client.storage` to create
    storage instances, rather than creating instances of this class
    directly.
    """

    def __init__(self, client, db_name):
        self.client = client
        self.db_name = int4_to_str(len(db_name)) + db_name
        self.socket = client.socket
        self.oid_pool = []
        self.oid_pool_size = 32
        self.begin()

    def _get_load_response(self, oid):
        status = read(self.socket, 1)
        if status == STATUS_OKAY:
            pass
        elif status == STATUS_INVALID:
            raise ReadConflictError([oid])
        elif status == STATUS_KEYERROR:
            raise DurusKeyError(oid)
        else:
            raise ProtocolError('status=%r, oid=%r' % (status, oid))
        n = read_int4(self.socket)
        record = read(self.socket, n)
        return record

    def _send_command(self, command):
        write_all(self.socket, command, self.db_name)

    def begin(self):
        self.records = {}
        self.transaction_new_oids = []

    def bulk_load(self, oids):
        oid_str = join_bytes(oids)
        num_oids, remainder = divmod(len(oid_str), 8)
        assert remainder == 0, remainder
        self._send_command('B')
        write_all(self.socket, int4_to_str(num_oids), oid_str)
        records = [self._get_load_response(oid) for oid in oids]
        for record in records:
            yield record

    def close(self):
        # No-op on server side, but destroys this instance so that
        # it conforms to API.
        self.socket = None

    def end(self, handle_invalidations=None):
        self._send_command('C')
        n = read_int4(self.socket)
        oid_list = []
        if n != 0:
            packed_oids = read(self.socket, 8 * n)
            oid_list = split_oids(packed_oids)
            try:
                handle_invalidations(oid_list)
            except ConflictError:
                self.transaction_new_oids.reverse()
                self.oid_pool.extend(self.transaction_new_oids)
                assert len(self.oid_pool) == len(set(self.oid_pool))
                self.begin() # clear out records and transaction_new_oids
                write_int4(self.socket, 0)
                raise
        tdata = []
        for oid, record in iteritems(self.records):
            tdata.append(int4_to_str(8 + len(record)))
            tdata.append(as_bytes(oid))
            tdata.append(record)
        tdata = join_bytes(tdata)
        write_int4_str(self.socket, tdata)
        self.records.clear()
        if len(tdata) > 0:
            status = read(self.socket, 1)
            if status == STATUS_OKAY:
                pass
            elif status == STATUS_INVALID:
                raise WriteConflictError()
            else:
                raise ProtocolError(
                    'server returned invalid status %r' % status)

    def load(self, oid):
        self._send_command('L')
        write(self.socket, oid)
        return self._get_load_response(oid)

    def new_oid(self):
        if not self.oid_pool:
            batch = self.oid_pool_size
            self._send_command('M')
            write(self.socket, chr(batch))
            self.oid_pool = split_oids(read(self.socket, 8 * batch))
            self.oid_pool.reverse()
            assert len(self.oid_pool) == len(set(self.oid_pool))
        oid = self.oid_pool.pop()
        assert oid not in self.oid_pool
        self.transaction_new_oids.append(oid)
        return oid

    def pack(self):
        self._send_command('P')
        status = read(self.socket, 1)
        if status != STATUS_OKAY:
            raise ProtocolError('server returned invalid status %r' % status)

    def store(self, oid, record):
        assert len(oid) == 8
        assert oid not in self.records
        self.records[oid] = record

    def sync(self):
        self._send_command('S')
        n = read_int4(self.socket)
        if n == 0:
            packed_oids = ''
        else:
            packed_oids = read(self.socket, 8 * n)
        return split_oids(packed_oids)


def main():
    parser = ArgumentParser(
        description='Connect to Durus databases via TCP/IP')
    parser.add_argument(
        '--host', type=str, default=DEFAULT_HOST,
        help='Host to connect to.')
    parser.add_argument(
        '--port', type=int, default=DEFAULT_PORT,
        help='Port to connect to.')
    args = parser.parse_args()
    client = Client(args.host, args.port)
    locals = dict(
        __name__='xdclient-shell',
        Connection=Connection,
        client=client,
        )
    print 'xdserver shell'
    print '  Connection - durus.connection.Connection class'
    print '  client - xdserver.client.Client instance'
    # Clear sys.argv so shell doesn't get confused.
    sys.argv[1:] = []
    try:
        import IPython
    except ImportError:
        # Use built-in shell.
        import code
        code.interact(local=locals)
    else:
        shell = IPython.Shell.IPShell(user_ns=locals)
        shell.mainloop()
    client.disconnect()
