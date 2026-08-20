"""
CLARIN/UFAL write surface - resource-policy creation, submitter-group setup,
group membership and metadata removal. Called by dspace-rest-test and
dspace-import-clarin; zero coverage before this suite.

Mock only the HTTP transport. Each test names the consumer it mirrors.
See test_clarin_read.py for the clarin / dtq_only marker meaning.
"""
import unittest

import pytest
import requests_mock

import _helpers  # noqa: F401
from _helpers import (
    make_client, sent_params, item_json, embedded,
    API, ITEM_UUID, BITSTREAM_UUID, COLLECTION_UUID, EPERSON_UUID, GROUP_UUID)
from dspace_rest_client.models import Group, User, Collection, Item

pytestmark = pytest.mark.clarin

LOGIN_URL = f"{API}/authn/login"
STATUS_URL = f"{API}/authn/status"


class TestCreateResourcePolicy(unittest.TestCase):
    """Mirrors dspace-rest-test / dspace-item-importer -
    create_resource_policy(resource, data, group_uuid=...) truthiness."""

    URL = f"{API}/authz/resourcepolicies"

    def test_sends_resource_and_group_params_and_body(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(self.URL, status_code=201, json={"id": 5})
            ok = c.create_resource_policy(
                BITSTREAM_UUID, data={"action": "READ"}, group_uuid=GROUP_UUID)
            self.assertTrue(ok)
            qs = sent_params(m.last_request)
            self.assertEqual(qs["resource"], [BITSTREAM_UUID])
            self.assertEqual(qs["group"], [GROUP_UUID])
            self.assertNotIn("eperson", qs)
            self.assertEqual(m.last_request.json(), {"action": "READ"})

    def test_sends_eperson_param_when_given(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(self.URL, status_code=201, json={"id": 5})
            c.create_resource_policy(
                BITSTREAM_UUID, data={"action": "READ"}, eperson_uuid=EPERSON_UUID)
            qs = sent_params(m.last_request)
            self.assertEqual(qs["eperson"], [EPERSON_UUID])
            self.assertNotIn("group", qs)

    def test_omits_absent_optional_params(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(self.URL, status_code=201, json={"id": 5})
            c.create_resource_policy(BITSTREAM_UUID, data={"action": "READ"})
            qs = sent_params(m.last_request)
            self.assertEqual(qs["resource"], [BITSTREAM_UUID])
            self.assertNotIn("group", qs)
            self.assertNotIn("eperson", qs)

    def test_returns_true_only_on_201(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(self.URL, status_code=201, json={"id": 5})
            self.assertIs(c.create_resource_policy(BITSTREAM_UUID, data={}), True)

    def test_non_201_returns_false(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(self.URL, status_code=422, json={"message": "bad"})
            self.assertIs(c.create_resource_policy(BITSTREAM_UUID, data={}), False)

    def test_401_reauthenticates_and_retries(self):
        """A 401 triggers authenticate()+retry, so a policy create that hit an
        expired session still succeeds. Shared: both main and dtq's api_post
        carry this reauth block (verified against the main impl), so it is a
        contract both must keep - not a dtq-only delta."""
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(self.URL, [
                {"status_code": 401,
                 "json": {"message": "Authentication is required"}},
                {"status_code": 201, "json": {"id": 5}}])
            m.post(LOGIN_URL, status_code=200)
            m.get(STATUS_URL, status_code=200, json={"authenticated": True})
            ok = c.create_resource_policy(BITSTREAM_UUID, data={"action": "READ"})
            self.assertTrue(ok)
            posts = [h for h in m.request_history
                     if h.method == "POST" and h.url.startswith(self.URL)]
            self.assertEqual(len(posts), 2)      # first 401, retry 201


class TestUpdateResourcePolicyGroup(unittest.TestCase):
    """Mirrors dspace-import-clarin - update_resource_policy_group(id, group)."""

    def test_puts_uri_list_and_returns_response(self):
        c = make_client()
        url = f"{API}/authz/resourcepolicies/77/group"
        with requests_mock.Mocker() as m:
            m.put(url, status_code=200, json={})
            r = c.update_resource_policy_group(77, GROUP_UUID)
            self.assertEqual(r.status_code, 200)       # returns raw Response
            self.assertEqual(m.last_request.text,
                             f"{API}/eperson/groups/{GROUP_UUID}")
            self.assertEqual(
                m.last_request.headers["Content-type"], "text/uri-list")

    def test_403_csrf_retries_once(self):
        c = make_client()
        url = f"{API}/authz/resourcepolicies/77/group"
        with requests_mock.Mocker() as m:
            m.put(url, [
                {"status_code": 403, "json": {"message": "Invalid CSRF token"}},
                {"status_code": 200, "json": {}}])
            r = c.update_resource_policy_group(77, GROUP_UUID)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(
                len([h for h in m.request_history if h.method == "PUT"]), 2)


class TestCreateSubmitGroup(unittest.TestCase):
    """Mirrors dspace-rest-test - create_submit_group(collection)."""

    def _collection(self):
        return Collection({"uuid": COLLECTION_UUID, "type": "collection"})

    def test_posts_to_submitters_group_url_and_returns_group(self):
        c = make_client()
        url = f"{API}/core/collections/{COLLECTION_UUID}/submittersGroup"
        with requests_mock.Mocker() as m:
            m.post(url, status_code=201,
                   json={"uuid": GROUP_UUID, "name": "submitters", "type": "group"})
            g = c.create_submit_group(self._collection())
            self.assertIsInstance(g, Group)
            self.assertEqual(g.uuid, GROUP_UUID)

    def test_non_201_returns_none(self):
        c = make_client()
        url = f"{API}/core/collections/{COLLECTION_UUID}/submittersGroup"
        with requests_mock.Mocker() as m:
            m.post(url, status_code=500, text="boom")
            self.assertIsNone(c.create_submit_group(self._collection()))


class TestAddMember(unittest.TestCase):
    """Mirrors dspace-rest-test - add_member(group, eperson)."""

    def _group(self):
        return Group({"uuid": GROUP_UUID, "name": "submitters"})

    def _user(self):
        return User({"uuid": EPERSON_UUID, "email": "a@b.c"})

    def test_non_204_returns_false(self):
        c = make_client()
        url = f"{API}/eperson/groups/{GROUP_UUID}/epersons"
        with requests_mock.Mocker() as m:
            m.post(url, status_code=422, json={"message": "nope"})
            self.assertFalse(c.add_member(self._group(), self._user()))

    def test_rejects_non_group_and_non_user_without_request(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertFalse(c.add_member("not-a-group", self._user()))
            self.assertFalse(c.add_member(self._group(), "not-a-user"))
            self.assertFalse(m.called)


class TestRemoveMetadata(unittest.TestCase):
    """Mirrors dspace-import-clarin - remove_metadata(item, field, place)."""

    def _item(self):
        return Item(item_json(
            ITEM_UUID, "T",
            _links={"self": {"href": f"{API}/core/items/{ITEM_UUID}"}}))

    def test_with_place_patches_indexed_path(self):
        c = make_client()
        url = f"{API}/core/items/{ITEM_UUID}"
        with requests_mock.Mocker() as m:
            m.patch(url, status_code=200,
                    json=item_json(ITEM_UUID, "T", id=ITEM_UUID))
            c.remove_metadata(self._item(), "dc.title", 0)
            body = m.last_request.json()
            self.assertEqual(body[0]["op"], "remove")
            self.assertEqual(body[0]["path"], "/metadata/dc.title/0")

    @pytest.mark.dtq_only
    def test_place_none_removes_whole_field(self):
        """B2: BEHAVIOUR CHANGE vs main. On main `place` was mandatory and a
        None place was a no-op; on dtq place=None removes EVERY value of the
        field (path has no index)."""
        c = make_client()
        url = f"{API}/core/items/{ITEM_UUID}"
        with requests_mock.Mocker() as m:
            m.patch(url, status_code=200,
                    json=item_json(ITEM_UUID, "T", id=ITEM_UUID))
            c.remove_metadata(self._item(), "dc.title")     # place defaults None
            body = m.last_request.json()
            self.assertEqual(body[0]["path"], "/metadata/dc.title")

    def test_invalid_dso_returns_self_without_request(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            self.assertIs(c.remove_metadata(None, "dc.title", 0), c)
            self.assertFalse(m.called)


if __name__ == "__main__":
    unittest.main()
