"""
Runtime hook: redirect sys.stdout/sys.stderr to devnull when running
in windowed mode (--noconsole) to prevent NoneType.write crashes.
"""
import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
