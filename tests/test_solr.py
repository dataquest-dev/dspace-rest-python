import unittest

import _helpers  # noqa: F401
from _helpers import make_client


class TestSolr(unittest.TestCase):

    def test_query_without_solr_extra_has_actionable_error(self):
        client = make_client()
        client.solr = None

        with self.assertRaisesRegex(RuntimeError, r"dspace-rest-client\[solr\]"):
            client.solr_query("*:*", rows=10)


if __name__ == "__main__":
    unittest.main()