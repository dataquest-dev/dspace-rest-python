# Changelog

### 0.2.0

Date: Unreleased

**Changes**

1. Migrated packaging and release builds from `setup.py` to `pyproject.toml`.
2. Raised the minimum supported Python version to 3.10 and added type checking.
3. Hardened UUID validation across every UUID-taking method (`get_dso`, `get_item`,
   `get_resourcepolicy`, `create_resourcepolicy`, `get_owningCollection`): a `None`
   or non-string argument is now logged and returns `None` instead of raising
   `TypeError`.
4. A non-JSON `401`/`403` body no longer crashes the CSRF-refresh/retry path of
   `api_post`, `api_post_uri`, `api_put`, `api_put_uri`, `api_delete`, `api_patch`
   and `create_bitstream`.
5. `get_communities`, `get_collections` and `get_bundle_by_name` return `None` on a
   failed or non-JSON response instead of raising `TypeError`.
6. `add_metadata` / `remove_metadata` return `None` (not the client) on invalid input.
7. Model instances no longer share class-level `links`, `embedded`, `checkSum` or
   `sections` dicts, `Group()` / `User()` accept a `None` API resource, and
   `Item.from_dso` / `DSpaceObject(dso=...)` deep-copy metadata instead of aliasing it.
8. `models.__all__` exports the full model surface re-exported by the package.
9. Moved direct Solr support to the documented `solr` optional dependency group;
   `solr_query()` raises an actionable `RuntimeError` when the extra is missing.

### 0.1.10

Date: 2024-04-04

PyPI release page: https://pypi.org/project/dspace-rest-client/0.1.10/

**Changes**

1. Correct content type header for URI tests: https://github.com/the-library-code/dspace-rest-python/pull/14 (thanks to @andreasgeissner)
2. Small change to example script checks for successful bitstream header retrieve before printing
3. Added new `MAINTAINING.md` to keep notes about build and publish process with the rest of the project files

### 0.1.9

Date: 2023-12-03

PyPI release page: https://pypi.org/project/dspace-rest-client/0.1.9/

**Changes**

1. All `print` statements in client module replaced with Python logging: https://github.com/the-library-code/dspace-rest-python/issues/12
2. A customisable user agent header is added to each request, to allow for better logging at the
API endpoint and to force requests through Cloudfront, other WAF proxies that filter
requests by user agent. Reported by @abubelinha: https://github.com/the-library-code/dspace-rest-python/issues/10
3. In the `search_objects` client method, the `dsoType` arg is renamed to `dso_type` to conform with
PEP 8 style guidlelines, and a new `scope` arg is added to restrict the search to a particular collection or community.
4. A new `get_items` client method is added, to get all items (admin-only)
5. A new `get_short_lived_token` client method is added, for bitstream retrieval
6. A new `download_bitstream` client method is added to retrieve actual /content
7. A new `example_gets.py` script is added, and `example.py` updated to include basic examples of how to retrieve, iterate and work with existing data in the repository. Reported by @pnbecker: https://github.com/the-library-code/dspace-rest-python/issues/11
8. pysolr added to requirements.txt to satisfy this solr client dependency missing from the last version: https://github.com/the-library-code/dspace-rest-python/issues/7

### 0.1.8

PyPI release page: https://pypi.org/project/dspace-rest-client/0.1.8/

Date: 2023-10-07

**Changes**

Fixes a bug when using get_communities with a uuid parameter to fetch a single community, 
see: https://github.com/the-library-code/dspace-rest-python/issues/8