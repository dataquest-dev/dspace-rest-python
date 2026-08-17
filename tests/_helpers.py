"""
Shared helpers for the client test-suite.

The tests mock *only* the HTTP transport (via ``requests_mock``) and let the
real ``DSpaceClient`` build URLs, send params and parse responses into model
objects. That way a change to the library that breaks URL construction or
response parsing - the two things downstream code (this repo) depends on -
fails a test instead of silently shipping.
"""
import json
import os
import re
import sys
from urllib.parse import urlparse, parse_qs

# Make ``dspace_rest_client`` importable when a test module is run directly
# (``python tests/test_x.py``), not just under pytest (see conftest.py).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dspace_rest_client.client import DSpaceClient  # noqa: E402

# Canonical test endpoint. All mocked URLs are built off this so a typo shows
# up as an unmatched request rather than a false pass.
API = "http://dspace.test/server/api"

# Real, syntactically-valid UUIDs - several client methods validate their UUID
# arguments with ``uuid.UUID(...)`` and short-circuit on a bad one, so tests
# that expect a request to actually go out must use valid values.
ITEM_UUID = "11111111-1111-1111-1111-111111111111"
COLLECTION_UUID = "22222222-2222-2222-2222-222222222222"
BITSTREAM_UUID = "9f54ef33-c454-4d8e-a5fe-79d8291045ba"
ANON_GROUP_UUID = "6ecfd145-3b7d-429e-ab31-ef6905a05763"


def make_client(api_endpoint: str = API) -> DSpaceClient:
    """A real client with no network touched.

    ``DSpaceClient.__init__`` performs no HTTP (it only creates a
    ``requests.Session`` and, optionally, a pysolr handle), so a plain
    construction is safe and gives us the genuine object under test.
    """
    return DSpaceClient(api_endpoint, "tester@dspace.test", "secret")


def sent_params(request) -> dict:
    """Case-preserving query params of a captured request.

    ``requests_mock``'s ``request.qs`` lowercases the whole query string, which
    would mangle case-sensitive values (eg. ``action=READ``). Parsing the
    original ``request.url`` keeps the real casing.
    """
    return parse_qs(urlparse(request.url).query)


def multipart_properties(request) -> dict:
    """Parse the JSON ``properties`` part of a create_bitstream multipart body.

    ``create_bitstream`` sends ``properties = json.dumps({name, metadata,
    bundleName}) + ';application/json'`` as a form field. This is what actually
    carries the bitstream's metadata to DSpace, so tests assert on it.
    """
    body = request.body
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    m = re.search(r'name="properties"\r?\n\r?\n(.*?);application/json',
                  body, re.DOTALL)
    return json.loads(m.group(1)) if m else None


# --- response-body builders (shape mirrors the DSpace 7 REST API) --------- #

def embedded(key: str, resources: list) -> dict:
    """A HAL ``_embedded`` list envelope, eg. ``{"_embedded": {"bundles": [...]}}``."""
    return {"_embedded": {key: resources}}


def item_json(uuid: str = ITEM_UUID, name: str = "Thesis", **extra) -> dict:
    d = {"uuid": uuid, "name": name, "type": "item", "metadata": {},
         "inArchive": True, "discoverable": True, "withdrawn": False}
    d.update(extra)
    return d


def bundle_json(uuid: str = "bnd", name: str = "ORIGINAL",
                bitstreams_href: str = None, **extra) -> dict:
    d = {"uuid": uuid, "name": name, "type": "bundle", "metadata": {}}
    if bitstreams_href is not None:
        d["_links"] = {"bitstreams": {"href": bitstreams_href}}
    d.update(extra)
    return d


def bitstream_json(uuid: str = "bs1", name: str = "thesis.pdf", size: int = 123,
                   seq: int = 1, checksum: str = "abc", **extra) -> dict:
    d = {"uuid": uuid, "name": name, "type": "bitstream", "metadata": {},
         "sizeBytes": size, "sequenceId": seq,
         "checkSum": {"checkSumAlgorithm": "MD5", "value": checksum}}
    d.update(extra)
    return d


def policy_json(pid: int = 1, action: str = "READ", group_name: str = "Anonymous",
                group_uuid: str = ANON_GROUP_UUID, start_date: str = None) -> dict:
    """A resource policy in the *live* API shape (group under ``_embedded``)."""
    d = {"id": pid, "action": action,
         "_embedded": {"group": {"name": group_name, "uuid": group_uuid}}}
    if start_date is not None:
        d["startDate"] = start_date
    return d
