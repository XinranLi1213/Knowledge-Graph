import json
import sqlite3
import threading
from contextlib import contextmanager
from .contracts import validate

class Store:
    def __init__(self,path):
        self.lock=threading.RLock()
        self.db=sqlite3.connect(str(path),check_same_thread=False,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS records(kind TEXT,id TEXT,revision INTEGER,payload TEXT,PRIMARY KEY(kind,id,revision)); CREATE TABLE IF NOT EXISTS pointers(key TEXT PRIMARY KEY,payload TEXT);')
    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:yield;self.db.execute('COMMIT')
            except BaseException:self.db.execute('ROLLBACK');raise
    def put(self,kind,id,value,revision=None):
        if kind in ('evaluation_changed','diagnostic_artifact','agent_run','conversation_turn'):validate(value)
        with self.lock:
            if revision is None:revision=self.db.execute('SELECT COALESCE(MAX(revision),0)+1 FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()[0]
            self.db.execute('INSERT INTO records VALUES(?,?,?,?)',(kind,id,revision,json.dumps(value,ensure_ascii=False,allow_nan=False)))
        return revision
    def get(self,kind,id,revision=None):
        with self.lock:
            row=self.db.execute('SELECT payload FROM records WHERE kind=? AND id=?'+(' AND revision=?' if revision is not None else ' ORDER BY revision DESC LIMIT 1'),(kind,id,revision) if revision is not None else (kind,id)).fetchone()
        return json.loads(row[0]) if row else None
    def all(self,kind):
        with self.lock:rows=self.db.execute('SELECT r.payload FROM records r JOIN (SELECT id,MAX(revision) revision FROM records WHERE kind=? GROUP BY id) m ON r.id=m.id AND r.revision=m.revision WHERE r.kind=? ORDER BY r.rowid',(kind,kind)).fetchall()
        return [json.loads(row[0]) for row in rows]
    def pointer(self,key,value=None):
        with self.lock:
            if value is not None:self.db.execute('INSERT INTO pointers VALUES(?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload',(key,json.dumps(value)));return value
            row=self.db.execute('SELECT payload FROM pointers WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def close(self):
        with self.lock:self.db.close()
