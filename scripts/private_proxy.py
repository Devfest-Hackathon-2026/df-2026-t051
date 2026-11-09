"""Loopback-only proxy for an IAM-private Cloud Run verification deployment.

Tokens stay in server memory; neither tokens nor response bodies are logged.
"""
import argparse
import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--gcloud', required=True)
parser.add_argument('--port', type=int, default=8085)
args = parser.parse_args()
parsed = urlsplit(args.url)
if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.run.app') or parsed.path not in {'','/'}:
    raise SystemExit('Expected an HTTPS Cloud Run service URL')

cached = None


def token():
    global cached
    if not cached or cached[1] < time.time() + 120:
        result = subprocess.run([args.gcloud, 'auth', 'print-identity-token'], capture_output=True, text=True, check=True)
        value = result.stdout.strip()
        import base64
        claims = json.loads(base64.urlsafe_b64decode(value.split('.')[1] + '=='))
        cached = (value, claims['exp'])
    return cached[0]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def forward(self):
        if not self.path.startswith('/') or self.path.startswith('//'):
            self.send_error(400)
            return
        if self.headers.get('Host') not in {f'127.0.0.1:{args.port}', f'localhost:{args.port}'}:
            self.send_error(403)
            return
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}'}:
            self.send_error(403)
            return
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.send_error(403)
            return
        length = int(self.headers.get('Content-Length', 0))
        if length > 6 * 1024 * 1024:
            self.send_error(413)
            return
        headers = {'X-Serverless-Authorization': f'Bearer {token()}', 'X-ChartBridge-Identity': token()}
        # Keep the Firebase bearer token intact. Platform IAM uses its own header.
        if self.headers.get('Authorization'):
            headers['Authorization']=self.headers['Authorization']
        if self.headers.get('Content-Type'):
            headers['Content-Type'] = self.headers['Content-Type']
        try:
            response = httpx.request(self.command, args.url.rstrip('/') + self.path,
                                     headers=headers, content=self.rfile.read(length), timeout=65)
        except Exception:
            self.send_error(502, 'Private service unavailable')
            return
        self.send_response(response.status_code)
        for name, value in response.headers.items():
            if name.lower() not in {'transfer-encoding','content-encoding','content-length','connection','server','date'}:
                self.send_header(name,value)
        self.send_header('Content-Length', str(len(response.content)))
        self.end_headers()
        self.wfile.write(response.content)

    do_GET = forward
    do_POST = forward
    do_PUT = forward


print(f'Private verification proxy: http://127.0.0.1:{args.port}', flush=True)
ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
