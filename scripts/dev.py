"""Start both local services and stop them together on Ctrl+C."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root=Path(__file__).resolve().parents[1]
children=[]
try:
    children.append(subprocess.Popen([str(root/'.venv/bin/python'),'-m','backend'],cwd=root,start_new_session=True))
    children.append(subprocess.Popen(['npm','run','dev'],cwd=root,start_new_session=True))
    while all(child.poll() is None for child in children):
        time.sleep(.5)
except KeyboardInterrupt:
    pass
finally:
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
    for child in children:
        child.wait()
