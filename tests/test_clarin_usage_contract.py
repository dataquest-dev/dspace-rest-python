"""
CLARIN-side integration contracts - the whole multi-call sequences the three
main-lineage consumers run, the counterpart to test_repo_usage_contract.py.

Where the per-method tests pin one call, these replay a flow end-to-end (only
the HTTP transport mocked) so a library change that individually looks harmless
but breaks a *chain* a consumer depends on still fails here.

Each class names the consumer repo it mirrors. clarin = must hold on both
main and dtq; dtq_only = relies on a dtq fix/behaviour, deselected on the main
leg of the differential-contract CI job.
"""
import unittest

import pytest
import requests_mock

import _helpers  # noqa: F401
from _helpers import (
    make_client, sent_params, embedded, item_json, bundle_json, raw_policy_json,
    user_json, group_json, license_json, label_json, clarin_allowance_json,
    search_envelope, API, ITEM_UUID, COLLECTION_UUID, BUNDLE_UUID, BITSTREAM_UUID,
    EPERSON_UUID, GROUP_UUID)
from dspace_rest_client.models import Item, Bundle, Group, User, License

pytestmark = pytest.mark.clarin


class TestImportClarinPolicyChain(unittest.TestCase):
    """Mirrors dspace-import-clarin - locate the ORIGINAL bundle, read its
    resource policy as a raw dict, move the policy to a new group."""

    def test_bundle_then_policy_dict_then_group_update(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles",
                  json=embedded("bundles", [
                      bundle_json("lic", "LICENSE"),
                      bundle_json(BUNDLE_UUID, "ORIGINAL")]))
            m.get(f"{API}/authz/resourcepolicies/search/resource",
                  json=embedded("resourcepolicies", [raw_policy_json(pid=55)]))
            m.put(f"{API}/authz/resourcepolicies/55/group",
                  status_code=200, json={})

            bundle = c.get_bundle_by_name("ORIGINAL", ITEM_UUID)
            self.assertEqual(bundle.uuid, BUNDLE_UUID)

            policy = c.get_resource_policy(bundle.uuid)
            pid = policy["id"]                      # dict subscript, not a model
            self.assertEqual(pid, 55)

            r = c.update_resource_policy_group(pid, GROUP_UUID)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(m.last_request.method, "PUT")

    @pytest.mark.dtq_only
    def test_missing_bundle_aborts_cleanly(self):
        """D1: when the bundle lookup fails, get_bundle_by_name is None and the
        chain stops - it must not crash on a NoneType subscript."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles",
                  status_code=500, text="boom")
            self.assertIsNone(c.get_bundle_by_name("ORIGINAL", ITEM_UUID))


class TestImportClarinLicenseIngest(unittest.TestCase):
    """Mirrors dspace-import-clarin - read a collection's items, then build the
    License dicts the importer writes out."""

    def test_collection_items_then_license_to_dict(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/discover/search/objects",
                  json=search_envelope([item_json(ITEM_UUID, "A"),
                                        item_json(COLLECTION_UUID, "B")]))
            items = c.get_items_from_collection(COLLECTION_UUID)
            self.assertEqual(len(items), 2)
            self.assertTrue(all(isinstance(i, Item) for i in items))

        lic = License(license_json(lid=1, name="CC-BY",
                                   label=label_json(lid=9, label="PUB")))
        out = lic.to_dict()
        self.assertEqual(out["license_id"], 1)
        self.assertEqual(out["label_id"], 9)


class TestImportClarinMetadataRemoval(unittest.TestCase):
    """Mirrors dspace-import-clarin - read items, remove an indexed metadata
    value from one (the 3-arg remove_metadata(item, field, place) form)."""

    def test_items_then_indexed_remove(self):
        c = make_client()
        self_href = f"{API}/core/items/{ITEM_UUID}"
        with requests_mock.Mocker() as m:
            m.get(f"{API}/discover/search/objects",
                  json=search_envelope([item_json(
                      ITEM_UUID, "A", _links={"self": {"href": self_href}})]))
            m.patch(self_href, status_code=200,
                    json=item_json(ITEM_UUID, "A", id=ITEM_UUID))

            items = c.get_items_from_collection(COLLECTION_UUID)
            c.remove_metadata(items[0], "dc.title", 0)

            body = m.last_request.json()
            self.assertEqual(body[0]["op"], "remove")
            self.assertEqual(body[0]["path"], "/metadata/dc.title/0")


class TestRestTestSubmitterSetup(unittest.TestCase):
    """Mirrors dspace-rest-test - resolve a user by email, create a collection
    submitter group, add the user to it."""

    def test_email_group_member(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/eperson/epersons/search/byEmail",
                  json=user_json(uuid=EPERSON_UUID, email="sub@dq.sk"))
            m.post(f"{API}/core/collections/{COLLECTION_UUID}/submittersGroup",
                   status_code=201, json=group_json(GROUP_UUID, "submitters"))
            m.post(f"{API}/eperson/groups/{GROUP_UUID}/epersons", status_code=204)

            user = c.get_user_by_email("sub@dq.sk")
            self.assertIsInstance(user, User)

            group = c.create_submit_group(
                type("C", (), {"uuid": COLLECTION_UUID})())
            self.assertIsInstance(group, Group)

            self.assertTrue(c.add_member(group, user))

    @pytest.mark.dtq_only
    def test_unknown_email_stops_before_add_member(self):
        """D4: an unknown email must resolve to None so the consumer's
        `if user:` guard skips group creation - not proceed with a uuid-less
        User and fail deep inside add_member."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/eperson/epersons/search/byEmail",
                  status_code=404, json={"timestamp": "now"})

            user = c.get_user_by_email("ghost@nowhere")
            self.assertIsNone(user)
            # consumer guard: nothing past the lookup should have been requested
            self.assertEqual(len(m.request_history), 1)


class TestRestTestBitstreamPolicyFlow(unittest.TestCase):
    """Mirrors dspace-rest-test - resolve an item by handle, find its ORIGINAL
    bundle, grant a resource policy, then read user allowances."""

    def test_handle_bundle_policy_allowance(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items/search/byHandle",
                  json=embedded("items", [item_json(ITEM_UUID, "T")]))
            m.get(f"{API}/core/items/{ITEM_UUID}/bundles",
                  json=embedded("bundles", [bundle_json(BUNDLE_UUID, "ORIGINAL")]))
            m.post(f"{API}/authz/resourcepolicies", status_code=201, json={"id": 1})
            m.get(f"{API}/core/clarinlruallowances",
                  json=embedded("clarinlruallowances", [clarin_allowance_json(1)]))

            item = c.get_item_by_handle("123456789/42")
            self.assertEqual(item.uuid, ITEM_UUID)

            bundle = c.get_bundle_by_name("ORIGINAL", item.uuid)
            self.assertEqual(bundle.name, "ORIGINAL")

            ok = c.create_resource_policy(
                BITSTREAM_UUID, data={"action": "READ"}, group_uuid=GROUP_UUID)
            self.assertTrue(ok)

            allowances = c.get_clarinlruallowances()
            self.assertEqual(len(allowances), 1)


class TestItemImporterPolicyRead(unittest.TestCase):
    """Mirrors dspace-item-importer - create a policy, then read it back using
    the `.get('id')` access form (not the `["id"]` subscript import-clarin uses)."""

    def test_create_then_get_with_dict_get(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authz/resourcepolicies", status_code=201, json={"id": 88})
            m.get(f"{API}/authz/resourcepolicies/search/resource",
                  json=embedded("resourcepolicies", [raw_policy_json(pid=88)]))

            self.assertTrue(
                c.create_resource_policy(BITSTREAM_UUID, data={"action": "READ"}))

            policy = c.get_resource_policy(BUNDLE_UUID)
            self.assertEqual(policy.get("id"), 88)      # .get(), not [...]


@pytest.mark.dtq_only
class TestRestTestNoArgGetItems(unittest.TestCase):
    """Mirrors dspace-rest-test/tests/integration/create_bitstreams.py:145 -
    the no-arg get_items() call. B1: on main the shadowed second def returned []
    (its `if len(all_items) < 3:` branch flipped); on dtq it paginates and
    returns real items with page=0&size=20."""

    def test_no_arg_get_items_paginates_and_returns_items(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.get(f"{API}/core/items", json=embedded("items", [
                item_json("11111111-1111-1111-1111-111111111111", "A"),
                item_json("22222222-2222-2222-2222-222222222222", "B"),
                item_json("33333333-3333-3333-3333-333333333333", "C")]))
            items = c.get_items()
            self.assertEqual(len(items), 3)
            qs = sent_params(m.last_request)
            self.assertEqual(qs["page"], ["0"])
            self.assertEqual(qs["size"], ["20"])


if __name__ == "__main__":
    unittest.main()
