"""Workspace metadata is separate from immutable dataset databases."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    @contextmanager
    def materialize(self,profile):
        yield profile

    def __init__(self, root):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path=self.root/'workspace.sqlite'
        with self.connect() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS evaluations (id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS evaluation_dataset ON evaluations(dataset_id, created_at);
                CREATE TABLE IF NOT EXISTS ai_insights (id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ai_insight_dataset ON ai_insights(dataset_id, created_at);
                CREATE TABLE IF NOT EXISTS datasets (id TEXT PRIMARY KEY, profile TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS answers (id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, answer TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS answer_dataset ON answers(dataset_id, created_at);
            ''')

    def connect(self):
        return sqlite3.connect(self.path,timeout=10)

    def save_dataset(self, profile):
        with self.connect() as con:
            con.execute('INSERT INTO datasets VALUES (?,?)',(profile['id'],json.dumps(profile,allow_nan=False)))

    def dataset(self, dataset_id):
        with self.connect() as con:
            row=con.execute('SELECT profile FROM datasets WHERE id=?',(dataset_id,)).fetchone()
        if not row:
            raise KeyError('Dataset not found.')
        return json.loads(row[0])

    def datasets(self):
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute('SELECT profile FROM datasets ORDER BY rowid DESC')]

    def delete_dataset(self, dataset_id):
        profile=self.dataset(dataset_id)
        database=Path(profile['databasePath'])
        # Files go first: if removing them fails, the dataset stays listed and can be deleted again.
        for path in (database, Path(f'{database}.wal')):
            path.unlink(missing_ok=True)
        with self.connect() as con:
            for table in ('answers','evaluations','ai_insights'):
                con.execute(f'DELETE FROM {table} WHERE dataset_id=?',(dataset_id,))
            con.execute('DELETE FROM datasets WHERE id=?',(dataset_id,))

    def save_answer(self, dataset_id, answer):
        with self.connect() as con:
            con.execute('INSERT INTO answers VALUES (?,?,?,?,?)',(answer['id'],dataset_id,json.dumps(answer,allow_nan=False),0,answer['createdAt']))

    def answers(self, dataset_id, pinned=False):
        with self.connect() as con:
            rows=con.execute('SELECT answer,pinned FROM answers WHERE dataset_id=?'+(' AND pinned=1' if pinned else '')+' ORDER BY created_at',(dataset_id,)).fetchall()
        return [{**json.loads(row[0]),'pinned':bool(row[1])} for row in rows]

    def pin(self,dataset_id,answer_id,pinned):
        with self.connect() as con:
            count=con.execute('UPDATE answers SET pinned=? WHERE id=? AND dataset_id=?',(int(pinned),answer_id,dataset_id)).rowcount
        if not count:
            raise KeyError('Answer not found.')

    def save_evaluation(self,dataset_id,result):
        with self.connect() as con:
            con.execute('INSERT INTO evaluations VALUES (?,?,?,?)',(result['id'],dataset_id,json.dumps(result,allow_nan=False),result['createdAt']))

    def evaluations(self,dataset_id):
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute('SELECT result FROM evaluations WHERE dataset_id=? ORDER BY created_at DESC LIMIT 20',(dataset_id,))]

    def save_ai_insights(self,dataset_id,result):
        with self.connect() as con:
            con.execute('INSERT INTO ai_insights VALUES (?,?,?,?)',(result['id'],dataset_id,json.dumps(result,allow_nan=False),result['createdAt']))

    def ai_insights(self,dataset_id):
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute('SELECT result FROM ai_insights WHERE dataset_id=? ORDER BY created_at DESC LIMIT 5',(dataset_id,))]
