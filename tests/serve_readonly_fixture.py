"""Isolated browser fixture with the packaged real results and no configured API."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.http_server import create_server
from agent.provider import Provider
if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        server=create_server(Path(__file__).resolve().parents[1],Path(tmp)/'readonly.sqlite3',0,Provider('rules'))
        print(f'http://127.0.0.1:{server.server_address[1]}',flush=True)
        try:server.serve_forever()
        finally:server.server_close();server.engine.close()
