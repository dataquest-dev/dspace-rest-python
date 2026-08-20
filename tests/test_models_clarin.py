"""
CLARIN/UFAL model classes - License, Label (dspace-import-clarin) and the
Group / User objects the submitter-setup flow builds. No coverage before this.

See test_clarin_read.py for the clarin / dtq_only marker meaning.
"""
import unittest

import pytest

import _helpers  # noqa: F401
from _helpers import (
    group_json, user_json, license_json, label_json, EPERSON_UUID, GROUP_UUID)
from dspace_rest_client.models import License, Label, Group, User

pytestmark = pytest.mark.clarin


class TestLicense(unittest.TestCase):
    """Mirrors dspace-import-clarin - License(...) / .to_dict()."""

    def test_core_fields(self):
        lic = License(license_json(lid=3, name="CC-BY", confirmation=1,
                                   required_info="SEND_TOKEN"))
        self.assertEqual(lic.id, 3)
        self.assertEqual(lic.name, "CC-BY")
        self.assertEqual(lic.confirmation, 1)
        self.assertEqual(lic.requiredInfo, "SEND_TOKEN")
        self.assertTrue(lic.definition)

    def test_nested_clarin_license_label_becomes_label(self):
        lic = License(license_json(label=label_json(lid=10, label="PUB")))
        self.assertIsInstance(lic.licenseLabel, Label)
        self.assertEqual(lic.licenseLabel.label, "PUB")

    def test_extended_labels_list(self):
        lic = License(license_json(extended=[label_json(11, "A"),
                                             label_json(12, "B")]))
        self.assertEqual(len(lic.extendedLicenseLabel), 2)
        self.assertTrue(all(isinstance(x, Label) for x in lic.extendedLicenseLabel))

    def test_to_dict_keys(self):
        lic = License(license_json(lid=3, label=label_json(lid=10)))
        self.assertEqual(
            set(lic.to_dict()),
            {"name", "license_id", "definition", "confirmation",
             "required_info", "label_id"})
        self.assertEqual(lic.to_dict()["license_id"], 3)
        self.assertEqual(lic.to_dict()["label_id"], 10)

    def test_to_dict_label_id_none_when_no_label(self):
        lic = License(license_json())
        self.assertIsNone(lic.to_dict()["label_id"])

    def test_from_empty_resource_does_not_crash(self):
        self.assertIsNone(License({}).name)


class TestLabel(unittest.TestCase):
    """Mirrors dspace-import-clarin - Label(...) / .to_dict()."""

    def test_core_fields_and_to_dict(self):
        lab = Label(label_json(lid=7, label="PUB", title="Public", icon="p.png",
                               extended=True))
        self.assertEqual((lab.label, lab.title, lab.icon), ("PUB", "Public", "p.png"))
        d = lab.to_dict()
        self.assertEqual(d["label_id"], 7)
        self.assertTrue(d["is_extended"])

    def test_extended_defaults_false(self):
        self.assertFalse(Label({"label": "x"}).extended)


class TestGroup(unittest.TestCase):
    """Group is built by create_submit_group / consumed by add_member."""

    def test_fields_and_as_dict(self):
        g = Group(group_json(uuid=GROUP_UUID, name="submitters", permanent=True))
        self.assertEqual((g.uuid, g.name, g.permanent), (GROUP_UUID, "submitters", True))
        self.assertEqual(g.as_dict()["name"], "submitters")


class TestUser(unittest.TestCase):
    """User is built by get_user_by_email / consumed by add_member."""

    def test_fields_and_as_dict(self):
        u = User(user_json(uuid=EPERSON_UUID, email="a@b.c", netid="n1"))
        self.assertEqual((u.uuid, u.email, u.netid), (EPERSON_UUID, "a@b.c", "n1"))
        self.assertTrue(u.canLogIn)
        self.assertEqual(u.as_dict()["email"], "a@b.c")


if __name__ == "__main__":
    unittest.main()
