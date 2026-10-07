"""
Import-time and public-surface contract of the package.

``DSpaceClient`` reads its defaults (DSPACE_API_ENDPOINT, PROXY_URL, ...) from
the environment when ``dspace_rest_client.client`` is first imported, so the
package must not import it as a side effect of importing anything else.
"""
import os
import subprocess
import sys
import unittest

import _helpers  # noqa: F401
from dspace_rest_client import client

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(code: str) -> str:
    return subprocess.run([sys.executable, "-c", code], cwd=_ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


class TestLazyClientImport(unittest.TestCase):

    def test_importing_models_does_not_import_client(self):
        out = _run("import sys, dspace_rest_client.models; "
                   "print('dspace_rest_client.client' in sys.modules)")
        self.assertEqual(out, "False")

    def test_env_set_after_models_import_reaches_client_defaults(self):
        out = _run("import os, dspace_rest_client.models; "
                   "os.environ['DSPACE_API_ENDPOINT'] = 'http://late/server/api'; "
                   "from dspace_rest_client.client import DSpaceClient; "
                   "print(DSpaceClient.API_ENDPOINT)")
        self.assertEqual(out, "http://late/server/api")

    def test_client_still_reachable_from_package(self):
        import dspace_rest_client
        self.assertIs(dspace_rest_client.DSpaceClient, client.DSpaceClient)


class TestClientModuleReExports(unittest.TestCase):

    def test_models_previously_star_imported_into_client_stay_importable(self):
        for name in ("DSpaceObject", "HALResource", "ExternalDataObject",
                     "SimpleDSpaceObject", "Community", "Collection", "Item",
                     "Bundle", "Bitstream", "User", "Group", "ResourcePolicy"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(client, name))


if __name__ == "__main__":
    unittest.main()
