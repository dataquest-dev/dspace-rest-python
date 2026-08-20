"""
CLARIN/UFAL read surface - the methods the three main-lineage consumers
(dspace-rest-test, dspace-import-clarin, dspace-item-importer) call but which
had zero coverage after `main` was merged into `dtq`.

Same discipline as the DQ suite: mock only the HTTP transport, let the real
client build URLs / parse responses. Each test names the consumer it mirrors.

Marks:
  clarin    - shared surface, must hold on both `main` and `dtq`
  dtq_only  - asserts a fix or a method that exists only on `dtq`; deselected
              when the differential-contract CI job runs against `main`.
"""
import unittest

import pytest
import requests_mock

import _helpers  # noqa: F401
from _helpers import (
    make_client, sent_params, embedded, item_json, bundle_json, raw_policy_json,
    user_json, clarin_allowance_json, search_envelope,
    API, ITEM_UUID, COLLECTION_UUID, BUNDLE_UUID, EPERSON_UUID)
from dspace_rest_client.models import Bundle, Item, Collection, User

pytestmark = pytest.mark.clarin


class TestGetResourcePolicyDict(unittest.TestCase):
    """Mirrors dspace-import-clarin - get_resource_policy(uuid)["id"].
    The dict-subscript contract that blocks the resource-policy API unification;
    it must keep returning a raw dict, not a model."""

    URL = f"{API}/authz/resourcepolicies/search/resource"

    def test_returns_first_raw_dict_with_id_subscript(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=embedded("resourcepolicies",
                                          [raw_policy_json(pid=7),
                                           raw_policy_json(pid=8)]))
            rp = c.get_resource_policy(BUNDLE_UUID)
            self.assertIsInstance(rp, dict)
            self.assertEqual(rp["id"], 7)          # dict subscript, first policy

    def test_sends_uuid_and_both_embeds(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=embedded("resourcepolicies", [raw_policy_json()]))
            c.get_resource_policy(BUNDLE_UUID)
            qs = sent_params(m.last_request)
            self.assertEqual(qs["uuid"], [BUNDLE_UUID])
            self.assertEqual(sorted(qs["embed"]), ["eperson", "group"])

    @pytest.mark.dtq_only
    def test_empty_list_returns_none(self):
        """D2: an empty policy list must be a clean None, not an IndexError."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=embedded("resourcepolicies", []))
            self.assertIsNone(c.get_resource_policy(BUNDLE_UUID))

    @pytest.mark.dtq_only
    def test_non_200_returns_none_and_records_last_err(self):
        """D3: a failed request must be None, not a NoneType subscript crash -
        and last_err is recorded so a caller can tell an HTTP error apart from a
        genuine empty result (both return None)."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, status_code=500, text="upstream boom")
            self.assertIsNone(c.get_resource_policy(BUNDLE_UUID))
            self.assertIsNotNone(c.last_err)
            self.assertEqual(c.last_err.status_code, 500)


class TestGetBundleByName(unittest.TestCase):
    """Mirrors dspace-import-clarin - get_bundle_by_name('ORIGINAL', item)."""

    URL = f"{API}/core/items/{ITEM_UUID}/bundles"

    def test_matches_named_bundle(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=embedded("bundles", [
                bundle_json("b1", "LICENSE"),
                bundle_json("b2", "ORIGINAL")]))
            b = c.get_bundle_by_name("ORIGINAL", ITEM_UUID)
            self.assertIsInstance(b, Bundle)
            self.assertEqual((b.uuid, b.name), ("b2", "ORIGINAL"))

    def test_no_match_returns_none(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=embedded("bundles", [bundle_json("b1", "LICENSE")]))
            self.assertIsNone(c.get_bundle_by_name("ORIGINAL", ITEM_UUID))

    @pytest.mark.dtq_only
    def test_non_200_returns_none(self):
        """D1: a failed lookup must be None, not a NoneType subscript crash."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, status_code=500, text="boom")
            self.assertIsNone(c.get_bundle_by_name("ORIGINAL", ITEM_UUID))


class TestGetItemsFromCollection(unittest.TestCase):
    """Mirrors dspace-import-clarin - get_items_from_collection(collection)."""

    URL = f"{API}/discover/search/objects"

    def test_parses_search_envelope(self):
        c = make_client()
        other = "22222222-2222-2222-2222-222222222222"
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=search_envelope([
                item_json(ITEM_UUID, "A"), item_json(other, "B")]))
            items = c.get_items_from_collection(COLLECTION_UUID)
            self.assertEqual(len(items), 2)
            self.assertTrue(all(isinstance(i, Item) for i in items))
            self.assertEqual([i.uuid for i in items], [ITEM_UUID, other])

    def test_sends_scope_dsotype_sort_embed(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=search_envelope([]))
            c.get_items_from_collection(COLLECTION_UUID)
            qs = sent_params(m.last_request)
            self.assertEqual(qs["scope"], [COLLECTION_UUID])
            self.assertEqual(qs["dsoType"], ["ITEM"])
            self.assertEqual(qs["sort"], ["dc.date.accessioned,DESC"])
            self.assertEqual(qs["embed"], ["thumbnail"])

    @pytest.mark.dtq_only
    def test_non_200_returns_empty(self):
        """D6: a failed request must yield [], not a NoneType subscript crash."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, status_code=500, text="boom")
            self.assertEqual(c.get_items_from_collection(COLLECTION_UUID), [])


class TestGetItemByHandle(unittest.TestCase):
    """Mirrors dspace-rest-test - get_item_by_handle(handle)."""

    URL = f"{API}/core/items/search/byHandle"

    def test_returns_first_item(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=embedded("items", [item_json(ITEM_UUID, "T")]))
            item = c.get_item_by_handle("123456789/42")
            self.assertIsInstance(item, Item)
            self.assertEqual(item.uuid, ITEM_UUID)
            self.assertEqual(sent_params(m.last_request)["handle"], ["123456789/42"])

    def test_none_handle_short_circuits(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertIsNone(c.get_item_by_handle(None))
            self.assertFalse(m.called)

    def test_no_match_returns_none(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=embedded("items", []))
            self.assertIsNone(c.get_item_by_handle("123456789/0"))

    def test_non_json_body_returns_none(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, status_code=500, text="<html>error</html>")
            self.assertIsNone(c.get_item_by_handle("123456789/42"))


class TestGetUserByEmail(unittest.TestCase):
    """Mirrors dspace-rest-test - get_user_by_email(email)."""

    URL = f"{API}/eperson/epersons/search/byEmail"

    def test_returns_user_with_uuid_and_email(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json=user_json(email="a@b.c", netid="n1"))
            u = c.get_user_by_email("a@b.c")
            self.assertIsInstance(u, User)
            self.assertEqual((u.uuid, u.email), (EPERSON_UUID, "a@b.c"))
            self.assertEqual(sent_params(m.last_request)["email"], ["a@b.c"])

    @pytest.mark.dtq_only
    def test_404_returns_none(self):
        """D4: a miss (404) must be falsy, not a truthy uuid-less User that
        slips past the consumer's `if user:` guard."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, status_code=404, json={"timestamp": "now"})
            u = c.get_user_by_email("nobody@nowhere")
            self.assertIsNone(u)
            self.assertFalse(bool(u))
            # the failing response is retained for callers, even for a 404 miss
            self.assertIsNotNone(c.last_err)
            self.assertEqual(c.last_err.status_code, 404)


class TestGetClarinAllowances(unittest.TestCase):
    """Mirrors dspace-rest-test - get_clarinlruallowances[_by_bitstream_and_user]."""

    def test_returns_embedded_list(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/clarinlruallowances",
                  json=embedded("clarinlruallowances", [clarin_allowance_json(1)]))
            allowances = c.get_clarinlruallowances()
            self.assertEqual(len(allowances), 1)
            self.assertEqual(allowances[0]["id"], 1)

    def test_error_returns_none(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/clarinlruallowances", status_code=500, text="boom")
            self.assertIsNone(c.get_clarinlruallowances())

    def test_by_bitstream_and_user_sends_both_params(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/clarinlruallowances/search/byBitstreamAndUser",
                  json=embedded("clarinlruallowances", [clarin_allowance_json(9)]))
            out = c.get_clarinlruallowances_by_bitstream_and_user("bs-1", "usr-1")
            self.assertEqual(out[0]["id"], 9)
            qs = sent_params(m.last_request)
            self.assertEqual(qs["bitstreamUUID"], ["bs-1"])
            self.assertEqual(qs["userUUID"], ["usr-1"])


@pytest.mark.dtq_only
class TestGetOwningCollection(unittest.TestCase):
    """dtq-only method. Mirrors src/repo/_audit.py:105-111, which relies on a
    None return + last_err.status_code to drive its 401 reauth retry."""

    URL = f"{API}/core/items/{ITEM_UUID}/owningCollection"

    def test_returns_typed_collection(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, json={"uuid": COLLECTION_UUID, "name": "Coll",
                                  "type": "collection"})
            col = c.get_owningCollection(ITEM_UUID)
            self.assertIsInstance(col, Collection)
            self.assertEqual(col.uuid, COLLECTION_UUID)

    def test_non_200_returns_none_and_sets_last_err(self):
        """D8: on 401 the method must return None (not an empty truthy
        Collection) and expose last_err, or _audit.py's reauth branch is dead."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(self.URL, status_code=401, json={"message": "Unauthorized"})
            col = c.get_owningCollection(ITEM_UUID)
            self.assertIsNone(col)
            self.assertIsNotNone(c.last_err)
            self.assertEqual(c.last_err.status_code, 401)


if __name__ == "__main__":
    unittest.main()
