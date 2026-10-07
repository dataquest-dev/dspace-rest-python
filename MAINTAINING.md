# Maintenance instructions

These notes are for maintenance of the Git / PyPI source and releases, rather than the client library - if you are not a maintainer, you can skip this doc!

## Release tasks

All the tasks we need to do, in order, when releasing a new version:

1. - [ ] **Check the main branch** — confirm all intended changes are merged and CI is green.
2. - [ ] **Update `project.version` in `pyproject.toml`** — note the new version number.
3. - [ ] **Update `CHANGELOG.md`** — move the new version to the top, add the release date and future PyPI URL, and summarize user-visible changes.
4. - [ ] **Install release tools** — run `python -m pip install ".[release]"`.
5. - [ ] **Run tests and checks** — run `python -m pytest tests/ -v` and `pre-commit run --all-files`.
6. - [ ] **Commit and push release preparation** — use a message such as `Prepare release 0.2.0`, then confirm CI remains green.
7. - [ ] **Run `./publish.sh`** — it clears old artifacts, builds the sdist and wheel from `pyproject.toml`, validates them with Twine, and uploads them to PyPI. Twine prompts for credentials when needed.

The publish script derives artifact names from the build output, so it does not need a version-specific edit.