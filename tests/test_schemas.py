#!/usr/bin/env python3
"""Contract tests for the JSON Schemas and taxonomy registries.

- Positive/negative fixtures against schemas/resource.schema.json.
- Taxonomy registry files validate against schemas/taxonomy.schema.json.
- Schema enums are cross-checked against the live registries (single source
  of truth lives in catalog/taxonomy/; the schema must not drift from it).
- Synonym targets resolve to exactly one registry slug.
- Export/meta/envelope fixtures validate against their schemas.
"""
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = REPO_ROOT / "schemas"
TAX_DIR = REPO_ROOT / "catalog" / "taxonomy"
FX = REPO_ROOT / "tests" / "fixtures" / "schema"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def validator_for(name):
    return Draft202012Validator(load(SCHEMAS / name), format_checker=FormatChecker())


class TestResourceSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = validator_for("resource.schema.json")

    def assert_invalid(self, fixture, needle):
        rec = load(FX / fixture)
        errs = list(self.v.iter_errors(rec))
        self.assertTrue(errs, f"{fixture} unexpectedly valid")
        self.assertTrue(any(needle in e.message for e in errs),
                        f"{fixture}: no error mentioning {needle!r}; got {[e.message for e in errs]}")

    def test_valid_fixture(self):
        errs = list(self.v.iter_errors(load(FX / "valid-resource.json")))
        self.assertEqual(errs, [])

    def test_rejects_bad_id(self):
        self.assert_invalid("invalid-id.json", "does not match")

    def test_rejects_bad_date(self):
        self.assert_invalid("invalid-date.json", "not a 'date'")

    def test_rejects_non_https_url(self):
        self.assert_invalid("invalid-url.json", "does not match")

    def test_rejects_unknown_type(self):
        self.assert_invalid("invalid-type.json", "not one of")

    def test_rejects_empty_topics(self):
        self.assert_invalid("empty-topics.json", "too short")

    def test_rejects_too_many_topics(self):
        self.assert_invalid("too-many-topics.json", "too long")

    def test_rejects_unknown_topic(self):
        self.assert_invalid("unknown-topic.json", "not one of")

    def test_rejects_extra_internal_field(self):
        rec = load(FX / "extra-field.json")
        errs = list(self.v.iter_errors(rec))
        self.assertTrue(any("Additional properties" in e.message for e in errs),
                        "leaked internal provenance field was not rejected")

    def test_rejects_missing_required(self):
        self.assert_invalid("missing-required.json", "required property")


class TestTaxonomyRegistries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = validator_for("taxonomy.schema.json")
        cls.docs = {}
        for f in TAX_DIR.glob("*.json"):
            if f.name == "synonyms.json":
                continue
            cls.docs[f.name] = load(f)

    def test_files_validate(self):
        for name, doc in self.docs.items():
            errs = list(self.v.iter_errors(doc))
            self.assertEqual(errs, [], f"{name}: {errs}")

    def test_schema_enums_match_registries(self):
        """The schema's enums must equal the registry slugs exactly."""
        schema = load(SCHEMAS / "resource.schema.json")
        facet_file = {
            "resource_type": "resource-types.json",
            "topics": "topics.json",
            "use_cases": "use-cases.json",
            "interfaces": "interfaces.json",
            "technologies": "technologies.json",
        }
        for prop, fname in facet_file.items():
            prop_def = schema["properties"][prop]
            enum = prop_def.get("enum") or prop_def["items"]["enum"]
            registry_slugs = sorted(self.docs[fname]["values"].keys())
            self.assertEqual(sorted(enum), registry_slugs,
                             f"schema enum drift for {prop}")

    def test_no_duplicate_aliases(self):
        seen = {}
        for name, doc in self.docs.items():
            for slug, val in doc["values"].items():
                for a in val.get("aliases", []):
                    self.assertNotIn(a, seen, f"alias {a!r} duplicated ({name})")
                    seen[a] = name

    def test_aliases_do_not_shadow_real_slugs(self):
        slugs = {s for doc in self.docs.values() for s in doc["values"]}
        for name, doc in self.docs.items():
            for slug, val in doc["values"].items():
                for a in val.get("aliases", []):
                    self.assertNotIn(a, slugs - {slug},
                                     f"alias {a!r} in {name} shadows a real slug")

    def test_synonym_targets_resolve(self):
        slugs = {s for doc in self.docs.values() for s in doc["values"]}
        syns = load(TAX_DIR / "synonyms.json")["synonyms"]
        self.assertTrue(len(syns) >= 20, "synonym list unexpectedly small")
        for term, target in syns.items():
            self.assertIn(target, slugs, f"synonym {term!r} -> unknown {target!r}")


class TestExportSchemas(unittest.TestCase):
    def test_meta_fixture(self):
        schema = load(SCHEMAS / "exports.schema.json")
        v = Draft202012Validator(schema["$defs"]["meta"], format_checker=FormatChecker())
        self.assertEqual(list(v.iter_errors(load(FX / "valid-meta.json"))), [])

    def test_facets_fixture(self):
        schema = load(SCHEMAS / "exports.schema.json")
        v = Draft202012Validator(schema["$defs"]["facets"])
        self.assertEqual(list(v.iter_errors(load(FX / "valid-facets.json"))), [])

    def test_envelope_fixtures(self):
        schema = load(SCHEMAS / "envelope.schema.json")
        v = Draft202012Validator(schema["$defs"]["resource_list_envelope"],
                                 format_checker=FormatChecker())
        self.assertEqual(list(v.iter_errors(load(FX / "valid-envelope.json"))), [])
        verr = Draft202012Validator(schema["$defs"]["error_envelope"])
        bad = list(verr.iter_errors(load(FX / "invalid-envelope.json")))
        self.assertTrue(bad, "invalid error envelope unexpectedly valid")


if __name__ == "__main__":
    unittest.main()
