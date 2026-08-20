"""
Construction and authentication contract.

``ingest.dspace_be`` constructs the client from an endpoint/user/password and
calls ``authenticate()``; a False return is turned into a hard ConnectionError,
so the True/False semantics here matter.
"""
import unittest

import requests_mock

import logging

import _helpers  # noqa: F401
from _helpers import make_client, API
from dspace_rest_client.client import DSpaceClient


class TestConstructor(unittest.TestCase):

    def test_endpoints_derived_from_api_endpoint(self):
        c = make_client("http://host:8080/server/api")
        self.assertEqual(c.API_ENDPOINT, "http://host:8080/server/api")
        self.assertEqual(c.LOGIN_URL, "http://host:8080/server/api/authn/login")
        self.assertIsNotNone(c.session)

    def test_default_last_err_is_none(self):
        self.assertIsNone(make_client().last_err)

    def test_timeout_default_and_override(self):
        # every request must be bounded so a stalled server can't hang forever
        self.assertEqual(make_client().timeout, DSpaceClient.DEFAULT_TIMEOUT)
        self.assertEqual(DSpaceClient(API, "u", "p", timeout=5).timeout, 5)

    def test_library_does_not_hijack_root_logger(self):
        # importing the client must not call logging.basicConfig; the module
        # logger carries a NullHandler so records drop unless the app opts in.
        lg = logging.getLogger("dspace.client")
        self.assertTrue(
            any(isinstance(h, logging.NullHandler) for h in lg.handlers))


class TestAuthenticate(unittest.TestCase):

    def test_success_returns_true_and_propagates_bearer_token(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authn/login", status_code=200,
                   headers={"Authorization": "Bearer tok123"})
            m.get(f"{API}/authn/status", status_code=200,
                  json={"authenticated": True})
            self.assertTrue(c.authenticate())
            # the bearer token must land on the session for later calls
            self.assertEqual(c.session.headers.get("Authorization"), "Bearer tok123")

    def test_invalid_credentials_401_returns_false(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authn/login", status_code=401,
                   json={"message": "invalid"})
            self.assertFalse(c.authenticate())

    def test_status_not_authenticated_returns_false(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authn/login", status_code=200,
                   headers={"Authorization": "Bearer t"})
            m.get(f"{API}/authn/status", status_code=200,
                  json={"authenticated": False})
            self.assertFalse(c.authenticate())

    def test_csrf_403_retries_once_then_gives_up(self):
        c = make_client()
        with requests_mock.Mocker() as m:
            m.post(f"{API}/authn/login", status_code=403,
                   json={"message": "CSRF token required"})
            self.assertFalse(c.authenticate())
            login_calls = [r for r in m.request_history
                           if r.path == "/server/api/authn/login"]
            # initial attempt + exactly one retry with the refreshed token
            self.assertEqual(len(login_calls), 2)


if __name__ == "__main__":
    unittest.main()
