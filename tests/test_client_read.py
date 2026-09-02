"""
Read-path contract: every GET method this repo calls.

Each test stubs only the HTTP response and asserts the real client (a) hits the
right URL with the right query params and (b) parses the response into the model
objects / shapes the callers rely on.
"""
import unittest

import requests_mock

import _helpers  # noqa: F401
from _helpers import (
    make_client, sent_params, embedded, item_json, bundle_json,
    bitstream_json, policy_json, API, ITEM_UUID, BITSTREAM_UUID)
from dspace_rest_client.models import Item, Bundle, Collection, Community


class TestSearchObjects(unittest.TestCase):

    def test_builds_url_params_and_parses_objects(self):
        c = make_client()
        # every caller's next step is dso.as_dict() + dso.links['self']['href']
        # (repo._search.dso2dict, mcp._dso_to_dict), so the search result must
        # carry both - include a self link to prove it survives parsing.
        obj1 = item_json("u1", "A", _links={"self": {"href": f"{API}/items/u1"}})
        body = {"_embedded": {"searchResult": {
            "page": {"totalElements": 2, "size": 100},
            "_embedded": {"objects": [
                {"_embedded": {"indexableObject": obj1}},
                {"_embedded": {"indexableObject": item_json("u2", "B")}},
            ]}}}}
        with requests_mock.Mocker() as m:
            m.get(f"{API}/discover/search/objects", json=body)
            details = {}
            res = c.search_objects(query="dc.identifier:123", size=100,
                                   page=0, details=details)
            self.assertEqual([d.uuid for d in res], ["u1", "u2"])
            # the two accessors every consumer reads off a search hit
            self.assertEqual(res[0].links["self"]["href"], f"{API}/items/u1")
            self.assertEqual(res[0].as_dict()["uuid"], "u1")
            p = sent_params(m.last_request)
            self.assertEqual(p["query"], ["dc.identifier:123"])
            self.assertEqual(p["size"], ["100"])
            self.assertEqual(p["page"], ["0"])
            # details["page"] is what repo.search.export_iter reads as export_len
            self.assertEqual(details["page"]["totalElements"], 2)

    def test_backend_error_returns_empty_list(self):
        # fetch_resource returns None on a non-200; search_objects swallows the
        # resulting TypeError and yields [] rather than crashing the crawl.
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/discover/search/objects", status_code=500, text="boom")
            self.assertEqual(c.search_objects(query="x"), [])

    def test_empty_result_set_returns_empty_list(self):
        c = make_client()
        body = {"_embedded": {"searchResult": {
            "page": {"totalElements": 0},
            "_embedded": {"objects": []}}}}
        with requests_mock.Mocker() as m:
            m.get(f"{API}/discover/search/objects", json=body)
            self.assertEqual(c.search_objects(query="x"), [])


class TestGetItems(unittest.TestCase):

    def test_parses_embedded_items_with_paging_params(self):
        c = make_client()
        body = embedded("items", [item_json("i1", "one"), item_json("i2", "two")])
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items", json=body)
            items = c.get_items(page=2, size=50)
            self.assertEqual([i.uuid for i in items], ["i1", "i2"])
            self.assertTrue(all(isinstance(i, Item) for i in items))
            p = sent_params(m.last_request)
            self.assertEqual(p["page"], ["2"])
            self.assertEqual(p["size"], ["50"])


class TestGetItem(unittest.TestCase):

    def test_returns_typed_item(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/{ITEM_UUID}", json=item_json(ITEM_UUID, "T"))
            it = c.get_item(ITEM_UUID)
            self.assertIsInstance(it, Item)
            self.assertEqual(it.uuid, ITEM_UUID)
            self.assertEqual(it.name, "T")

    def test_invalid_uuid_returns_none_without_request(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            for value in ("not-a-uuid", None):
                with self.subTest(value=value):
                    self.assertIsNone(c.get_item(value))
            self.assertEqual(m.call_count, 0)


class TestUuidValidation(unittest.TestCase):

    def test_uuid_endpoints_reject_none_without_request(self):
        c = make_client()
        cases = (
            ("get_dso", lambda: c.get_dso(f"{API}/core/items", None)),
            ("get_resourcepolicy", lambda: c.get_resourcepolicy(None)),
            ("create_resourcepolicy_resource", lambda: c.create_resourcepolicy(
                resource_uuid=None, group_uuid=BITSTREAM_UUID)),
            ("create_resourcepolicy_group", lambda: c.create_resourcepolicy(
                resource_uuid=BITSTREAM_UUID, group_uuid=None)),
        )
        with requests_mock.Mocker() as m:
            for name, call in cases:
                with self.subTest(name=name):
                    self.assertIsNone(call())
            self.assertEqual(m.call_count, 0)


class TestGetBundles(unittest.TestCase):

    def test_by_parent_item_lists_bundles(self):
        c = make_client()
        parent = Item(item_json(ITEM_UUID))
        body = embedded("bundles", [
            bundle_json("b1", "ORIGINAL"), bundle_json("b2", "THUMBNAIL")])
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles", json=body)
            bundles = c.get_bundles(parent=parent, size=1000)
            self.assertEqual([b.name for b in bundles], ["ORIGINAL", "THUMBNAIL"])
            self.assertTrue(all(isinstance(b, Bundle) for b in bundles))
            self.assertEqual(sent_params(m.last_request)["size"], ["1000"])

    def test_by_uuid_returns_single_wrapped_in_list(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/bundles/b9", json=bundle_json("b9", "ORIGINAL"))
            bundles = c.get_bundles(uuid="b9")
            self.assertEqual(len(bundles), 1)
            self.assertEqual(bundles[0].uuid, "b9")

    def test_deleted_item_404_returns_empty_list(self):
        # PR #16 contract: a gone item is a clean empty result, not a crash.
        c = make_client()
        parent = Item(item_json(ITEM_UUID))
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles", status_code=404,
                  json={"timestamp": "2026-01-01"})
            self.assertEqual(c.get_bundles(parent=parent), [])

    def test_non_404_error_raises_informative_error(self):
        # a non-404 fetch failure surfaces with its status + url so the caller
        # can retry, rather than an opaque 'NoneType is not subscriptable'.
        c = make_client()
        parent = Item(item_json(ITEM_UUID))
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles",
                  status_code=500, text="boom")
            with self.assertRaises(RuntimeError) as ctx:
                c.get_bundles(parent=parent)
            self.assertIn("500", str(ctx.exception))

    def test_no_args_returns_empty_without_request(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertEqual(c.get_bundles(), [])
            self.assertEqual(m.call_count, 0)


class TestGetBitstreams(unittest.TestCase):

    def test_by_bundle_uses_embedded_link(self):
        c = make_client()
        # href deliberately NOT equal to the fallback URL (.../bundles/bnd/
        # bitstreams): if the embedded-link branch were removed the client would
        # build the fallback, which is unmocked, and this test would fail.
        href = f"{API}/core/bundles/HREF-ONLY-PATH/bitstreams"
        bundle = Bundle(bundle_json("bnd", bitstreams_href=href))
        body = embedded("bitstreams", [bitstream_json("s1", "a.pdf", size=10)])
        with requests_mock.Mocker() as m:
            m.get(href, json=body)
            bs = c.get_bitstreams(bundle=bundle, size=500)
            self.assertEqual([b.uuid for b in bs], ["s1"])
            self.assertEqual(bs[0].sizeBytes, 10)
            self.assertEqual(m.last_request.url.split("?")[0], href)
            self.assertEqual(sent_params(m.last_request)["size"], ["500"])

    def test_by_bundle_without_link_constructs_url(self):
        c = make_client()
        bundle = Bundle(bundle_json("bnd2"))  # no _links -> manual URL
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/bundles/bnd2/bitstreams",
                  json=embedded("bitstreams",
                                [bitstream_json("s9", "x.pdf", size=7)]))
            bs = c.get_bitstreams(bundle=bundle)
            # proves both the constructed URL AND parsing on the fallback path
            self.assertEqual([b.uuid for b in bs], ["s9"])
            self.assertEqual(bs[0].sizeBytes, 7)

    def test_no_args_returns_empty_list(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertEqual(c.get_bitstreams(), [])
            self.assertEqual(m.call_count, 0)

    def test_deleted_bundle_404_returns_empty_list(self):
        # 404 -> [] fail-safe, mirroring get_bundles (#16): a gone bundle simply
        # has no bitstreams, which is a clean empty result, not a crash.
        c = make_client()
        bundle = Bundle(bundle_json("bnd2"))
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/bundles/bnd2/bitstreams",
                  status_code=404, json={"timestamp": "2026-01-01"})
            self.assertEqual(c.get_bitstreams(bundle=bundle), [])

    def test_non_404_error_raises_informative_error(self):
        # a transient 5xx must NOT masquerade as "no bitstreams"; it surfaces
        # with its status + url (not a bare TypeError) so the caller can retry.
        c = make_client()
        bundle = Bundle(bundle_json("bnd2"))
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/bundles/bnd2/bitstreams",
                  status_code=500, text="boom")
            with self.assertRaises(RuntimeError) as ctx:
                c.get_bitstreams(bundle=bundle)
            self.assertIn("500", str(ctx.exception))
            self.assertIn("/core/bundles/bnd2/bitstreams", str(ctx.exception))

    def test_200_without_bitstreams_returns_empty_list(self):
        # a well-formed response with no bitstreams -> [] (not None), so callers
        # can iterate the result unconditionally.
        c = make_client()
        bundle = Bundle(bundle_json("bnd2"))
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/bundles/bnd2/bitstreams",
                  json={"page": {"totalElements": 0}})
            self.assertEqual(c.get_bitstreams(bundle=bundle), [])


class TestGetCollections(unittest.TestCase):

    def test_for_community_uses_collections_link(self):
        c = make_client()
        href = f"{API}/core/communities/c1/collections"
        com = Community({"uuid": "c1", "name": "Com", "type": "community",
                         "_links": {"collections": {"href": href}}})
        body = embedded("collections", [
            {"uuid": "col1", "name": "Theses", "handle": "123/1",
             "type": "collection"}])
        with requests_mock.Mocker() as m:
            m.get(href, json=body)
            cols = c.get_collections(community=com)
            self.assertEqual([x.name for x in cols], ["Theses"])
            self.assertEqual(cols[0].handle, "123/1")
            self.assertTrue(all(isinstance(x, Collection) for x in cols))

    def test_plain_list(self):
        c = make_client()
        body = embedded("collections", [
            {"uuid": "col2", "name": "C2", "type": "collection"}])
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/collections", json=body)
            cols = c.get_collections()
            self.assertEqual([x.uuid for x in cols], ["col2"])


class TestGetCommunities(unittest.TestCase):

    def test_top_uses_search_top_endpoint(self):
        c = make_client()
        body = embedded("communities", [
            {"uuid": "c1", "name": "Top", "type": "community"}])
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/communities/search/top", json=body)
            coms = c.get_communities(top=True)
            self.assertEqual([x.name for x in coms], ["Top"])
            self.assertTrue(all(isinstance(x, Community) for x in coms))

    def test_plain_list(self):
        c = make_client()
        body = embedded("communities", [
            {"uuid": "c2", "name": "Other", "type": "community"}])
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/communities", json=body)
            coms = c.get_communities()
            self.assertEqual([x.uuid for x in coms], ["c2"])


class TestGetResourcePolicy(unittest.TestCase):

    def test_parses_live_policies_and_sends_uuid_action(self):
        c = make_client()
        body = embedded("resourcepolicies", [policy_json(pid=1)])
        with requests_mock.Mocker() as m:
            m.get(f"{API}/authz/resourcepolicies/search/resource", json=body)
            rps = c.get_resourcepolicy(BITSTREAM_UUID, action="READ")
            self.assertEqual(len(rps), 1)
            self.assertEqual(rps[0].groupName, "Anonymous")
            p = sent_params(m.last_request)
            self.assertEqual(p["uuid"], [BITSTREAM_UUID])
            self.assertEqual(p["action"], ["READ"])

    def test_action_none_omits_the_action_filter(self):
        # The bitstream export path calls this via the ingest wrapper whose
        # default is action=None (ingest/_dspace.py get_resourcepolicy), which
        # must fetch policies of ALL actions - so no `action` param is sent.
        c = make_client()
        body = embedded("resourcepolicies", [
            policy_json(pid=1, action="READ"),
            policy_json(pid=2, action="WRITE")])
        with requests_mock.Mocker() as m:
            m.get(f"{API}/authz/resourcepolicies/search/resource", json=body)
            rps = c.get_resourcepolicy(BITSTREAM_UUID, action=None)
            self.assertEqual([rp.action for rp in rps], ["READ", "WRITE"])
            p = sent_params(m.last_request)
            self.assertEqual(p["uuid"], [BITSTREAM_UUID])
            self.assertNotIn("action", p)

    def test_empty_result_set_returns_empty_list(self):
        # The live endpoint returns an _embedded envelope even when empty.
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/authz/resourcepolicies/search/resource",
                  json=embedded("resourcepolicies", []))
            self.assertEqual(c.get_resourcepolicy(BITSTREAM_UUID), [])

    def test_invalid_uuid_returns_none_without_request(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertIsNone(c.get_resourcepolicy("not-a-uuid"))
            self.assertEqual(m.call_count, 0)

    def test_fetch_failure_returns_none(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/authz/resourcepolicies/search/resource",
                  status_code=500, text="boom")
            self.assertIsNone(c.get_resourcepolicy(BITSTREAM_UUID))


class TestFetchResource(unittest.TestCase):

    def test_200_returns_parsed_json(self):
        c = make_client()
        url = f"{API}/eperson/groups/search/byMetadata"
        with requests_mock.Mocker() as m:
            m.get(url, json=embedded("groups", []))
            self.assertEqual(c.fetch_resource(url, params={"query": "Anonymous"}),
                             {"_embedded": {"groups": []}})

    def test_404_returns_none_and_records_last_err(self):
        # group_uuid() and get_bundles() both branch on last_err.status_code.
        c = make_client()
        url = f"{API}/core/items/{ITEM_UUID}/bundles"
        with requests_mock.Mocker() as m:
            m.get(url, status_code=404, text="gone")
            self.assertIsNone(c.fetch_resource(url))
            self.assertEqual(c.last_err.status_code, 404)


if __name__ == "__main__":
    unittest.main()
