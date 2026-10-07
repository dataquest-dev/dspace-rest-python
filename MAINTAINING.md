# Maintenance instructions

These notes are for maintenance of the Git / PyPI source and releases, rather than the client library - if you are not a maintainer, you can skip this doc!

## Release tasks

All the tasks we need to do, in order, when releasing a new version:

1. - [ ] **Check the main branch!** - we should have all the changes we want to include merged/picked and tested
2. - [ ] **Update `project.version` in pyproject.toml** - this might include other dependency or project description changes, but usually will just be a case of incrementing the version number, e.g. `0.1.9` -> `0.1.10`. Note the new number.
3. - [ ] **Update CHANGELOG.md** - new versions go at the top of the file. See previous release blocks for formatting. I include a 'thanks' or 'reported by' attribution for PRs contributed or issues reported. The new version number from `pyproject.toml` is used for the heading and the (future) PyPI URL
4. - [ ] **Commit release preparation** - once you are happy with the steps above, commit with a message like 'Prepare release 0.1.10'
5. - [ ] **Push branch** - making sure github is up to date, (in future: CI)
6. - [ ] **Clear out build and dist directories**: OPTIONAL, but nice to start with a clean Python build environment before making this new version
7. - [ ] **Run publish script** - this will run `python -m build` (needs `pip install build twine`) to build the sdist and wheel from `pyproject.toml`, check them and upload `dist/*` to PyPI with twine - you will be prompted for credentials interactively

TODO: If we just keep a `version` file around some of these steps can be more easily automated or derived instead of updated by hand, but for now it's all pretty simple.