import os
import sys

from argparse import ArgumentParser

from cogen.core.coroutines import coro
from cogen.core.schedulers import Scheduler
from cogen.core.sockets import ConnectionClosed, Socket

from durus.logger import log
from durus.file_storage import FileStorage
from durus.storage_server import DEFAULT_GCBYTES
from durus.utils import int4_to_str


DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 22972

PROTOCOL = int4_to_str(20001)


def database_names(path):
    """Return a list of all Durus database names in a given path."""
    for filename in os.listdir(path):
        name, ext = os.path.splitext(filename)
        if ext == '.durus':
            yield name


class Server(object):

    handlers = {
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
        self.path = path
        self.scheduler = scheduler
        self.storage_class = storage_class
        self.host = host
        self.port = port
        # Database name -> open storage mapping.  By default all are closed.
        self.databases = dict((name, None) for name in database_names(path))

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
        client = client_socket.makefile()
        while not client.closed:
            try:
                command = yield client.read(1)
            except ConnectionClosed:
                break
            else:
                if command in self.handlers:
                    handler_name = self.handlers[command]
                    handler = getattr(self, handler_name)
                    yield handler(client)
                elif command in self.db_handlers:
                    handler_name = self.handlers[command]
                    handler = getattr(self, handler_name)
                    db_name = 'DUMMY' # XXX
                    yield handler(client, db_name)
        log(20, 'Connection closed.')

    # Server handlers.

    @coro
    def handle_quit(self, client):
        log(20, 'Quit')
        for storage in self.databases.values():
            if storage is not None:
                storage.close()
        self.scheduler.shutdown()

    @coro
    def handle_version(self, client):
        log(20, 'Version')
        yield client.write(PROTOCOL)
        yield client.flush()

    @coro
    def handle_disconnect(self, client):
        log(20, 'Disconnect')
        yield client.close()

    # Database handlers.

    @coro
    def handle_bulk_read(self, client, db_name):
        pass

    @coro
    def handle_commit(self, client, db_name):
        pass

    @coro
    def handle_destroy(self, client, db_name):
        pass

    @coro
    def handle_load(self, client, db_name):
        pass

    @coro
    def handle_new_oids(self, client, db_name):
        pass

    @coro
    def handle_new_oid(self, client, db_name):
        pass

    @coro
    def handle_open(self, client, db_name):
        pass

    @coro
    def handle_pack(self, client, db_name):
        pass

    @coro
    def handle_sync(self, client, db_name):
        pass

    @coro
    def handle_close(self, client, db_name):
        pass


def main():
    parser = ArgumentParser(description='Serve Durus databases via TCP/IP')
    parser.add_argument(
        'path', type=str,
        help='Path containing databases.')
    parser.add_argument(
        '--host', type=str, default=DEFAULT_HOST,
        help='Interface to serve on.')
    parser.add_argument(
        '--port', type=str, default=DEFAULT_PORT,
        help='Port to serve on.')
    # parser.add_argument(
    #     '--gcbytes', type=int, default=DEFAULT_GCBYTES,
    #     help='Number of bytes to transfer between packing.')
    args = parser.parse_args()
    scheduler = Scheduler()
    server = Server(
        scheduler=scheduler,
        path=args.path,
        host=args.host,
        port=args.port,
        )
    scheduler.add(server.dispatch)
    scheduler.run()


def main_database_names():
    parser = ArgumentParser(description='List Durus databases')
    parser.add_argument(
        'path', type=str,
        help='Path containing databases.')
    args = parser.parse_args()
    for name in database_names(args.path):
        print name
