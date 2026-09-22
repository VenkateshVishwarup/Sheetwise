"""Isolated entry point; never inherits application secrets or calls AI services."""
import json
import sys
from .evaluation import _analyze

if __name__=='__main__':
    try:
        request=json.load(sys.stdin)
        result=_analyze(request['profile'],request['definition'],request['evaluate'])
    except ValueError as exc:
        result={'error':str(exc)}
    except Exception:
        result={'error':'This dataset could not be evaluated. Check the selected outcome and inputs.'}
    print(json.dumps(result,allow_nan=False))
