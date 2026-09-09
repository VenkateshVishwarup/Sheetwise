"""Credential-free subprocess entry point; never starts the HTTP server."""
import json
import sys
from .query import _worker


class Output:
    def send(self,value):
        sys.stdout.write(json.dumps(value,allow_nan=False))
        sys.stdout.flush()

    def close(self):
        pass


if __name__=='__main__':
    job=json.load(sys.stdin)
    _worker(job['databasePath'],job['keys'],job['sql'],Output())
