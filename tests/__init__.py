"""Ingest tests. From ingest/: python -m unittest discover -s tests"""

import os
import sys

_INGEST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _INGEST not in sys.path:
    sys.path.insert(0, _INGEST)
