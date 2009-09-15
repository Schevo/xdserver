import sys

from argparse import ArgumentParser

from durus.error import ProtocolError
from durus.storage_server import SocketAddress
from durus.utils import read, read_int4, write, write_all

from duruses.server import DEFAULT_HOST, DEFAULT_PORT, PROTOCOL


class Client(object):

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.address = SocketAddress.new((host, port))
        self.socket = self.address.get_connected_socket()
        assert self.socket, 'Could not connect to %s' % (self.address)
        if self.server_protocol() != PROTOCOL:
            raise ProtocolError("Protocol version mismatch.")

    def disconnect(self):
        if self.socket is not None:
            write(self.socket, '.')
            self.socket.close()
            self.socket = None

    def enumerate_all(self):
        write(self.socket, 'A')
        return list(self._enumerate_database_names())

    def enumerate_open(self):
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
        write(self.socket, 'Q')
        self.disconnect()

    def server_protocol(self):
        write_all(self.socket, 'V')
        return read(self.socket, 4)


def main():
    parser = ArgumentParser(
        description='Connect to Durus databases via TCP/IP')
    parser.add_argument(
        '--host', type=str, default=DEFAULT_HOST,
        help='Host to connect to.')
    parser.add_argument(
        '--port', type=str, default=DEFAULT_PORT,
        help='Port to connect to.')
    args = parser.parse_args()
    client = Client(args.host, args.port)
    locals = dict(
        __name__='duruses-client-shell',
        client=client,
        )
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
