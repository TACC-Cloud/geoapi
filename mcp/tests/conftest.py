import os
import sys

# Make server.py (one level up) importable without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
