import unittest

import _helpers  # noqa: F401
import dspace_rest_client
from dspace_rest_client import models


class TestPublicApi(unittest.TestCase):

    def test_package_and_models_export_the_same_models(self):
        self.assertEqual(
            set(dspace_rest_client.__all__) - {"DSpaceClient"},
            set(models.__all__),
        )


if __name__ == "__main__":
    unittest.main()