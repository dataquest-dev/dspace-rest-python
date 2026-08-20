"""
Integration contract: the exact multi-call sequences DSpace-ISstag-integration
runs against this library.

Where the per-method tests pin one call, these replay a whole flow end-to-end
(only the HTTP transport mocked) so that a library change which individually
looks harmless but breaks a *chain* our tooling depends on still fails here.

Each test names the source it mirrors.
"""
import unittest
from types import SimpleNamespace

import requests_mock

import _helpers  # noqa: F401
from _helpers import (
    make_client, sent_params, embedded, item_json, bundle_json, bitstream_json,
    policy_json, API, ITEM_UUID, BITSTREAM_UUID, ANON_GROUP_UUID)
from dspace_rest_client.models import Item, Bundle


class TestBitstreamExportChain(unittest.TestCase):
    """Mirrors src/export/_dspace.py :: exporter.export_bitstreams -
    get_bundles(parent) -> get_resourcepolicy(bundle) -> get_bitstreams(bundle)
    -> get_resourcepolicy(bitstream), then serialises a fixed set of attrs."""

    # real UUIDs: the export chain calls get_resourcepolicy() on the bundle and
    # bitstream, and that method validates (and short-circuits on) its UUID arg.
    BUNDLE_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    def test_full_chain_yields_serialisable_attributes(self):
        c = make_client()
        item = Item(item_json(ITEM_UUID))
        bits_href = f"{API}/core/bundles/{self.BUNDLE_UUID}/bitstreams"
        bundle_md = {"dc.title": [{"value": "ORIGINAL"}]}
        bs_md = {"dc.description": [{"value": "VŠKP"}]}
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles",
                  json=embedded("bundles",
                                [bundle_json(self.BUNDLE_UUID, "ORIGINAL",
                                             bitstreams_href=bits_href,
                                             metadata=bundle_md)]))
            m.get(bits_href,
                  json=embedded("bitstreams",
                                [bitstream_json(BITSTREAM_UUID, "thesis.pdf",
                                                size=123, seq=1, checksum="abc",
                                                metadata=bs_md)]))
            m.get(f"{API}/authz/resourcepolicies/search/resource",
                  json=embedded("resourcepolicies", [policy_json(pid=1)]))

            bundles = c.get_bundles(parent=item, size=1000)
            self.assertEqual(len(bundles), 1)
            bundle = bundles[0]
            self.assertEqual((bundle.name, bundle.uuid, bundle.type),
                             ("ORIGINAL", self.BUNDLE_UUID, "bundle"))
            self.assertEqual(bundle.metadata, bundle_md)

            # the exporter calls get_resourcepolicy via a wrapper defaulting to
            # action=None (ingest/_dspace.py), so NO action filter is sent.
            bundle_rp = c.get_resourcepolicy(bundle.uuid, action=None)
            self.assertEqual([rp.as_dict()["groupName"] for rp in bundle_rp],
                             ["Anonymous"])
            self.assertNotIn("action", sent_params(m.last_request))

            bitstreams = c.get_bitstreams(bundle=bundle, size=1000)
            self.assertEqual(len(bitstreams), 1)
            b = bitstreams[0]
            # a representative set of the attributes the exporter serialises
            # (src/export/_dspace.py:333-340) - name/uuid/size/seq/checksum/meta
            self.assertEqual((b.name, b.uuid, b.sizeBytes, b.sequenceId),
                             ("thesis.pdf", BITSTREAM_UUID, 123, 1))
            self.assertEqual(b.checkSum["value"], "abc")
            self.assertEqual(b.metadata, bs_md)

            bs_rp = c.get_resourcepolicy(b.uuid, action=None)
            self.assertEqual(bs_rp[0].as_dict()["groupUUID"], ANON_GROUP_UUID)


class TestPolicyReplacementChain(unittest.TestCase):
    """Mirrors src/reposync/_files.py :: files_access._set_read_policy -
    read live policies, create a fresh Anonymous READ policy, delete the old."""

    def test_read_create_delete(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/authz/resourcepolicies/search/resource",
                  json=embedded("resourcepolicies", [policy_json(pid=11)]))
            m.post(f"{API}/authz/resourcepolicies", status_code=201,
                   json={"id": 99, "action": "READ", "startDate": "2028-05-19",
                         "_embedded": {"group": {"name": "Anonymous",
                                                 "uuid": ANON_GROUP_UUID}}})
            m.delete(f"{API}/authz/resourcepolicies/11", status_code=204)

            live = c.get_resourcepolicy(BITSTREAM_UUID, action="READ")
            # _set_read_policy reads id / action / groupName off each live policy
            self.assertEqual(live[0].id, 11)
            self.assertEqual(live[0].action, "READ")
            self.assertEqual(live[0].groupName, "Anonymous")

            new = c.create_resourcepolicy(
                resource_uuid=BITSTREAM_UUID, group_uuid=ANON_GROUP_UUID,
                action="READ", start_date="2028-05-19")
            self.assertEqual(new.id, 99)

            r = c.api_delete(
                f"{API}/authz/resourcepolicies/{live[0].id}", params=None)
            self.assertEqual(r.status_code, 204)


class TestMcpBundleWalk(unittest.TestCase):
    """Mirrors mcp/core.py :: make_service_from_env - lookup via search_objects,
    then get_item -> get_bundles(SimpleNamespace parent) -> get_bitstreams."""

    def test_lookup_then_item_bundles_bitstreams(self):
        c = make_client()
        # mcp/core.py drops _links (it round-trips bundles through as_dict), so
        # get_bitstreams must use the manually-constructed fallback URL, not the
        # embedded link. The link below is a decoy that must NOT be requested.
        decoy_href = f"{API}/core/bundles/DECOY-LINK/bitstreams"
        fallback = f"{API}/core/bundles/bnd/bitstreams"
        with requests_mock.Mocker() as m:
            m.get(f"{API}/discover/search/objects", json={"_embedded": {
                "searchResult": {"page": {"totalElements": 1},
                                 "_embedded": {"objects": [
                                     {"_embedded": {"indexableObject":
                                                    item_json(ITEM_UUID, "T")}}]}}}})
            m.get(f"{API}/core/items/{ITEM_UUID}", json=item_json(ITEM_UUID, "T"))
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles",
                  json=embedded("bundles",
                                [bundle_json("bnd", "ORIGINAL",
                                             bitstreams_href=decoy_href)]))
            m.get(fallback,
                  json=embedded("bitstreams", [bitstream_json("bs1", "a.pdf")]))

            matches = c.search_objects(query="dc.identifier:42")
            self.assertEqual(matches[0].uuid, ITEM_UUID)

            item = c.get_item(ITEM_UUID)
            self.assertEqual(item.uuid, ITEM_UUID)

            # mcp passes a duck-typed parent (only .uuid), not a real Item
            parent = SimpleNamespace(uuid=item.uuid)
            bundles = c.get_bundles(parent=parent, size=200)
            self.assertEqual(bundles[0].name, "ORIGINAL")

            # mirror mcp: rebuild the Bundle from as_dict() (which strips _links)
            # so get_bitstreams takes the fallback-URL branch the consumer hits.
            bstub = Bundle(bundles[0].as_dict())
            self.assertNotIn("bitstreams", bstub.links)
            bitstreams = c.get_bitstreams(bundle=bstub, size=500)
            self.assertEqual(bitstreams[0].uuid, "bs1")
            self.assertEqual(m.last_request.url.split("?")[0], fallback)


class TestGroupSearchForUuidResolution(unittest.TestCase):
    """Mirrors src/ingest/_dspace.py :: dspace_be.group_uuid - a raw
    fetch_resource on the group-search endpoint, reading _embedded.groups."""

    def test_group_search_shape(self):
        c = make_client()
        url = f"{API}/eperson/groups/search/byMetadata"
        with requests_mock.Mocker() as m:
            m.get(url, json=embedded("groups", [
                {"name": "Anonymous", "uuid": "anon-uuid"}]))
            r = c.fetch_resource(url, params={"query": "Anonymous", "size": 100})
            groups = (r.get("_embedded") or {}).get("groups") or []
            self.assertEqual(groups[0]["name"], "Anonymous")
            self.assertEqual(groups[0]["uuid"], "anon-uuid")


if __name__ == "__main__":
    unittest.main()
