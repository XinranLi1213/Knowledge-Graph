from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os
os.chdir(Path(__file__).resolve().parents[1])
print('Local: http://127.0.0.1:8765', flush=True)
ThreadingHTTPServer(('127.0.0.1', 8765), SimpleHTTPRequestHandler).serve_forever()
