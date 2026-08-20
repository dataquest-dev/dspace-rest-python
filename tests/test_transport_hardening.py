"""
Transport hardening introduced on dtq - timeout / proxies on every verb, the
verify_response helper, and the last_err bookkeeping. These are the changes
that make the newly merged CLARIN methods actually surface transient failures
(instead of hanging) - so they are proven here against the low-level api_*.

All dtq_only: main's client takes no timeout/proxies and has no
verify_response / last_err.
"""
import unittest

import pytest

import _helpers  # noqa: F401
from _helpers import make_client, API

pytestmark = [pytest.mark.dtq_only]


class FakeResp:
    """Minimal stand-in for requests.Response - enough for update_token /
    parse_json / verify_response to run without a real transport."""

    def __init__(self, status_code=200, body=None, bad_json=False):
        self.status_code = status_code
        self.headers = {}
        self.url = "http://dspace.test"
        self.text = "" if body is None else str(body)
        self._body = {} if body is None else body
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._body


class RecordingSession:
    """Captures the kwargs each verb is called with."""

    def __init__(self, resp):
        self._resp = resp
        self.calls = {}

    def _verb(self, name):
        def f(url, **kw):
            self.calls[name] = kw
            return self._resp
        return f

    def __getattr__(self, name):
        if name in ("get", "post", "put", "delete", "patch"):
            return self._verb(name)
        raise AttributeError(name)


def _client_with_session(timeout=42, proxies=None):
    c = make_client()
    c.timeout = timeout
    c.proxies = proxies if proxies is not None else {"http": "http://proxy:3128"}
    sess = RecordingSession(FakeResp(200, {}))
    c.session = sess
    return c, sess


class TestTimeoutAndProxiesOnEveryVerb(unittest.TestCase):

    def test_timeout_is_passed_on_every_verb(self):
        c, sess = _client_with_session(timeout=7)
        c.api_get(f"{API}/x")
        c.api_post(f"{API}/x", params=None, json={})
        c.api_put(f"{API}/x", params=None, json={})
        c.api_delete(f"{API}/x", params=None)
        for verb in ("get", "post", "put", "delete"):
            self.assertEqual(sess.calls[verb].get("timeout"), 7,
                             f"{verb} did not pass timeout to the transport")

    def test_proxies_are_passed_on_every_verb(self):
        proxies = {"http": "http://proxy:3128", "https": "http://proxy:3128"}
        c, sess = _client_with_session(proxies=proxies)
        c.api_get(f"{API}/x")
        c.api_post(f"{API}/x", params=None, json={})
        c.api_put(f"{API}/x", params=None, json={})
        c.api_delete(f"{API}/x", params=None)
        for verb in ("get", "post", "put", "delete"):
            self.assertEqual(sess.calls[verb].get("proxies"), proxies,
                             f"{verb} did not pass proxies to the transport")

    def test_clarin_get_honours_custom_timeout(self):
        """A CLARIN read (get_clarinlruallowances) must ride the same timeout."""
        c, sess = _client_with_session(timeout=3)
        c.get_clarinlruallowances()
        self.assertEqual(sess.calls["get"].get("timeout"), 3)


class TestVerifyResponse(unittest.TestCase):

    def test_non_200_records_last_err_and_returns_false(self):
        c = make_client()
        r = FakeResp(503, "unavailable")
        self.assertFalse(c.verify_response(r, "id:1"))
        self.assertIs(c.last_err, r)

    def test_200_ok_returns_true(self):
        c = make_client()
        self.assertTrue(c.verify_response(FakeResp(200, {"ok": True}), "id:1"))

    def test_as_json_on_invalid_body_returns_false(self):
        c = make_client()
        self.assertFalse(
            c.verify_response(FakeResp(200, bad_json=True), "id:1", as_json=True))


class TestLastErrReset(unittest.TestCase):

    def test_last_err_is_reset_at_the_start_of_each_request(self):
        """A stale error from a previous call must not be read by the next one:
        api_* clears _last_err on entry."""
        c, _sess = _client_with_session()
        c._last_err = FakeResp(500, "stale")
        c.api_get(f"{API}/x")
        self.assertIsNone(c.last_err)


if __name__ == "__main__":
    unittest.main()
