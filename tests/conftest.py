"""
Pytest bootstrap for the dspace_rest_client test-suite.

Ensures the in-tree ``dspace_rest_client`` package is importable when the tests
are run straight from a checkout (``pytest tests/``) without a prior
``pip install``. When the package *is* installed, inserting the source root at
the front of ``sys.path`` means the tests still exercise the working-tree copy,
which is the one we ship and vendor as a submodule.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
