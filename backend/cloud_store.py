"""Private, append-only Blob persistence for stateless Vercel functions."""
import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from vercel.blob import BlobClient, BlobNotFoundError


class CloudStore:
    def __init__(self, root, client=None):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.client=client or BlobClient()

    def _read(self,path):
        try:
            result=self.client.get(path,access='private',use_cache=False,timeout=30)
        except BlobNotFoundError:
            raise KeyError('Not found.') from None
        if result is None:
            raise KeyError('Not found.')
        return json.loads(result.content)

    def _write(self,path,value):
        self.client.put(path,json.dumps(value,allow_nan=False).encode(),access='private',content_type='application/json',overwrite=False)

    def _paths(self,prefix):
        cursor=None
        while True:
            result=self.client.list_objects(prefix=prefix,limit=1000,cursor=cursor)
            yield from (b.pathname for b in result.blobs)
            if not result.has_more:
                break
            cursor=result.cursor

    def dataset(self,dataset_id):
        return self._read(f'profiles/{dataset_id}.json')

    def datasets(self):
        return sorted((self._read(path) for path in self._paths('profiles/')),key=lambda p:p['createdAt'],reverse=True)

    def save_dataset(self,profile):
        path=Path(profile['databasePath'])
        if path.stat().st_size>400*1024*1024:
            raise ValueError('The imported database is too large for this cloud workspace.')
        database=f'databases/{profile["id"]}/{uuid.uuid4()}.duckdb'
        self.client.upload_file(path,database,access='private',multipart=True,overwrite=False)
        saved={**profile,'databasePath':'blob:'+database}
        try:
            self._write(f'profiles/{profile["id"]}.json',saved)
        except Exception as exc:
            # A request may time out after the profile committed, or another importer may win.
            # Verify the commit before deciding this failed. Unreferenced immutable DB objects
            # can be cleaned up later; never delete a possibly committed database here.
            try:
                saved=self.dataset(profile['id'])
            except KeyError:
                raise exc
        path.unlink(missing_ok=True)
        return saved

    @contextmanager
    def materialize(self,profile):
        # Each execution owns its temporary file. Nothing depends on a warm instance.
        with TemporaryDirectory(dir=self.root) as directory:
            path=Path(directory)/'dataset.duckdb'
            self.client.download_file(profile['databasePath'].removeprefix('blob:'),path,access='private',timeout=60)
            yield {**profile,'databasePath':str(path)}

    def save_answer(self,dataset_id,answer):
        self._write(f'answers/{dataset_id}/{answer["id"]}.json',answer)

    def answers(self,dataset_id,pinned=False):
        values=[self._read(path) for path in self._paths(f'answers/{dataset_id}/')]
        pins={}
        # Unique event objects avoid overwriting a cached object or losing concurrent saves.
        for path in sorted(self._paths(f'pins/{dataset_id}/')):
            event=self._read(path)
            pins[event['answerId']]=event['pinned']
        return sorted(({**a,'pinned':pins.get(a['id'],False)} for a in values if not pinned or pins.get(a['id'],False)),key=lambda a:a['createdAt'])

    def pin(self,dataset_id,answer_id,pinned):
        self._read(f'answers/{dataset_id}/{answer_id}.json')
        self._write(f'pins/{dataset_id}/{time.time_ns():020d}-{uuid.uuid4()}.json',{'answerId':answer_id,'pinned':pinned})

    def save_evaluation(self,dataset_id,result):
        self._write(f'evaluations/{dataset_id}/{result["createdAt"]}--{result["id"]}.json',result)

    def evaluations(self,dataset_id):
        paths=sorted(self._paths(f'evaluations/{dataset_id}/'),reverse=True)[:20]
        return [self._read(path) for path in paths]
