import http.server
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from common.http_json import bounded_json_get, HTTPJSONError


class HTTPJSONTests(unittest.TestCase):
    def test_redirects_and_oversized_responses_are_not_consumed(self):
        paths = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                paths.append(self.path)
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/target')
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    try:
                        self.wfile.write(b' ' * (256 * 1024 + 1))
                    except OSError:
                        pass
            def log_message(self, *_):
                pass
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}'
                self.assertEqual(bounded_json_get(url + '/redirect', timeout=2), (302, None))
                self.assertEqual(paths, ['/redirect'])
                with self.assertRaises(HTTPJSONError):
                    bounded_json_get(url + '/large', timeout=2)
            finally:
                server.shutdown()
                thread.join()

    def test_entire_request_deadline_covers_dripping_headers_and_body(self):
        class Drip(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    if self.path == '/headers':
                        for byte in b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n':
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(.05)
                    else:
                        self.send_response(200)
                        self.send_header('Content-Length', '100')
                        self.end_headers()
                        for _ in range(100):
                            self.wfile.write(b' ')
                            self.wfile.flush()
                            time.sleep(.05)
                except OSError:
                    pass
            def log_message(self, *_):
                pass
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Drip) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for path in ('/headers', '/body'):
                    started = time.monotonic()
                    with self.assertRaises(HTTPJSONError):
                        bounded_json_get(f'http://127.0.0.1:{server.server_port}' + path, timeout=.25)
                    self.assertLess(time.monotonic() - started, 1.5)
            finally:
                server.shutdown()
                thread.join()

    def test_default_netrc_credentials_are_never_sent(self):
        received = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.headers.get('Authorization'))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')
            def log_message(self, *_):
                pass
        with tempfile.TemporaryDirectory() as directory:
            netrc = Path(directory) / 'netrc'
            netrc.write_text('default login private-user password private-password\n')
            with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    with patch.dict(os.environ, {'NETRC': str(netrc)}):
                        self.assertEqual(bounded_json_get(f'http://127.0.0.1:{server.server_port}', timeout=2), (200, {}))
                    self.assertEqual(received, [None])
                finally:
                    server.shutdown()
                    thread.join()
