__all__ = [
    'Server',
    ]

from datetime import datetime
import os
import sys

from argparse import ArgumentParser

from cogen.core.coroutines import coro
from cogen.core.schedulers import Scheduler
from cogen.core.sockets import ConnectionClosed, Socket, SocketError

from durus.error import ConflictError
from durus.logger import log, logger, is_logging
from durus.file_storage import FileStorage
from durus.serialize import extract_class_name, split_oids
from durus.storage_server import (
    DEFAULT_GCBYTES,
    STATUS_OKAY, STATUS_KEYERROR, STATUS_INVALID,
    ClientError,
    )
from durus.utils import (
    int4_to_str, int8_to_str, str_to_int4, str_to_int8,
    join_bytes,
    )


DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 22972

PROTOCOL = int4_to_str(20001)

EXTENSION = '.durus'


def database_names(path):
    """Return a list of all Durus database names in a given path."""
    for filename in os.listdir(path):
        name, ext = os.path.splitext(filename)
        if ext == EXTENSION:
            yield name


class ConnectedClient(object):

    def __init__(self, client_socket):
        f = self.f = client_socket.makefile()
        self.invalid = {}
        self.unused_oids = {}
        self.read = f.read
        self.write = f.write
        self.flush = f.flush
        self.close = f.close

    @property
    def closed(self):
        return self.f.closed


class Server(object):
    """Provides access to databases for xdserver clients.

    In most cases your code will not use this class directly.  Use
    :program:`xdserver` instead; see :doc:`server`.
    """

    handlers = {
        'A': 'handle_enumerate_all',
        'E': 'handle_enumerate_open',
        'Q': 'handle_quit',
        'V': 'handle_version',
        '.': 'handle_disconnect',
    }

    db_handlers = {
        'B': 'handle_bulk_read',
        'C': 'handle_commit',
        'D': 'handle_destroy',
        'L': 'handle_load',
        'M': 'handle_new_oids',
        'N': 'handle_new_oid',
        'O': 'handle_open',
        'P': 'handle_pack',
        'S': 'handle_sync',
        'X': 'handle_close',
    }

    def __init__(self, scheduler, path, storage_class=FileStorage,
                 host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.path = os.path.abspath(path)
        self.scheduler = scheduler
        self.storage_class = storage_class
        self.host = host
        self.port = port
        # Database name -> open storage mapping.  By default all are closed.
        self.clients = set()
        self.storages = {}

    @coro
    def dispatch(self):
        socket = Socket()
        address = (self.host, self.port)
        socket.bind(address)
        socket.listen(16)
        log(20, 'Listening on %s:%i' % address)
        while 1:
            client_socket, client_address = yield socket.accept()
            log(20, 'Connection from %s:%s' % client_address)
            self.scheduler.add(
                self.serve_to_client,
                args=(client_socket,),
                )

    @coro
    def serve_to_client(self, client_socket):
        client = ConnectedClient(client_socket)
        # Initialize per-storage state for the new client.
        client.invalid = dict(
            (db_name, set()) for db_name in self.storages)
        client.unused_oids = dict(
            (db_name, set()) for db_name in self.storages)
        self.clients.add(client)
        while not client.closed:
            try:
                command = yield client.read(1)
            except (ConnectionClosed, SocketError):
                break
            else:
                if command in self.handlers:
                    handler_name = self.handlers[command]
                    handler = getattr(self, handler_name)
                    yield handler(client)
                elif command in self.db_handlers:
                    handler_name = self.db_handlers[command]
                    handler = getattr(self, handler_name)
                    # Get database name.
                    name_length = str_to_int4((yield client.read(4)))
                    db_name = yield client.read(name_length)
                    yield handler(client, db_name)
                yield client.flush()
        log(20, 'Connection closed.')
        self.clients.remove(client)

    # Server handlers.

    @coro
    def handle_enumerate_all(self, client):
        # A
        log(20, 'Enumerate all')
        names = list(database_names(self.path))
        yield self._handle_enumerate_database_names(client, names)

    @coro
    def handle_enumerate_open(self, client):
        # E
        log(20, 'Enumerate open')
        names = self.storages.keys()
        yield self._handle_enumerate_database_names(client, names)

    @coro
    def _handle_enumerate_database_names(self, client, names):
        yield client.write(int4_to_str(len(names)))
        for name in names:
            yield client.write(int4_to_str(len(name)))
            yield client.write(name)

    @coro
    def handle_quit(self, client):
        # Q
        log(20, 'Quit')
        for storage in self.storages.values():
            if storage is not None:
                storage.close()
        self.scheduler.stop()

    @coro
    def handle_version(self, client):
        # V
        log(20, 'Version')
        yield client.write(PROTOCOL)

    @coro
    def handle_disconnect(self, client):
        # .
        log(20, 'Disconnect')
        yield client.close()

    # Database handlers.

    def _db_path(self, db_name):
        db_path = os.path.join(self.path, db_name + EXTENSION)
        db_path = os.path.abspath(db_path)
        if not db_path.startswith(self.path):
            raise RuntimeError('Malformed db name %s' % db_name)
        return db_path

    def _handle_invalidations(self, db_name, oids):
        for c in self.clients:
            c.invalid[db_name].update(oids)

    def _new_oids(self, client, db_name, storage, count):
        oids = []
        while len(oids) < count:
            oid = storage.new_oid()
            for c in self.clients:
                if oid in c.invalid[db_name]:
                    oid = None
                    break
            if oid is not None:
                oids.append(oid)
        client.unused_oids[db_name].update(oids)
        return oids

    def _report_load_record(self, storage):
        if storage.d_load_record and is_logging(5):
            log(5, '\n'.join('%8s: %s' % (value, key)
                             for key, value
                             in sorted(storage.d_load_record.items())))
            storage.d_load_record.clear()

    @coro
    def _send_load_response(self, client, db_name, storage, oid):
        if oid in client.invalid[db_name]:
            yield client.write(STATUS_INVALID)
        else:
            try:
                record = storage.load(oid)
            except KeyError:
                log(10, 'KeyError %s', str_to_int8(oid))
                yield client.write(STATUS_KEYERROR)
            except ReadConflictError:
                log(10, 'ReadConflictError %s', str_to_int8(oid))
                yield client.write(STATUS_INVALID)
            else:
                if is_logging(5):
                    class_name = extract_class_name(record)
                    if class_name in storage.d_load_record:
                        storage.d_load_record[class_name] += 1
                    else:
                        storage.d_load_record[class_name] = 1
                    log(4, 'Load %-7s %s', str_to_int8(oid), class_name)
                yield client.write(STATUS_OKAY)
                yield client.write(int4_to_str(len(record)))
                yield client.write(record)

    def _sync_storage(self, db_name, storage):
        self._handle_invalidations(db_name, storage.sync())

    @coro
    def handle_bulk_read(self, client, db_name):
        # B
        log(20, 'Bulk read %s' % db_name)
        storage = self.storages[db_name]
        number_of_oids = str_to_int4((yield client.read(4)))
        oid_str_len = 8 * number_of_oids
        oid_str = yield client.read(oid_str_len)
        oids = split_oids(oid_str)
        for oid in oids:
            yield self._send_load_response(client, db_name, storage, oid)

    @coro
    def handle_commit(self, client, db_name):
        # C
        log(20, 'Commit %s' % db_name)
        storage = self.storages[db_name]
        self._sync_storage(db_name, storage)
        invalid = client.invalid[db_name]
        yield client.write(int4_to_str(len(invalid)))
        yield client.write(join_bytes(invalid))
        yield client.flush()
        invalid.clear()
        tdata_len = str_to_int4((yield client.read(4)))
        if tdata_len == 0:
            # Client decided not to commit (e.g. conflict)
            return
        tdata = yield client.read(tdata_len)
        logging_debug = is_logging(10)
        logging_debug and log(10, 'Committing %s bytes', tdata_len)
        storage.begin()
        i = 0
        oids = []
        while i < tdata_len:
            rlen = str_to_int4(tdata[i:i+4])
            i += 4
            oid = tdata[i:i+8]
            record = tdata[i+8:i+rlen]
            i += rlen
            if logging_debug:
                class_name = extract_class_name(record)
                log(10, '  oid=%-6s rlen=%-6s %s',
                    str_to_int8(oid), rlen, class_name)
            storage.store(oid, record)
            oids.append(oid)
        assert i == tdata_len
        oid_set = set(oids)
        for c in self.clients:
            if c is not client:
                if oid_set.intersection(c.unused_oids[db_name]):
                    raise ClientError('invalid oid: %r' % oid)
        try:
            handle_invalidations = (
                lambda oids: self._handle_invalidations(db_name, oids))
            storage.end(handle_invalidations=handle_invalidations)
        except ConflictError:
            log(20, 'Conflict during commit')
            yield client.write(STATUS_INVALID)
        else:
            self._report_load_record(storage)
            log(20, 'Committed %3s objects %s bytes at %s',
                len(oids), tdata_len, datetime.now())
            yield client.write(STATUS_OKAY)
            client.unused_oids[db_name] -= oid_set
            for c in self.clients:
                if c is not client:
                    c.invalid[db_name].update(oids)
            storage.d_bytes_since_pack += tdata_len + 8

    @coro
    def handle_destroy(self, client, db_name):
        # D
        log(20, 'Destroy %s' % db_name)
        if db_name in self.storages:
            # Do nothing if it's still in use.
            pass
        else:
            db_path = self._db_path(db_name)
            os.unlink(db_path)

    @coro
    def handle_load(self, client, db_name):
        # L
        log(20, 'Load %s' % db_name)
        storage = self.storages[db_name]
        oid = yield client.read(8)
        yield self._send_load_response(client, db_name, storage, oid)

    @coro
    def handle_new_oids(self, client, db_name):
        # M
        log(20, 'New OIDs %s' % db_name)
        storage = self.storages[db_name]
        count = ord((yield client.read(1)))
        log(10, 'oids: %s', count)
        yield client.write(
            join_bytes(self._new_oids(client, db_name, storage, count)))

    @coro
    def handle_new_oid(self, client, db_name):
        # N
        log(20, 'New OID %s' % db_name)
        storage = self.storages[db_name]
        yield client.write(self._new_oids(client, db_name, storage, 1)[0])

    @coro
    def handle_open(self, client, db_name):
        # O
        log(20, 'Open %s' % db_name)
        if db_name not in self.storages:
            db_path = self._db_path(db_name)
            storage = self.storage_class(db_path)
            storage.d_bytes_since_pack = 0
            storage.d_load_record = {}
            storage.d_packer = None
            self.storages[db_name] = storage
            # Initialize per-storage state for each client.
            for c in self.clients:
                c.invalid[db_name] = set()
                c.unused_oids[db_name] = set()

    @coro
    def handle_pack(self, client, db_name):
        # P
        log(20, 'Pack %s' % db_name)
        storage = self.storages[db_name]
        if storage.d_packer is None:
            log(20, 'Pack started at %s' % datetime.now())
            storage.d_packer = storage.get_packer()
            if storage.d_packer is None:
                log(20, 'Cannot iteratively pack, performing full pack.')
                storage.pack()
                log(20, 'Pack completed at %s' % datetime.now())
        else:
            log(20, 'Pack already in progress at %s' % datetime.now())
        yield client.write(STATUS_OKAY)

    @coro
    def handle_sync(self, client, db_name):
        # S
        log(20, 'Sync %s' % db_name)
        storage = self.storages[db_name]
        self._report_load_record(storage)
        self._sync_storage(db_name, storage)
        invalid = client.invalid[db_name]
        log(8, 'Sync %s', len(invalid))
        yield client.write(int4_to_str(len(invalid)))
        yield client.write(join_bytes(invalid))
        invalid.clear()

    @coro
    def handle_close(self, client, db_name):
        # X
        log(20, 'Close %s' % db_name)
        if db_name in self.storages:
            self.storages[db_name].close()
            del self.storages[db_name]
            # Remove per-storage state for each client.
            for c in self.clients:
                del c.invalid[db_name]
                del c.unused_oids[db_name]


def main():
    parser = ArgumentParser(description='Serve Durus databases via TCP/IP')
    parser.add_argument(
        'path', type=str,
        help='Path containing databases.')
    parser.add_argument(
        '--host', type=str, default=DEFAULT_HOST,
        help='Interface to serve on.')
    parser.add_argument(
        '--port', type=int, default=DEFAULT_PORT,
        help='Port to serve on.')
    # parser.add_argument(
    #     '--gcbytes', type=int, default=DEFAULT_GCBYTES,
    #     help='Number of bytes to transfer between packing.')
    parser.add_argument(
        '--loglevel', type=int, default=20,
        help='Logging level.')
    args = parser.parse_args()
    logger.setLevel(args.loglevel)
    scheduler = Scheduler()
    server = Server(
        scheduler=scheduler,
        path=args.path,
        host=args.host,
        port=args.port,
        )
    scheduler.add(server.dispatch)
    scheduler.run()
