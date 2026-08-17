"""
Write-path contract: the POST / DELETE methods this repo calls.

The sync tooling only ever inspects a handful of things off these calls
(``ResourcePolicy.id`` after a create, the response ``status_code`` after a
delete, ``Bitstream.uuid`` after an upload); the tests pin the request that is
sent *and* the object that comes back.
"""
import os
import tempfile
import unittest

import requests_mock

import _helpers  # noqa: F401
from _helpers import (
    make_client, sent_params, multipart_properties, bundle_json,
    bitstream_json, item_json, API, ITEM_UUID, COLLECTION_UUID,
    BITSTREAM_UUID, ANON_GROUP_UUID)
from dspace_rest_client.models import Item, Bundle, Bitstream


class TestCreateResourcePolicy(unittest.TestCase):

    def test_success_sends_params_body_and_returns_policy(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authz/resourcepolicies", status_code=201,
                   json={"id": 42, "action": "READ", "startDate": "2028-05-19",
                         "_embedded": {"group": {"name": "Anonymous",
                                                 "uuid": ANON_GROUP_UUID}}})
            rp = c.create_resourcepolicy(
                resource_uuid=BITSTREAM_UUID, group_uuid=ANON_GROUP_UUID,
                action="READ", start_date="2028-05-19")
            self.assertIsNotNone(rp)
            self.assertEqual(rp.id, 42)
            p = sent_params(m.last_request)
            self.assertEqual(p["resource"], [BITSTREAM_UUID])
            self.assertEqual(p["group"], [ANON_GROUP_UUID])
            body = m.last_request.json()
            self.assertEqual(body["action"], "READ")
            self.assertEqual(body["type"], "resourcepolicy")
            self.assertEqual(body["startDate"], "2028-05-19")

    def test_without_start_date_omits_it_from_body(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authz/resourcepolicies", status_code=201,
                   json={"id": 1, "action": "READ"})
            c.create_resourcepolicy(resource_uuid=BITSTREAM_UUID,
                                    group_uuid=ANON_GROUP_UUID)
            self.assertNotIn("startDate", m.last_request.json())

    def test_invalid_uuid_returns_none_without_request(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertIsNone(c.create_resourcepolicy(
                resource_uuid="bad", group_uuid=ANON_GROUP_UUID))
            self.assertEqual(m.call_count, 0)

    def test_server_error_returns_none(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authz/resourcepolicies", status_code=500, text="boom")
            self.assertIsNone(c.create_resourcepolicy(
                resource_uuid=BITSTREAM_UUID, group_uuid=ANON_GROUP_UUID))


class TestApiDelete(unittest.TestCase):

    def test_returns_response_with_status_code(self):
        c = make_client()
        url = f"{API}/authz/resourcepolicies/42"
        with requests_mock.Mocker() as m:
            m.delete(url, status_code=204)
            self.assertEqual(c.api_delete(url, params=None).status_code, 204)

    def test_404_surfaces_as_response(self):
        # files_access treats a 404 on delete as "already gone" == success.
        c = make_client()
        url = f"{API}/authz/resourcepolicies/7"
        with requests_mock.Mocker() as m:
            m.delete(url, status_code=404)
            self.assertEqual(c.api_delete(url, params=None).status_code, 404)


class TestCreateBundle(unittest.TestCase):

    def test_posts_to_item_bundles_and_returns_bundle(self):
        c = make_client()
        parent = Item(item_json(ITEM_UUID))
        with requests_mock.Mocker() as m:
            m.post(f"{API}/core/items/{ITEM_UUID}/bundles", status_code=201,
                   json=bundle_json("nb", "ORIGINAL"))
            b = c.create_bundle(parent=parent)
            self.assertIsInstance(b, Bundle)
            self.assertEqual(b.uuid, "nb")
            self.assertEqual(m.last_request.json(),
                             {"name": "ORIGINAL", "metadata": {}})

    def test_none_parent_returns_none(self):
        self.assertIsNone(make_client().create_bundle(parent=None))

    def test_server_error_returns_none(self):
        # a failed create returns None (not a uuid-less Bundle), so the
        # importer's `if not bundle` guard fires correctly.
        c = make_client()
        parent = Item(item_json(ITEM_UUID))
        with requests_mock.Mocker() as m:
            m.post(f"{API}/core/items/{ITEM_UUID}/bundles",
                   status_code=500, text="boom")
            self.assertIsNone(c.create_bundle(parent=parent))


class TestCreateItem(unittest.TestCase):

    def test_posts_with_owning_collection_param_and_returns_item(self):
        c = make_client()
        item = Item({"name": "New thesis", "metadata": {}})
        with requests_mock.Mocker() as m:
            m.post(f"{API}/core/items", status_code=201,
                   json=item_json("newu", "New thesis"))
            out = c.create_item(parent=COLLECTION_UUID, item=item)
            self.assertIsInstance(out, Item)
            self.assertEqual(out.uuid, "newu")
            self.assertEqual(sent_params(m.last_request)["owningCollection"],
                             [COLLECTION_UUID])
            # the POST body is item.as_dict() - this is how the importer's built
            # metadata actually reaches DSpace, so pin it, not just the uuid.
            body = m.last_request.json()
            self.assertEqual(body["name"], "New thesis")
            self.assertEqual(body["type"], "item")
            self.assertEqual(body["metadata"], {})
            self.assertIs(body["inArchive"], True)

    def test_server_error_returns_none(self):
        # a failed create returns None (not a uuid-less Item), so the importer's
        # `if dso is None` guard (reposync/_importer.py:127-129) fires correctly.
        c = make_client()
        item = Item({"name": "x", "metadata": {}})
        with requests_mock.Mocker() as m:
            m.post(f"{API}/core/items", status_code=500, text="boom")
            self.assertIsNone(c.create_item(parent=COLLECTION_UUID, item=item))

    def test_non_item_returns_none(self):
        self.assertIsNone(make_client().create_item(
            parent=COLLECTION_UUID, item={"not": "an item"}))

    def test_none_parent_returns_none(self):
        item = Item({"name": "x", "metadata": {}})
        self.assertIsNone(make_client().create_item(parent=None, item=item))


class TestCreateBitstream(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(fd, "wb") as fh:
            fh.write(b"%PDF-1.4 hello world")
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def test_success_multipart_upload_returns_bitstream(self):
        c = make_client()
        bundle = Bundle(bundle_json("bnd"))
        with requests_mock.Mocker() as m:
            m.post(f"{API}/core/bundles/bnd/bitstreams", status_code=201,
                   json=bitstream_json("bsnew", "a.pdf", size=20))
            bs = c.create_bitstream(
                bundle=bundle, name="a.pdf", path=self.path,
                mime="application/pdf",
                metadata={"dc.title": [{"value": "a.pdf"}]})
            self.assertIsInstance(bs, Bitstream)
            self.assertEqual(bs.uuid, "bsnew")
            self.assertEqual(bs.sizeBytes, 20)
            # the request really was a multipart file upload...
            self.assertIn("multipart/form-data",
                          m.last_request.headers["Content-Type"])
            # ...carrying the name/bundleName/metadata that actually attach the
            # bitstream's metadata in DSpace (reposync/_utils.create_new_bitstream)
            props = multipart_properties(m.last_request)
            self.assertEqual(props["name"], "a.pdf")
            self.assertEqual(props["bundleName"], "ORIGINAL")  # == bundle.name
            self.assertEqual(props["metadata"], {"dc.title": [{"value": "a.pdf"}]})

    def test_server_error_returns_none(self):
        c = make_client()
        bundle = Bundle(bundle_json("bnd"))
        with requests_mock.Mocker() as m:
            m.post(f"{API}/core/bundles/bnd/bitstreams", status_code=500,
                   text="boom")
            self.assertIsNone(c.create_bitstream(
                bundle=bundle, name="a.pdf", path=self.path,
                mime="application/pdf"))


class TestCreateClarinAllowances(unittest.TestCase):

    def test_requires_metadata_payload(self):
        # the previous hardcoded {"metadataValue":"Test"} is gone; with no
        # payload the call refuses and makes no request.
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertFalse(c.create_clarinlruallowances(BITSTREAM_UUID))
            self.assertEqual(m.call_count, 0)

    def test_posts_supplied_payload(self):
        c = make_client()
        payload = [{"metadataKey": "NAME", "metadataValue": "real value"}]
        with requests_mock.Mocker() as m:
            m.post(f"{API}/core/clarinusermetadata/manage", status_code=200,
                   json={})
            self.assertTrue(c.create_clarinlruallowances(BITSTREAM_UUID, payload))
            self.assertEqual(m.last_request.json(), payload)
            self.assertEqual(sent_params(m.last_request)["bitstreamUUID"],
                             [BITSTREAM_UUID])


if __name__ == "__main__":
    unittest.main()
