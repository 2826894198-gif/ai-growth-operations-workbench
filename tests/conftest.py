import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
WORKER = os.path.join(ROOT, "browser-worker")

for path in (BACKEND, WORKER):
    if path not in sys.path:
        sys.path.insert(0, path)
