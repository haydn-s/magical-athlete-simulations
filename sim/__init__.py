"""
Batch simulation harness for the Magical Athlete engine.

The engine (Basics, Events, Powers, Racers) lives as flat modules at the repo
root and is used as-is; nothing in this package changes racer mechanics.
"""
import os
import sys

# Make the root-level engine modules importable however this package is loaded.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
