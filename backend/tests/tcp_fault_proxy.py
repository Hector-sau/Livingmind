"""Local test transport: reset existing connections and reject new ones until healed."""
import select
import socket
import socketserver
import threading

from sqlalchemy.engine import make_url


class TcpFaultProxy(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def __init__(self, database_url):
        target = make_url(database_url)
        if target.get_backend_name() != "postgresql" or target.host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Use only the explicitly configured local disposable PostgreSQL")
        self.upstream = (target.host, target.port or 5432)
        self._cut = threading.Event()
        self._mutex = threading.Lock()
        self._connections = set()
        super().__init__(("127.0.0.1", 0), _Handler)
        # Bound connection establishment; do not modify server durability or timeout settings.
        self.url = target.set(host="127.0.0.1", port=self.server_address[1]).update_query_dict(
            {"connect_timeout": "2"}).render_as_string(hide_password=False)
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def cut(self):
        with self._mutex:
            self._cut.set()
            for connection in tuple(self._connections):
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()

    def heal(self):
        self._cut.clear()

    def close(self):
        self.cut()
        self.shutdown()
        self.server_close()
        self._thread.join(3)


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        peers = {}
        try:
            with self.server._mutex:
                if self.server._cut.is_set():
                    return
                upstream = socket.create_connection(self.server.upstream, timeout=2)
                peers = {self.request: upstream, upstream: self.request}
                self.server._connections.update(peers)
            while not self.server._cut.is_set():
                ready, _, _ = select.select(list(peers), [], [], .05)
                for source in ready:
                    data = source.recv(65536)
                    if not data:
                        return
                    peers[source].sendall(data)
        except (OSError, ValueError):
            pass  # Socket shutdown is the deliberate fault, including an in-use pooled connection.
        finally:
            with self.server._mutex:
                self.server._connections.difference_update(peers)
            for connection in peers:
                connection.close()
