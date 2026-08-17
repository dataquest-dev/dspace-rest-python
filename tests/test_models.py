"""
Model construction / accessor contract.

This repo builds these model objects straight from cached or live API JSON and
reads a fixed set of attributes off them (``.uuid``, ``.name``, ``.metadata``,
``.sizeBytes``, ``.checkSum``, ``ResourcePolicy.groupUUID`` ...). If a rename or
a parsing change in the library dropped one of those, the audit/export/sync
tooling would break - these tests pin the shape.
"""
import unittest

import _helpers  # noqa: F401  (bootstraps sys.path for direct runs)
from dspace_rest_client.models import (
    Item, Community, Collection, Bundle, Bitstream, ResourcePolicy)


class TestItem(unittest.TestCase):

    def test_core_fields_from_api_resource(self):
        it = Item({
            "uuid": "u1", "name": "Thesis", "type": "item",
            "metadata": {"dc.title": [{"value": "Thesis"}]},
            "_links": {"self": {"href": "http://x/items/u1"}},
        })
        self.assertEqual(it.uuid, "u1")
        self.assertEqual(it.name, "Thesis")
        self.assertEqual(it.type, "item")
        self.assertEqual(it.metadata["dc.title"][0]["value"], "Thesis")
        self.assertEqual(it.links["self"]["href"], "http://x/items/u1")

    def test_type_is_item_even_without_explicit_type(self):
        # ingest.dspace_be.create_item builds Item(dict) from a hand-made dict
        # that has no "type" key; the class must still self-identify as an item.
        it = Item({"name": "n", "metadata": {}})
        self.assertEqual(it.type, "item")

    def test_as_dict_carries_item_flags(self):
        it = Item({"uuid": "u1", "name": "N", "metadata": {},
                   "inArchive": True, "discoverable": True, "withdrawn": False})
        d = it.as_dict()
        self.assertEqual(d["uuid"], "u1")
        self.assertEqual(d["type"], "item")
        self.assertEqual(
            (d["inArchive"], d["discoverable"], d["withdrawn"]),
            (True, True, False))


class TestCommunityCollection(unittest.TestCase):

    def test_community_fields_and_links(self):
        com = Community({
            "uuid": "c1", "name": "Faculty", "type": "community",
            "_links": {"collections": {"href": "http://x/communities/c1/collections"}},
        })
        self.assertEqual(com.uuid, "c1")
        self.assertEqual(com.name, "Faculty")
        self.assertEqual(com.type, "community")
        self.assertEqual(com.links["collections"]["href"],
                         "http://x/communities/c1/collections")

    def test_collection_fields_including_handle(self):
        col = Collection({"uuid": "col1", "name": "Theses",
                          "handle": "123456789/1", "type": "collection"})
        self.assertEqual(col.uuid, "col1")
        self.assertEqual(col.name, "Theses")
        self.assertEqual(col.handle, "123456789/1")
        self.assertEqual(col.type, "collection")


class TestBundleBitstream(unittest.TestCase):

    def test_bundle_fields_and_bitstreams_link(self):
        # get_bitstreams(bundle=...) prefers this embedded link over a manually
        # constructed URL, so it is part of the contract.
        b = Bundle({"uuid": "b1", "name": "ORIGINAL", "type": "bundle",
                    "metadata": {"dc.title": [{"value": "ORIGINAL"}]},
                    "_links": {"bitstreams": {"href": "http://x/bundles/b1/bitstreams"}}})
        self.assertEqual((b.uuid, b.name, b.type), ("b1", "ORIGINAL", "bundle"))
        # .metadata is parsed from the response (unlike .type, a class constant)
        # and is serialised by export/_dspace.py:323, so pin it.
        self.assertEqual(b.metadata, {"dc.title": [{"value": "ORIGINAL"}]})
        self.assertEqual(b.links["bitstreams"]["href"],
                         "http://x/bundles/b1/bitstreams")

    def test_bitstream_file_fields(self):
        # export/_dspace serialises exactly these attributes per bitstream.
        b = Bitstream({"uuid": "s1", "name": "f.pdf", "type": "bitstream",
                       "metadata": {"dc.title": [{"value": "f.pdf"}]},
                       "sizeBytes": 2048, "sequenceId": 3,
                       "checkSum": {"checkSumAlgorithm": "MD5", "value": "deadbeef"}})
        self.assertEqual(b.uuid, "s1")
        self.assertEqual(b.name, "f.pdf")
        self.assertEqual(b.sizeBytes, 2048)
        self.assertEqual(b.sequenceId, 3)
        self.assertEqual(b.checkSum["value"], "deadbeef")
        # the checksum verifier compares checkSumAlgorithm == "MD5"
        # (reposync/_files.py:187-189); .metadata is serialised by the exporter.
        self.assertEqual(b.checkSum["checkSumAlgorithm"], "MD5")
        self.assertEqual(b.metadata, {"dc.title": [{"value": "f.pdf"}]})
        d = b.as_dict()
        self.assertEqual(d["sizeBytes"], 2048)
        self.assertEqual(d["checkSum"]["value"], "deadbeef")
        self.assertEqual(d["sequenceId"], 3)

    def test_bitstream_from_none_does_not_crash(self):
        # some cache/None paths construct Bitstream(None); it must not raise the
        # way it used to on the membership checks in __init__.
        b = Bitstream(None)
        self.assertEqual(b.type, "bitstream")
        self.assertIsNone(b.uuid)


class TestResourcePolicy(unittest.TestCase):

    def test_direct_cached_format(self):
        # the shape produced by ResourcePolicy.as_dict() and re-read from cache
        rp = ResourcePolicy({"id": 5, "action": "READ", "groupName": "Anonymous",
                             "groupUUID": "g1", "startDate": "2028-01-01",
                             "endDate": None})
        self.assertEqual(rp.id, 5)
        self.assertEqual(rp.action, "READ")
        self.assertEqual(rp.groupName, "Anonymous")
        self.assertEqual(rp.groupUUID, "g1")
        self.assertEqual(rp.startDate, "2028-01-01")
        self.assertIsNone(rp.endDate)

    def test_live_api_embedded_group_format(self):
        # This is what /authz/resourcepolicies actually returns; files_access
        # relies on groupName/groupUUID being lifted out of _embedded.group.
        rp = ResourcePolicy({"id": 9, "action": "READ", "startDate": "2028-05-19",
                             "_embedded": {"group": {"name": "Anonymous",
                                                     "uuid": "anon-uuid"}}})
        self.assertEqual(rp.groupName, "Anonymous")
        self.assertEqual(rp.groupUUID, "anon-uuid")

    def test_as_dict_roundtrip_keeps_group_and_action(self):
        rp = ResourcePolicy({"id": 7, "action": "READ",
                             "_embedded": {"group": {"name": "Anonymous",
                                                     "uuid": "anon"}}})
        d = rp.as_dict()
        self.assertEqual(d["id"], 7)
        self.assertEqual(d["action"], "READ")
        self.assertEqual(d["groupName"], "Anonymous")
        self.assertEqual(d["groupUUID"], "anon")
        # a re-parse of the cached dict must survive the round-trip
        rp2 = ResourcePolicy(d)
        self.assertEqual(rp2.groupUUID, "anon")
        self.assertEqual(rp2.action, "READ")


if __name__ == "__main__":
    unittest.main()
